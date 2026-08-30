# Alpaca regular-session execution gate

Date: 2026-08-30

## External trigger

- Upstream project: `HKUDS/Vibe-Trading`
- Upstream commit: `6d98811759a42acd4ab7856c38eaa0bafaab867c` (`Merge PR #1253: skip closed-market trigger ticks`)
- Upstream license: MIT
- Reuse mode: behavioral principle only; no upstream source code copied or adapted.

The upstream change prevents market-triggered autonomous runs from queuing orders while their markets are closed. The useful invariant is broader than that implementation: an autonomous trading decision generated from a market event must not silently become a future-session order merely because the broker accepts and queues the mutation.

## Official provider evidence

Alpaca's official equity-order documentation states that a `day` order is regular-hours-only by default and that a non-extended-hours order submitted after the close is queued for the following trading day. Alpaca also exposes `GET /v2/clock`, whose response states whether the US market is currently open and supplies next-open/next-close information.

The repository's Alpaca stock bar feed can receive market-data events outside the regular session, while the execution adapter always emits `time_in_force=day` and does not enable `extended_hours`. Before this change, the adapter could therefore accept a fresh pre/post-market signal and hand Alpaca a DAY order that would sit queued until a later regular session.

## Local RED

- RED commit: `ec78b4e2178439b8b3872f373ded14e89e38c45c`
- CI: `#647`
- Result: Python 3.12 full pytest produced exactly `1 failed, 271 passed`; Ruff, dependency audit, and container build were unrelatedly healthy.
- Failure: `test_alpaca_submit_refuses_to_queue_day_order_when_market_is_closed` observed the current adapter POST `/v2/orders` and return `ACCEPTED` even though a mocked authoritative Alpaca clock reported `is_open=false`.

This proved the local gap at the broker mutation boundary rather than merely inferring it from documentation.

## Minimal GREEN

- Implementation commit: `e390efd7acb65a053b735bf06f8cb21b9ae59597`
- Contract-alignment commits: `dd8b5d645187e7a3a24e21ccb3e9330a40706b45`, `d9d8cf2b0aa8dcf907aeeb2a47983dbd9c620ffb`
- GREEN CI: `#653` on `d9d8cf2b0aa8dcf907aeeb2a47983dbd9c620ffb`, complete success.

`AlpacaExecutionAdapter.submit()` now checks the provider's `/v2/clock` before any DAY-order mutation. It behaves as follows:

1. `is_open=true`: continue through the existing submit path unchanged.
2. `is_open=false`: return a deterministic `REJECTED / alpaca_market_closed` result without POSTing an order.
3. clock transport failure, HTTP error, malformed JSON, or missing/non-boolean `is_open`: return `REJECTED / alpaca_market_clock_unavailable` without attempting an order mutation.
4. once an order POST has begun, the existing ambiguous transport/HTTP semantics remain unchanged (`UNKNOWN` followed by reconciliation where required).
5. cancel and reconciliation remain available outside market hours; the new gate applies only to creating a new DAY order.

The clock failure is represented as a rejection rather than `UNKNOWN` because no order mutation has been attempted yet; there is no ambiguous broker order outcome to reconcile.

## Security, dependency, and runtime impact

- No new runtime or CI dependency.
- No credentials or account identifiers added.
- No extended-hours capability enabled.
- One provider read is added immediately before an Alpaca order submission. This deliberately favors session correctness over a small amount of added latency.
- Using Alpaca's own clock avoids maintaining a local exchange-holiday/early-close calendar and therefore avoids a new dependency and duplicated source of session truth.

## Durable invariant

A market-data event occurring outside an order's eligible execution session must not silently queue a stale autonomous intent into a later session. Before a new broker mutation, the execution boundary must have provider-appropriate evidence that the intended order is currently eligible to execute. If that eligibility cannot be established, creation of new exposure fails closed. Explicit extended-hours support, if introduced later, requires its own reviewed capability model, order-type/TIF restrictions, liquidity/risk controls, and tests.

## Rollback

The change is isolated to the Alpaca submit preflight and its tests. It can be reverted through normal Git history without schema/data migration. Reverting would intentionally restore the prior ability to queue DAY orders outside the regular session and should therefore require explicit safety review.
