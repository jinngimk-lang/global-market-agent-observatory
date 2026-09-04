# Conditional Order Identity and Lifecycle Routing — 2026-08-26

## Upstream evidence

Repository: `nautechsystems/nautilus_trader`
Primary commit: `30d5002e13fe2d8d384941638f95935671db0ce3`
Follow-up commit: `d36b7eb1c2b357a35ec3bc8ec98a8cfa64450ae4`
Primary observed: 2026-08-26 10:35 UTC
Follow-up observed: 2026-08-27 03:54 UTC
License: LGPL-3.0
Theme: conditional/algo order identity, ownership-based command routing, replay deduplication, and post-trigger routing.

No upstream source code was copied or adapted. This record captures behavior and design constraints only.

## Verified upstream behavior

The primary upstream commit standardizes OKX algo-order lifecycle routing by:

- binding a conditional/algo parent and its triggered child to one tracked logical order identity;
- routing commands and later events through the authoritative venue order id after the child exists;
- holding identity-binding races instead of applying whichever event arrives first;
- suppressing stale or replayed parent updates once a newer authoritative child binding exists;
- keeping late-fill recovery separate from normal parent/child lifecycle routing.

The follow-up commit closes a distinct ownership/status race for emulated trigger orders. `submit_order` and `cancel_order` already routed trigger-carrying orders to the order emulator based on execution ownership, but `modify_order` used transient `is_emulated()` status. A strategy can synchronously modify an order after initialization but before the emulator has processed submission, so the order is emulator-owned before it is emulator-known. In that window the status predicate misrouted the modify toward the risk path and the modification could be dropped. Upstream changed modify routing to use the same ownership predicate as cancel routing.

Both upstream commits are signed/verified in GitHub.

## Local comparison

The current project execution layer supports the present Alpaca/IBKR market/limit-oriented order lifecycle and does not yet expose a general conditional-order parent/triggered-child, local order-emulator ownership, or replace-chain abstraction. Existing safety work already requires exact client-order identity for Alpaca reconciliation and account/order binding for IBKR recovery, but there is no local conditional-order lifecycle or trigger-emulator modify path to patch today.

Introducing a parent/child identity subsystem or emulator-routing layer now would therefore add state-machine complexity without closing a demonstrated current failure. No production code or dependency change is justified by these deltas alone.

## Durable constraint for future order-type expansion

If the project later adds stop/triggered/algo orders, replace chains, venue-generated child orders, or local order emulation, the implementation must preserve these invariants:

1. One logical strategy order retains a stable local identity across provider parent/child transitions.
2. Once a provider child or replacement becomes authoritative, later commands must use the strongest current provider identity rather than a stale parent id.
3. Stale/replayed parent events cannot overwrite newer child/replacement truth.
4. Identity-binding races must resolve deterministically and fail closed when ambiguous.
5. Command routing must follow declared execution ownership/capability, not a transient lifecycle status that may lag ownership handoff. Submit, modify, and cancel must use one coherent ownership predicate.
6. An order may be owned by an execution subsystem before that subsystem has emitted the status that makes the ownership externally visible; synchronous event handlers must not create a routing gap in that window.
7. Late fills/corrections remain a separate reconciliation path and must not be conflated with ordinary lifecycle routing.
8. Any future adoption requires local failure-injection tests before implementation and must preserve reconciliation-before-retry.

## Decision

Conceptual reuse only. Keep these as future execution-contract requirements. Do not add conditional-order or emulator breadth until a concrete strategy or broker requirement exists and a local RED test demonstrates the state transition that must be supported.
