# Reconciliation Evidence Binding — 2026-08-26

## Trigger

Upstream: `nautechsystems/nautilus_trader`
Commit: `ccc80cdb2d5ba6520152e4a3df544715d2143772`
Observed: 2026-08-26
License: LGPL-3.0

The upstream Polymarket reconciliation change tightened REST report authority: order/fill evidence is validated against the requested account, instrument, and order scope before it is allowed to affect reconciliation. Contradictory owned evidence is propagated rather than silently accepted.

No upstream source code was copied or adapted. This repository used the behavior as conceptual evidence and independently tested its own broker adapters.

## Local audit

IBKR already binds disconnect-recovery trade history to the queried `order_ref` and configured account before extracting one broker order id and asking the authoritative order-status endpoint for terminal state.

Alpaca had a narrower gap. `GET /v2/orders:by_client_order_id` was queried with the expected client-order id, but the returned payload was mapped without checking that its `client_order_id` matched the query. A contradictory response could therefore be accepted as `FILLED` and attributed to the wrong local order.

## RED

Commit: `b0783d90e2b85cc9b83298a51d802c438fccca2b`
CI: `#532`

The new test returns a successful Alpaca lookup response for a different `client_order_id` and marks that unrelated order as filled. Before the fix, full pytest failed exactly at this contract: `1 failed, 241 passed`; the adapter returned `FILLED` for the unrelated order instead of failing closed.

## GREEN

Commit: `ec6054e71aa43583fead96ff0d0ce1ccbb50cfa9`
CI: `#534`

The Alpaca lookup now verifies that the response `client_order_id` exactly matches the requested identity before accepting broker state. A missing or contradictory identity returns `UNKNOWN` with code `alpaca_lookup_identity_mismatch`, preserves the queried client-order id, and does not import unrelated fill quantity or price.

Python 3.12 and 3.13 full tests, Ruff, compileall, engineering-skill verification, and Docker build passed on the GREEN commit.

## Durable rule

Reconciliation evidence is not authoritative merely because it came from a broker endpoint. Evidence used to resolve an unknown mutation must be bound to the identity being reconciled; where the provider exposes account/instrument/order identity, contradictory evidence fails closed and cannot be used to claim a fill or terminal state.

For future adapters, the minimum binding dimensions should be the strongest identifiers the provider makes authoritative: client/order reference, broker order id, account, and instrument where available.

## Rollback

The change is isolated to the Alpaca lookup validation and one regression test. It can be reverted independently if Alpaca changes the documented response identity contract, but any replacement must retain an equally strong fail-closed proof that an unrelated order cannot satisfy reconciliation.