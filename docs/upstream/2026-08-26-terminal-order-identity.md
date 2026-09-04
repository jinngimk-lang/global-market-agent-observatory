# Terminal order identity across reconnects and late fills — 2026-08-26

## Upstream evidence

Repository: `nautechsystems/nautilus_trader`
Commit: `8ecab1ce90d9790b1e18e162842decbae4d9de57`
Observed upstream commit time: 2026-08-26 02:30:59 UTC
License: LGPL-3.0

Upstream theme: retain terminal order identity across reconnects so late fills, void/correction events, replacement chains, and reconciliation reports can still be correlated to the original local order without duplicating terminal transitions.

Relevant mechanisms described by the upstream change include retaining a bounded set of closed-order identities, restoring closed identity from cache after reconnect, preserving multiple venue-order identifiers across replacements, and routing late terminal evidence through retained local identity.

No NautilusTrader source code is copied or adapted here. This record is conceptual evidence only.

## Local relevance

The local project already has strong identity binding for active/unknown execution recovery:

- client-order IDs are idempotent;
- Alpaca reconciliation accepts REST order truth only when the returned client-order identity exactly matches the query;
- IBKR unknown-order recovery binds recent execution history to exact `order_ref` plus configured account and then asks the authoritative order-status endpoint for terminal truth;
- unknown execution outcomes reconcile before retry.

The new upstream evidence highlights a different lifecycle boundary: a broker event can arrive after local state has already considered an order terminal, especially across reconnects, replacements, late fills, busts/voids, or corrections. A system that discards terminal identity too aggressively can fail to correlate that evidence or can accidentally treat it as a new order lifecycle.

## Decision

Do not copy the LGPL implementation and do not add a generic closed-order cache without a local failing test. The current Alpaca/IBKR paths do not yet demonstrate the same late-terminal-event failure mode.

Preserve this invariant for future execution/reconciliation work:

> Terminal state does not erase order identity. Broker evidence that arrives late must remain correlatable to the strongest durable local/broker identifiers, and applying late evidence must be idempotent.

If streaming execution events, replace chains, bust/void corrections, or asynchronous late fills are added, create failure-injection tests that cover reconnect plus terminal-state retention before implementation. Retention must be bounded and must never authorize a retry or new exposure by itself.

## Related upstream delta

NautilusTrader commit `d99ffbbfb3465a5254b055a7c67d6a5232215bf6` on 2026-08-26 also tightened retry timeout tests so they prove the intended `OperationTimeout` path instead of merely asserting a generic error. This reinforces the repository's existing verification rule that RED tests must fail for the intended behavioral reason. No local change is needed because current TDD evidence records exact failing contracts rather than generic `is_err`-style success criteria.
