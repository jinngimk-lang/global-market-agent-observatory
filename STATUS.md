# Global Market Autonomous Trading Platform — Status

Updated: 2026-08-25
Branch: `feature/autonomous-live-trading-platform`
Draft PR: `#8`

## Recovery order

When resuming after context pressure, a new session, an agent handoff, or uncertainty about prior decisions, read in this order:

1. `PROJECT_DIRECTION.md` — durable product direction and safety invariants.
2. `STATUS.md` — current branch/workstream state, completed work, blockers, and immediate next steps.
3. `AGENTS.md` — repository operating rules.
4. `docs/AUTONOMOUS_OWNER_GOVERNANCE.md` — autonomous project-owner authority and ecosystem-intelligence intake gate.
5. `docs/INNOVATION_DOCTRINE.md` — innovation/reframing method and strategy-promotion doctrine when relevant.
6. `CONTEXT.md` plus the newest relevant ADR/spec/plan/decision/upstream record.
7. Current branch, PR/CI evidence, and latest materially relevant upstream/provider changes.

Do not ask the user to repeat durable direction already recorded here.

## Current product state

This repository is the primary autonomous market-monitoring and trading platform workstream.

Primary runtime chain:

`market data -> market structure -> strategy hypothesis/signal -> portfolio allocation -> deterministic risk -> execution -> reconciliation -> audit -> continuous evaluation/promotion`

Permanent maintenance chain:

`ecosystem discovery -> verification -> license/security review -> smallest useful integration -> RED/GREEN -> full CI -> provenance -> direction/status update`

Core operating rule:

**Processes recover where safe; capital permission fails closed.** Runtime liveness, broker capability, strategy maturity, strategy health, and operator activation are independent gates.

## Governance now in force

- `PROJECT_DIRECTION.md` is a living long-horizon compass and includes autonomous project ownership plus permanent Continuous Ecosystem Intelligence / Phase 7.
- `docs/AUTONOMOUS_OWNER_GOVERNANCE.md` defines normal repository autonomy, direction stewardship, upstream intake, license/security/provenance requirements, skill/MCP/connector policy, and project-completeness rules.
- `AGENTS.md` requires future agents to recover this governance and inspect relevant upstream changes before material implementation work.
- Normal reversible evidence-backed repository decisions should be made autonomously without repeatedly asking the user.
- Repository autonomy does not grant permission to expose secrets, make paid purchases/legal commitments, perform irreversible external actions, disclose sensitive findings, bypass deterministic risk, promote strategy stages without evidence, or enable live capital merely because a broker/tool supports it.
- `Trading Ecosystem Watch` runs as an hourly condition-based delta monitor and uses the same intake/test/provenance gate before any repository integration.

## Trading/runtime capabilities completed

### Safety and execution

- Explicit `replay`, `paper`, `broker-paper`, and `live` modes.
- Execution providers: local paper, Alpaca, IBKR.
- Live execution requires explicit enablement/confirmation and remains OFF by default.
- Deterministic risk is mandatory before execution.
- ACTIVE / REDUCING / HALTED state is persisted across restart.
- Unknown execution outcomes reconcile before retry; ambiguous results are not treated as definite failures.
- Alpaca submit/cancel and IBKR submit/confirmation/cancel now explicitly classify HTTP 408/429 as `UNKNOWN` mutation outcomes rather than definite `REJECTED` outcomes; transport errors and 5xx remain reconciliation-required UNKNOWN paths.
- Idempotent client-order identifiers and persistent completed-cycle checkpoints prevent duplicate decisions/orders.
- Feed/cycle failures can HALT capital permission while process recovery/reconnect continues.
- Append-only audit records strategy, risk, execution, reconciliation, and kill-switch transitions.

### Authenticated operator controls

- `OPERATOR_API_TOKEN` is a dedicated secret, independent of broker keys.
- `/api/operator/halt` and `/api/operator/activate` use Bearer authentication with constant-time token comparison.
- Missing operator token fails closed.
- HALT persists and is audited.
- ACTIVATE cannot promote a strategy or bypass promotion eligibility.
- ACTIVATE is rejected while the runtime strategy-health gate is degraded.
- The lifecycle-race regression test changes simulated health after application startup; production semantics remain request-time health truth.

### Market data and resilient loops

- Alpaca multi-symbol stock minute bars.
- Replay restart resumes from the last persisted candle rather than moving synthetic time backward.
- Updated/revised bars update history but do not create duplicate trade decisions.
- Market-feed reconnect supervisor uses bounded exponential backoff and records failure state.
- Browser stream separates JSON/transport errors from chart rendering errors and ignores old out-of-order candles per symbol+interval.
- Runtime loop liveness/failures are visible read-only.
- `/api/market/coverage` separates raw feed FRESH/STALE/MISSING from strategy-cycle OBSERVED/WAITING/ERROR.

### Market structure and options

- VWAP / anchored VWAP, volume profile, order-flow imbalance.
- Transparent GEX proxy, gamma flip, put-wall and call-wall estimates with explicit methodology/provenance.
- Alpaca option contract/open-interest data joins option snapshot Greeks/IV.
- Options structure has freshness/TTL semantics and invalidates stale/failed data.
- `TradingCycleResult` retains the exact structure used by the strategy.
- `/api/market/structure` exposes that exact strategy-used snapshot rather than recomputing a different view.
- Missing values remain missing; inferred values are not presented as direct fact.

### Strategy evidence and promotion

- Versioned hypothesis manifests and canonical maturity path: `idea -> research -> replay -> paper -> broker-paper -> live`.
- Runtime promotion gate validates exact strategy/version evidence and fails closed on missing/mismatched evidence.
- Continuous learning settles observations only after future prices arrive and applies configured transaction costs.
- Prospective walk-forward partitioning exists: calibration/holdout/fold assignment is fixed before outcomes are known; historical unassigned observations cannot be retrospectively relabeled as OOS.
- OOS holdout sample/fold thresholds are wired from `Settings` into both evidence generation and promotion policy.
- Strategy health includes per-symbol attribution with sample count, net expectancy, win rate, and drawdown.
- A sufficiently sampled degraded symbol can degrade overall strategy health; tiny symbol samples report attribution without automatically tripping the strategy.
- Health recovery does not automatically reactivate REDUCING/HALTED state.
- Runtime never self-modifies strategy code/parameters or automatically skips promotion stages.

### Trading Console

The old Observatory showcase has been removed from the main UI. The console focuses on:

- system/trading/promotion state;
- NVDA/SPCX/KLAC and current-feed symbol switching;
- per-symbol feed coverage and strategy-cycle state;
- exact strategy-used VWAP / OFI / Put Wall estimate / Call Wall estimate / Net GEX Proxy and freshness/provenance;
- strategy action/confidence/rationale/invalidation;
- allocation/risk/execution outcomes;
- positions/P&L and audit chain;
- strategy promotion and health;
- per-symbol strategy attribution;
- runtime-loop liveness.

A replay BTC chart is explicitly separated from US-equity coverage and is never presented as proof that NVDA/SPCX/KLAC are receiving live data.

## Latest verified CI

CI `#450` on commit `06737299996dfbc97df9fc588ff2277a45a4eec2` completed successfully after the broker mutation-outcome hardening.

Verified by that run:

- Ruff;
- full pytest on Python 3.12;
- full pytest on Python 3.13;
- application compileall;
- required engineering-skill check;
- Docker build.

The RED run immediately before the fix produced 10 targeted failures in `tests/test_broker_mutation_outcomes.py`: Alpaca submit/cancel and IBKR submit/confirmation/cancel treated HTTP 408/429 as `REJECTED`. The GREEN implementation routes those ambiguous mutation responses to provider-specific `UNKNOWN` results so reconciliation must establish broker truth before retry. No NautilusTrader source code was copied; the upstream LGPL project was used as conceptual evidence only.

## Ecosystem intelligence state

First governed ecosystem scan is recorded in `docs/upstream/2026-08-25-ecosystem-scan.md`.

Current upstream evidence queue:

1. **NautilusTrader `d2b1221...`** — transport-outcome classification pattern. The concrete local Alpaca/IBKR 408/429 mutation gap has now been closed and verified by CI #450. Continue applying the invariant to future broker mutation endpoints.
2. **NautilusTrader `6cb6afc...`** — atomic WebSocket subscription state, request/connection epoch correlation, desired-subscription replay on reconnect. Evaluate only if local failure-injection exposes a concrete gap.
3. **Alpaca Python SDK `8b466396...`** — reconnect jitter, half-open socket cleanup, optional connected-but-mute timeout, control-vs-market-frame separation. Alpaca SDK is Apache-2.0. Review our Alpaca feed with local failure-injection before adopting behavior.
4. **QuantConnect LEAN `78232af...`** — backup live-universe source pattern. LEAN is Apache-2.0. We will not silently substitute backup data for safety-critical primary truth; any fallback must retain explicit provenance and fail-closed risk semantics.
5. **QuantConnect LEAN `09e96f...`** — duplicate shared-bar correctness fix independently supports our existing revision/completed-cycle invariant; no local change needed now.

The hourly ecosystem watch remains silent when there is no material delta. Monitoring does not mean uncontrolled mutation: every integration still passes relevance, license/security, provenance, RED/GREEN, and exact-head CI gates.

## Immediate engineering queue

Priority order is now:

1. Review Alpaca WebSocket connect/auth/reconnect lifecycle against the latest upstream reliability findings: prove half-open cleanup behavior, evaluate bounded jitter, and keep any connected-but-mute timeout opt-in and cadence-aware. Add local failure-injection tests before changing production behavior.
2. Expand prospective OOS/walk-forward evidence with regime segmentation, realistic costs/slippage/latency, and provenance without retroactive holdout labeling.
3. Add regime-level strategy attribution after the completed per-symbol attribution layer.
4. Verify real NVDA/SPCX/KLAC market coverage end-to-end in monitor-only/paper-safe Alpaca configuration when runtime credentials are available outside Git.
5. Evaluate FINRA/off-exchange evidence with source/reporting-latency/classification methodology before integration.
6. Keep auditing any new broker mutation endpoint for definite-vs-ambiguous outcome semantics before it can clear pending state or retry.
7. Keep PR #8 Draft until evidence and operational readiness justify a different state.

## Known blockers / intentionally unfinished

- No current strategy is approved for autonomous live capital.
- Real broker credentials are not stored in Git.
- Real Alpaca end-to-end NVDA/SPCX/KLAC runtime evidence has not been produced from this execution environment.
- Dark-pool/off-exchange evidence is not yet integrated.
- Walk-forward/OOS evidence is not sufficient for live promotion.
- Alpaca reconnect jitter/half-open cleanup has not yet been locally regression-tested against our implementation.

## Future-agent rule

Do not interpret “live execution supported” as “strategy safe for live capital”. Broker capability, market-data quality, strategy evidence, health, deterministic risk, operator state, and reconciliation are independent gates.

Keep improving the platform autonomously, but only integrations that reduce uncertainty and survive local evidence/CI belong in the system.
