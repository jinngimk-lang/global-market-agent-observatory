# Conditional Order Identity and Lifecycle Routing — 2026-08-26

## Upstream evidence

Repository: `nautechsystems/nautilus_trader`
Commit: `30d5002e13fe2d8d384941638f95935671db0ce3`
Observed: 2026-08-26 10:35 UTC
License: LGPL-3.0
Theme: conditional/algo order identity, replay deduplication, and post-trigger routing.

No upstream source code was copied or adapted. This record captures behavior and design constraints only.

## Verified upstream behavior

The upstream commit standardizes OKX algo-order lifecycle routing by:

- binding a conditional/algo parent and its triggered child to one tracked logical order identity;
- routing commands and later events through the authoritative venue order id after the child exists;
- holding identity-binding races instead of applying whichever event arrives first;
- suppressing stale or replayed parent updates once a newer authoritative child binding exists;
- keeping late-fill recovery separate from normal parent/child lifecycle routing.

The upstream commit is signed/verified in GitHub and directly follows the previously reviewed reducing-risk fix `8aa30f9acad6c623eca9a1489e3a4cd4c955f66f`.

## Local comparison

The current project execution layer supports the present Alpaca/IBKR market/limit-oriented order lifecycle and does not yet expose a general conditional-order parent/triggered-child or replace-chain abstraction. Existing safety work already requires exact client-order identity for Alpaca reconciliation and account/order binding for IBKR recovery, but there is no local conditional-order lifecycle to patch today.

Introducing a parent/child identity subsystem now would therefore add state-machine complexity without closing a demonstrated current failure. No production code or dependency change is justified by this delta alone.

## Durable constraint for future order-type expansion

If the project later adds stop/triggered/algo orders, replace chains, or venue-generated child orders, the implementation must preserve these invariants:

1. One logical strategy order retains a stable local identity across provider parent/child transitions.
2. Once a provider child or replacement becomes authoritative, later commands must use the strongest current provider identity rather than a stale parent id.
3. Stale/replayed parent events cannot overwrite newer child/replacement truth.
4. Identity-binding races must resolve deterministically and fail closed when ambiguous.
5. Late fills/corrections remain a separate reconciliation path and must not be conflated with ordinary lifecycle routing.
6. Any future adoption requires local failure-injection tests before implementation and must preserve reconciliation-before-retry.

## Decision

Conceptual reuse only. Keep this as a future execution-contract requirement. Do not add conditional-order breadth until a concrete strategy or broker requirement exists and a local RED test demonstrates the state transition that must be supported.
