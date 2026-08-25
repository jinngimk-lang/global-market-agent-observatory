# Ecosystem Scan — 2026-08-25

## Scope

This scan follows `docs/AUTONOMOUS_OWNER_GOVERNANCE.md` and records upstream changes that may materially improve execution correctness, market-data resilience, or live-operation safety.

No upstream source code was copied in this scan. The listed projects are being used as evidence and design references only until a local failing test demonstrates a real repository gap.

## NautilusTrader

Repository: `nautechsystems/nautilus_trader`
License: LGPL-3.0

### Commit `d2b1221ca20165d7286525e8bec295cc56f1413b`

Theme: execution recovery correctness.

Relevant upstream behavior:

- classify transport outcomes before rolling back pending commands;
- retain pending state for ambiguous outcomes that require reconciliation;
- distinguish local/definite rejection from ambiguous transport failure;
- preserve partial reconciliation data without claiming full completeness.

Local relevance:

Our project already treated transport errors and server-side unknown execution results as reconciliation-required, but a local RED audit found that HTTP 408/429 on mutation endpoints were still being interpreted as definite `REJECTED` results. These statuses can occur after a request crossed a network/proxy/rate-limit boundary, so an automatic retry after such a classification can duplicate an order or cancellation.

Local integration completed:

- `tests/test_broker_mutation_outcomes.py` created ten targeted RED cases for HTTP 408/429;
- Alpaca submit/cancel now return provider-specific `UNKNOWN` results for those ambiguous HTTP outcomes;
- IBKR submit, precautionary-confirmation reply, and cancel now return provider-specific `UNKNOWN` results for those outcomes;
- `app/broker/http_outcomes.py` centralizes the local mutation-status classification;
- implementation commits: `6fd5701662eb4cb46a9d7a1a11f6deca9b4f6d3b` and `06737299996dfbc97df9fc588ff2277a45a4eec2`;
- exact-head CI `#450` passed Ruff, full pytest on Python 3.12/3.13, compileall, engineering-skill verification, and Docker build.

License/provenance decision: conceptual reuse only. No NautilusTrader LGPL source was copied or adapted.

Decision: local gap closed for the current Alpaca submit/cancel and IBKR submit/confirmation/cancel mutation paths. Preserve this invariant for every future broker mutation endpoint.

### Commit `6cb6afcfc5f34cf70afbad0d0791650526f9920a`

Theme: WebSocket subscription state and reconnect recovery.

Relevant upstream behavior:

- subscription transitions are atomic;
- desired subscriptions survive send failures and socket replacement;
- acknowledgement state resets before reconnect replay;
- stale responses are correlated with the connection/request epoch.

Local relevance:

Our market-feed supervisor reconnects after stream failure, but the Alpaca stream implementation should be reviewed for explicit desired-versus-acknowledged subscription state and reconnect epoch semantics. This matters most if subscriptions become dynamic or provider control frames arrive late.

Decision: evaluate with local failure-injection tests before changing implementation.

### Commit `13a7f7010373db0695c18675b4d8866907b22e8c`

Observed: 2026-08-25 12:41 UTC.
Theme: rate-limit coordination and order-state preservation.

Relevant upstream behavior:

- coordinate transport/IP and account/route quotas rather than treating each request path independently;
- perform rate-limit waits before request signing so pacing delay does not consume signed-request validity;
- incorporate venue-reported limits into local pacing state;
- preserve order state across rate-limit rejects, retries, and reconnects rather than treating pacing as permission to recreate a mutation.

Local relevance:

The current Alpaca and IBKR adapters do not use short-lived per-request signatures equivalent to Bybit, so the sign-after-wait detail does not justify a local production change. More importantly, the repository already classifies HTTP 429 mutation outcomes as `UNKNOWN` and requires reconciliation before retry, which protects the duplicate-order boundary this upstream fix reinforces.

For future broker adapters or any explicit mutation pacing layer, rate limiting must remain subordinate to idempotency and reconciliation: pacing may delay a not-yet-sent request, but it must never reinterpret an ambiguous sent request as safe to recreate. If a future provider uses expiring request signatures, signing must happen only after pacing waits complete.

License/provenance decision: conceptual reuse only. The upstream implementation is LGPL-3.0 and no source was copied.

Decision: record as a durable execution-integration invariant; no local code change without a failing test demonstrating a provider-specific gap.

### Commit `ca696f9737df700246bc0e598e494ca84855218b`

Theme: Interactive Brokers adaptive limit order parsing.

Local relevance:

Our IBKR adapter currently focuses on submit/cOID/reply confirmation/cancel/status. Adaptive order support is not yet a project requirement. Track the change but do not add order-type breadth without a concrete strategy/execution need.

Decision: monitor only.

## Alpaca Python SDK

Repository: `alpacahq/alpaca-py`
License: Apache-2.0

### Commit `8b4663966bb52f19c9dc64e15b8e4a44f3a62f62`

Theme: streaming reconnect reliability.

Relevant upstream behavior:

- exponential reconnect backoff with jitter to reduce reconnect storms/HTTP 429 risk;
- close half-open sockets on connect/auth failure before retry;
- optional data-level timeout for connected-but-mute streams;
- keep data timeout disabled by default because quiet subscriptions can be valid;
- distinguish market-data frames from control frames.

Local relevance:

Our outer market-feed supervisor already performs bounded exponential backoff, but currently uses deterministic delays. The local Alpaca feed should be reviewed for half-open socket cleanup and whether equal-jitter backoff would reduce synchronized reconnect risk without harming deterministic tests. A data-level silence timeout must remain opt-in and must be calibrated to the subscription cadence to avoid false positives.

Decision: create local failure-injection tests for cleanup first. Adopt jitter or silence detection only if a concrete local operational gap remains. Do not copy SDK code blindly.

## QuantConnect LEAN

Repository: `QuantConnect/Lean`
License: Apache-2.0

### Commit `78232af205e78efda4d977d1534d0c037c8393c5`

Theme: live-data continuity when expected universe files are temporarily unavailable.

Relevant upstream behavior:

- defer reads closer to the point of need;
- use a known backup source when the expected live source is temporarily unavailable;
- keep fallback logic centralized rather than probing at multiple layers.

Local relevance:

Our project intentionally fails closed when live market/account truth is stale or missing. We should not adopt a generic backup-data fallback that could silently change provenance. The useful pattern is narrower: fallback is acceptable only when provenance, timestamp, source quality, and risk semantics remain explicit and the fallback cannot be mistaken for primary live truth.

Decision: retain fail-closed semantics; consider explicitly labeled backup/reference data only for monitor/research use, never as an invisible replacement for safety-critical live inputs.

### Commit `09e96f648be7c9b86fe907ecdc63594a18f20175`

Theme: prevent one shared bar from being counted twice in an indicator.

Local relevance:

This independently reinforces our completed-cycle/revision design: an updated or shared observation must not silently create a second trading decision. Existing revision/checkpoint tests already cover the local invariant.

Decision: no code change required; keep as supporting external evidence.

## Integration queue created by this scan

Priority order:

1. Review Alpaca WebSocket connection lifecycle for half-open cleanup and reconnect jitter.
2. Add dynamic-subscription epoch/acknowledgement machinery only if the project actually introduces runtime subscription changes; avoid premature complexity.
3. Keep backup market-data sources explicit and provenance-preserving; never let a fallback silently satisfy a live risk freshness requirement.
4. Continue applying definite-vs-ambiguous mutation classification to any future execution mutation endpoint.
5. For future broker pacing, coordinate provider-defined quota scopes without weakening idempotency/reconciliation; if request signatures expire, sign only after pacing waits finish.

## License decision

- NautilusTrader is LGPL-3.0: use concepts/patterns as references by default; avoid source copying unless a future adaptation is deliberately isolated and license obligations are satisfied.
- Alpaca Python SDK is Apache-2.0: source adaptation is possible with attribution/notice compliance, but conceptual/local reimplementation remains preferred when small.
- QuantConnect LEAN is Apache-2.0: source adaptation is possible with attribution/notice compliance, but local behavior tests remain mandatory.

## Provenance rule

Any future implementation derived from the items above must cite this scan or a more specific ADR/integration note and must include a local RED/GREEN verification trail. Upstream success is evidence, not a substitute for local correctness.
