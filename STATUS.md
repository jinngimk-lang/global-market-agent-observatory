# Global Market Autonomous Trading Platform — Status

Updated: 2026-08-28
Branch: `feature/autonomous-live-trading-platform`
Draft PR: `#8`

## Recovery order

When resuming after context pressure, a new session, an agent handoff, or uncertainty about prior decisions, read in this order:

1. `PROJECT_DIRECTION.md` — durable product direction and safety invariants.
2. `STATUS.md` — current branch/workstream state, completed work, blockers, and immediate next steps.
3. `AGENTS.md` — repository operating rules.
4. `docs/AUTONOMOUS_OWNER_GOVERNANCE.md` — autonomous project-owner authority and ecosystem-intelligence intake gate.
5. `docs/INNOVATION_DOCTRINE.md` when changing strategy, architecture, integration, safety, or durable workflow.
6. `CONTEXT.md` plus the newest relevant ADR/spec/plan/decision/upstream record.
7. Current branch, PR/CI evidence, and latest materially relevant upstream/provider changes.

Do not ask the user to repeat durable direction already recorded in the repository.

## Current operating model

Primary runtime chain:

`market data -> market structure -> strategy hypothesis/signal -> portfolio allocation -> deterministic risk -> execution -> reconciliation -> audit -> continuous evaluation/promotion`

Permanent maintenance chain:

`ecosystem discovery -> verification -> license/security review -> smallest useful integration -> RED/GREEN -> full CI -> provenance -> direction/status update`

Core rule: **processes recover where safe; capital permission fails closed.** Repository autonomy, broker capability, data quality, strategy maturity, strategy health, deterministic risk, operator state, and live-capital permission are separate gates.

`Trading Ecosystem Watch` uses delta-based public/official research and may integrate normal reversible improvements without repeated user approval, but no skill/MCP/upstream project can bypass deterministic risk, promotion evidence, reconciliation, secret boundaries, or explicit live enablement.

## Completed runtime capabilities

### Execution and safety

- Explicit `replay`, `paper`, `broker-paper`, and `live` modes; live remains OFF by default.
- Execution providers: local paper, Alpaca, IBKR.
- Deterministic risk approval is mandatory before every execution path.
- ACTIVE / REDUCING / HALTED state persists across restart.
- Strict non-reversing exposure reductions remain executable through drawdown, realized-loss, order-notional, symbol/gross exposure, and cash-style bounds whose purpose is to prevent creation or enlargement of exposure; HALTED, stale market/account state, allowlists, quantity/reference validation, and reversal rejection remain fail-closed.
- Idempotent client-order identifiers and completed-cycle checkpoints prevent duplicate decisions/orders.
- Alpaca submit/cancel and IBKR submit/confirmation/cancel classify HTTP 408/429 as ambiguous `UNKNOWN`, not definite rejection.
- Unknown execution outcomes reconcile before retry; if reconciliation is absent or itself remains `UNKNOWN`, capital transitions to HALTED rather than allowing unresolved broker truth to coexist with ACTIVE state.
- Feed/cycle failures can HALT capital while process recovery continues.
- IBKR account observation exhausts the provider's paginated position endpoint until an empty terminal page before constructing portfolio/risk truth; HTTP failures, malformed pages, or partial coverage are not reinterpreted as a flat account.
- IBKR reconciliation checks open orders first, then the full provider-supported seven-day execution-history window when an order has disappeared from the open-order view, then confirms authoritative terminal state via the order-status endpoint. Trade history is a recovery locator, never proof of a full fill, and finite provider history is not treated as globally complete.
- Alpaca reconciliation lookup binds successful REST evidence to the exact queried client-order id; contradictory or missing response identity returns `UNKNOWN` and cannot import an unrelated fill into local order truth.
- Append-only audit records strategy, risk, execution, reconciliation, and kill-switch transitions.

### Operator controls

- Dedicated `OPERATOR_API_TOKEN`, separate from broker credentials.
- Authenticated `/api/operator/halt` and `/api/operator/activate`.
- Missing/wrong authentication fails closed.
- HALT persists and is audited.
- ACTIVATE cannot bypass promotion or degraded strategy-health gates.

### Market data and structure

- Alpaca multi-symbol stock minute bars plus deterministic replay.
- Revised bars update history without creating duplicate trading decisions.
- Market-feed reconnect supervisor uses bounded exponential backoff and exposes failure state.
- Browser stream separates transport/JSON errors from rendering errors and ignores stale out-of-order bars.
- `/api/market/coverage` separates raw feed FRESH/STALE/MISSING from strategy-cycle OBSERVED/WAITING/ERROR.
- VWAP / anchored VWAP, volume profile, order-flow imbalance.
- Options OI + snapshot Greeks/IV with transparent GEX proxy, gamma flip, put/call wall estimates and methodology/provenance.
- Options structure has TTL/freshness invalidation.
- `TradingCycleResult` and `/api/market/structure` expose the exact structure consumed by strategy logic rather than recomputing a different view.

### Strategy evidence and promotion

- Versioned hypothesis manifests and maturity path `idea -> research -> replay -> paper -> broker-paper -> live`.
- Runtime promotion validates exact strategy/version evidence and fails closed on missing or mismatched evidence.
- Continuous learning settles observations only after future prices arrive and includes configured transaction costs.
- Prospective walk-forward calibration/holdout/fold assignment is fixed before outcomes are known; historical unassigned observations cannot be relabeled as OOS.
- OOS thresholds are shared by evidence generation and promotion policy.
- Strategy observations prospectively lock market regime from the exact strategy-used structure before outcome settlement; current regime key combines gamma sign with VWAP location.
- Health exposes per-symbol and per-regime sample count, expectancy, win rate, and drawdown.
- Regime-local degradation remains attribution evidence and does not silently become a global kill condition.
- Held-out OOS regime attribution uses only holdout observations from completed walk-forward folds. Calibration observations, historical `UNASSIGNED` observations, and incomplete folds cannot contaminate OOS regime metrics.
- Each OOS regime independently reports holdout sample count, completed folds, expectancy, drawdown, win rate, and `verified`; global OOS sufficiency does not imply per-regime sufficiency.
- Strategy observations distinguish signal/reference entry price from evaluated entry price and preserve execution-friction provenance.
- A strategy observation upgrades its entry source to `observed-fill` only when a `FILLED` execution matches an allocation for the same strategy/version/symbol/action/generated-at identity and exact client-order ID. Unrelated fills cannot contaminate the observation.
- When no verified fill exists, configured entry/exit slippage remains explicitly `modeled`; default modeled entry/exit slippage is zero rather than an invented market-wide constant.
- Observed fills record actual entry slippage and signal-to-fill observation latency; an observed entry does not also pay modeled entry slippage a second time.
- Exit evaluation is still fixed-horizon mark-to-market with explicitly modeled exit slippage; it is not represented as an observed broker exit.
- Strategy health exposes execution-friction attribution: observed-vs-modeled entry counts, observed-fill rate, mean observed entry slippage, mean signal-to-fill latency, and the current modeled transaction-cost/entry/exit assumptions.
- The Trading Console renders this attribution separately from symbol health. With no verified fills it displays `NO OBSERVED FILLS` and leaves actual slippage/latency unknown instead of manufacturing numbers.
- Broker-paper total observations and verified broker-paper fills are separate persisted promotion evidence fields. Verified fill depth is counted only from closed `BROKER_PAPER` observations whose entry source is an exact matched `observed-fill`.
- LIVE promotion requires both sufficient broker-paper observation depth and sufficient verified broker-paper fill depth. Legacy broker-paper counts default to zero verified fills and are never retroactively relabeled.
- Runtime never self-modifies strategy code/parameters or automatically skips promotion stages.

## Latest verification baseline

### IBKR paginated position completeness

- External trigger: NautilusTrader commit `1308d94dfc00ac46de5fd33ffa476d2bed46ef75` on 2026-08-27 fixed reconciliation paths where unavailable/partial bulk position coverage could be misread as affirmative flat-position evidence. NautilusTrader is LGPL-3.0; no source was copied.
- Official IBKR Trading Web API documents `GET /portfolio/{accountId}/positions/{pageId}` as the paginated account-position endpoint.
- Local audit found `IBKRObserver` requested only `positions/0` and promoted that first page into authoritative portfolio/risk state, silently omitting any later position pages.
- RED commit `eb74cacd0b2263fc1938e2e17b274c12f9df56c4`, CI `#618`: Ruff passed and Python 3.12 full pytest failed on the new multi-page contract, proving the observer stopped after page 0.
- Test-fixture follow-up `31f8be0cdca3a2b96320c0b1950661403e1f3a61` models an explicit empty terminal page for the pre-existing single-page case.
- GREEN commit `2c8057e45bcb9f6dd258e90731be5961ac3c7761` walks page IDs until an empty terminal page and fails before producing account truth if a page is HTTP-failing, non-list, or contains invalid items.
- GREEN CI `#622` completed successfully.
- Provenance: `docs/upstream/2026-08-28-ibkr-position-pagination.md`.

### Unknown execution outcome remains fail-closed through reconciliation

- External trigger: NautilusTrader commit `f2b2addb99527e3c9465573a596284f47b9edf10` on 2026-08-27 retained Kraken Spot request correlation after timeouts until definitive evidence or shutdown. NautilusTrader is LGPL-3.0; no source was copied.
- Local audit found that `ExecutionController` reconciled an ambiguous submit but only HALTED when lookup returned `None`; a lookup result whose status remained `UNKNOWN` left capital ACTIVE.
- RED commit `12895075a5d07debcb147244ff6c0ad8beba0a10`, CI `#605`: Ruff and Docker passed, while Python 3.13 full pytest failed on the new contract proving `UNKNOWN -> UNKNOWN` did not HALT.
- GREEN commit `c2870a1687a31d66eaf102b3ad44703848c96b4a`: after an ambiguous submit, a definite reconciliation result is accepted, while absent or still-UNKNOWN broker truth transitions the controller to HALTED.
- GREEN CI `#608` completed successfully on Python 3.12/3.13 with Ruff, full pytest, compileall, engineering-skill verification, and Docker build.
- Provenance: `docs/upstream/2026-08-27-unknown-outcome-reconciliation-halt.md`.

### IBKR trade-history retention completeness

- External trigger: NautilusTrader commit `5a2d9801eac2133689c555441f6b4bd6e8e634ba` on 2026-08-27 fixed Binance Futures reconciliation that treated history outside the venue-retained execution window as complete. NautilusTrader is LGPL-3.0; no source was copied.
- Official IBKR Trading Web API documentation states `GET /iserver/account/trades` can return up to seven prior days through `days=7`.
- Local RED commit `9b33efee2a5c9b570cfb990ff67f82ac7facffcd`, CI `#594`: Ruff passed and full pytest failed exactly at the requested-window contract; Python 3.12 reported `1 failed, 266 passed`, observing `days=1` instead of `days=7`.
- GREEN implementation commits `c512b6c08f8b8c7219e6c3c4444404040a4f7f27`, `33c91ae108f812fb2d69e246ebdfff194bc361d1`, and `1aa32b1c3e2cd7594dbf774694fef85713c8ffc0` route production IBKR construction through a retention-aware adapter that requests the full supported window while preserving order-status authority for terminal truth.
- Code/provenance exact-head CI `#602` on `951ddd74590420936ba47306074d6771e33b24db` completed successfully: Python 3.12/3.13, Ruff, full pytest, compileall, engineering-skill verification, and Docker build all passed.
- Provenance: `docs/upstream/2026-08-27-ibkr-trade-history-retention.md`.

### Risk-reducing exits versus new-risk bounds

- External trigger: NautilusTrader commit `8aa30f9acad6c623eca9a1489e3a4cd4c955f66f` on 2026-08-26 fixed whole-position exits being denied by placeholder/new-risk bounds. NautilusTrader is LGPL-3.0; no source was copied.
- Local RED commit `bfa54a568b3bb30d00e62b8499fc912bd1d85225`, CI `#580`: Python 3.13 produced exactly `2 failed, 264 passed`, proving a full reduction could be blocked first by drawdown lockout and separately by order-notional lockout.
- GREEN commit `022de44c2507cac08c7f083177c48f01f5d902a8` defines a verified reduction as a fresh known non-zero position projected to a strictly smaller absolute quantity without reversal. Only new-risk bounds are bypassed; HALTED/freshness/identity/validation gates remain intact.
- GREEN CI `#582` completed successfully on Python 3.12 and 3.13 with Ruff, full pytest, compileall, engineering-skill verification, and Docker build.
- Provenance: `docs/upstream/2026-08-26-reducing-risk-bounds.md`.

### IBKR disconnect-fill recovery

External trigger: QuantConnect `Lean.Brokerages.InteractiveBrokers#249` (opened 2026-08-04) describes fills that can be missed across IBKR 1100 disconnect windows unless execution history is explicitly recovered. QuantConnect repository license is Apache-2.0; no source was copied.

Local evidence:

- RED commit `f2133487bc6f0d2487ead646550120064b6d541f`, CI `#458`: Ruff passed; full pytest produced exactly `1 failed, 228 passed`, proving the adapter stopped at the open-order view.
- Test strengthened at `0459b6be1cfc3d4bab3475242af50245a079cb08` to require terminal order-status truth after trade-history identification.
- GREEN implementation `06d809259fba3cf9d0b4fdcf6f5f493534cbba56` adds open-order -> trade-history -> order-status recovery with fail-closed UNKNOWN behavior on ambiguity.
- Provenance: `docs/upstream/2026-08-25-ibkr-disconnect-fill-recovery.md`.

### Prospective and OOS regime attribution

- Prospective regime model commit `83784fbedb2f2183de359ac647850ef75098c9bb`.
- Prospective regime service commit `56d702ed29975ee16275cc46f11e9bda9865bc42`.
- OOS regime RED commit `b2fe194c0444bf009bd9c82ae39faa1affeb0c3d` requires only held-out observations from completed folds and independent per-regime evidence sufficiency.
- OOS model commit `38aa571033c4772707659c57305a0bc40f3124d2`.
- OOS service commit `042228bafc3f6cba916b483ae9f763400e65a731`.
- Exact-head CI `#478` on `042228bafc3f6cba916b483ae9f763400e65a731` completed successfully: Ruff, full pytest, compileall, engineering-skill verification on Python 3.12 and 3.13, plus Docker build all passed.

### Execution-friction provenance and Trading Console

- Execution-friction observations distinguish modeled entries from exact matched observed fills and record observed entry slippage plus signal-to-fill latency.
- Settings/runtime wiring exposes `STRATEGY_MODELED_ENTRY_SLIPPAGE_BPS` and `STRATEGY_MODELED_EXIT_SLIPPAGE_BPS`, both defaulting to `0`; configured transaction cost remains separately explicit.
- Unmatched client-order IDs are ignored for observed-fill attribution.
- Strategy-health aggregation separates historical observed execution evidence from current modeled friction assumptions.
- UI RED commit `34c7d77dab76cf467fef2ca0c535b1ec925a6929`, CI `#506`: Docker passed and full pytest failed exactly at the missing execution-friction dashboard contract (`2 failed, 237 passed`).
- Trading Console container commit `6dd56400fd54f6d780a615dc2e8a72d547c3f605` and renderer commit `b9162c6dc9137a33334feed89179d756c4a312f8` expose observed-fill coverage, actual entry slippage/latency, and modeled cost/entry/exit assumptions without adding any write endpoint.
- Exact-head CI `#510` on `b9162c6dc9137a33334feed89179d756c4a312f8` completed successfully: Ruff, full pytest, compileall, engineering-skill verification on Python 3.12 and 3.13, plus Docker build all passed.

### Verified broker-paper fill gate for LIVE promotion

- Promotion RED commit `72e3f3c5a429365e73013766e9aa603f3e505abf`, CI `#514`: full pytest produced exactly `1 failed, 239 passed`; the failure demonstrated that `broker_paper_observations=50` with zero verified fills was incorrectly accepted for LIVE promotion.
- Learning-sync RED commit `5d5e0b1db834bf47e104c730a317679fbc603110`, CI `#516`: full pytest produced exactly `2 failed, 239 passed`, proving both the missing verified-fill evidence field and missing broker-paper exact-fill synchronization.
- Evidence model commit `e7187ffee5f433c7ab8fbaceea5145a04452f503` adds a separate non-negative `verified_broker_paper_fill_observations` field.
- LIVE gate commit `39b64d274d8d034bc732e978941e78c29183da7b` requires verified broker-paper fill depth to meet the configured broker-paper minimum in addition to total broker-paper observations.
- Learning sync commit `3c1846a55e2069cf0ac7d5040a13f8ee22880184` counts verified depth only from closed `BROKER_PAPER` observations with exact matched `observed-fill` entry provenance.
- CI `#522` on `3c1846a55e2069cf0ac7d5040a13f8ee22880184` completed successfully: Ruff, full pytest, compileall, engineering-skill verification on Python 3.12 and 3.13, plus Docker build all passed.
- `PROJECT_DIRECTION.md` makes the distinction durable policy: broker-paper mode/count alone cannot satisfy LIVE validation, and historical evidence cannot be retroactively relabeled as verified broker execution.

### Reconciliation evidence binding

- External trigger: NautilusTrader commit `ccc80cdb2d5ba6520152e4a3df544715d2143772` on 2026-08-26 tightened REST reconciliation authority by binding reports to requested account/instrument/order scope. NautilusTrader is LGPL-3.0; no source was copied.
- Local audit found IBKR already scopes recovered trade history by exact `order_ref` and configured account, but Alpaca `by_client_order_id` accepted a successful response body without verifying the returned client-order identity.
- RED commit `b0783d90e2b85cc9b83298a51d802c438fccca2b`, CI `#532`: Ruff passed and full pytest produced exactly `1 failed, 241 passed`; an unrelated response marked `FILLED` was incorrectly accepted as the queried order.
- GREEN commit `ec6054e71aa43583fead96ff0d0ce1ccbb50cfa9` validates exact client-order identity before accepting Alpaca lookup state. Contradictory/missing identity returns `UNKNOWN` with no unrelated fill quantity or price.
- GREEN CI `#534` completed successfully on Python 3.12 and 3.13 with Ruff, full pytest, compileall, engineering-skill verification, and Docker build.
- Provenance: `docs/upstream/2026-08-26-reconciliation-evidence-binding.md`.

The status-only commit that records this baseline must itself remain CI-clean before becoming the next exact-head baseline.

## Ecosystem intelligence state

Canonical scan: `docs/upstream/2026-08-25-ecosystem-scan.md`.
IBKR disconnect-fill follow-up: `docs/upstream/2026-08-25-ibkr-disconnect-fill-recovery.md`.
Reconciliation binding follow-up: `docs/upstream/2026-08-26-reconciliation-evidence-binding.md`.
Reducing-risk bounds follow-up: `docs/upstream/2026-08-26-reducing-risk-bounds.md`.
IBKR retention follow-up: `docs/upstream/2026-08-27-ibkr-trade-history-retention.md`.
Unknown-outcome halt follow-up: `docs/upstream/2026-08-27-unknown-outcome-reconciliation-halt.md`.
IBKR position-pagination follow-up: `docs/upstream/2026-08-28-ibkr-position-pagination.md`.

Current evidence queue:

1. NautilusTrader `1308d94...` — unavailable or partial bulk position coverage must not be treated as affirmative flat-position evidence. The analogous local IBKR first-page-only gap is closed by exhausting the provider's paginated position endpoint before constructing portfolio/risk truth.
2. NautilusTrader `f2b2add...` — request correlation must survive timeouts until definitive evidence or shutdown. The analogous local `UNKNOWN -> UNKNOWN` capital-state gap is closed; preserve the invariant that unresolved broker truth cannot coexist with ACTIVE capital permission.
3. NautilusTrader `5a2d980...` — finite broker history must never be represented as complete outside its provider-retained window. The local IBKR adapter now uses the official seven-day maximum instead of one day, while durable local identity/checkpoints remain necessary beyond provider retention.
4. NautilusTrader `8aa30f9...` — strict reducing-exit versus new-risk bounds; analogous local gap is closed with RED/GREEN evidence. Preserve the rule that only proven non-reversing reductions can bypass exposure-creation bounds, while stale/unknown account state and HALTED continue to fail closed.
5. QuantConnect IBKR issue #249 — local analogous open-order blind spot addressed with official IBKR trade-history + terminal-status recovery; continue auditing reconnect/recovery semantics.
6. NautilusTrader `d2b1221...` — ambiguous transport outcome classification; current 408/429 broker mutation gaps are closed, preserve invariant for future mutations.
7. NautilusTrader `6cb6afc...` — connection epoch / desired-vs-acknowledged subscription recovery; adopt only if local failure injection proves a gap.
8. NautilusTrader `ccc80cdb...` — reconciliation authority/evidence binding; analogous Alpaca lookup identity gap closed locally, and future broker recovery must bind evidence to the strongest available order/account/instrument identity before accepting terminal truth.
9. Alpaca Python SDK `8b466396...` — reconnect jitter, half-open cleanup, optional silence timeout, control/data frame separation. Half-open/auth cleanup is covered locally. A naive fixed silence timeout is not safe for stock bars across closed-market periods; connected-but-mute detection still needs session/provider-aware semantics before production adoption.
10. QuantConnect LEAN `78232af...` — backup live data pattern; no invisible fallback may satisfy safety-critical live freshness.
11. QuantConnect LEAN `09e96f...` — duplicate shared-bar correctness independently supports the existing revision/completed-cycle invariant.

No external repository is integrated merely because it is new or popular. Every external adaptation must retain provenance/license review and local RED/GREEN evidence.

## Immediate engineering queue

1. Preserve exact-head CI after the IBKR position-pagination code, provenance, and status updates.
2. Continue Alpaca WebSocket resilience review, but do not add a naive fixed stock-bar silence timeout that would misclassify market-closed periods; require session/provider-aware evidence first.
3. Collect real NVDA/SPCX/KLAC observed-fill and coverage evidence in monitor-only/paper-safe or broker-paper configuration when runtime credentials are available outside Git; verified broker-paper fills, not mode labels alone, are required for LIVE evidence depth.
4. Extend execution-friction evidence toward observed exit fills only when an auditable entry-to-exit execution identity exists; keep fixed-horizon exits explicitly modeled until then.
5. Evaluate FINRA/off-exchange evidence with explicit source, reporting-latency, classification, and provenance methodology.
6. Keep auditing broker mutation/recovery endpoints for definite-vs-ambiguous outcomes, evidence identity binding, finite-history completeness, paginated/partial position coverage, post-disconnect execution recovery, and any safety gate that could unintentionally prevent a proven reduction.
7. Keep PR #8 Draft until strategy evidence and operational readiness justify otherwise.

## Known blockers / intentionally unfinished

- No current strategy is approved for autonomous live capital.
- Real broker credentials are never stored in Git.
- Real Alpaca end-to-end NVDA/SPCX/KLAC runtime evidence has not been produced from this execution environment.
- Verified broker-paper fill depth is currently insufficient for LIVE promotion; legacy broker-paper counts do not satisfy the gate.
- Fixed-horizon exit evaluation remains modeled; no observed broker exit is claimed without an auditable entry-to-exit execution identity.
- Dark-pool/off-exchange evidence is not yet integrated.
- Walk-forward/OOS evidence is still insufficient for live promotion.
- Alpaca reconnect jitter/connected-but-mute behavior has not yet been justified for a safe production change.

## Future-agent rule

Do not interpret “live execution supported” as “safe for live capital”. Continue improving autonomously, but only changes that reduce uncertainty and survive local evidence, provenance, and exact-head CI belong in the system.