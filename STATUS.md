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

- `PROJECT_DIRECTION.md` is a living long-horizon compass and now includes autonomous project ownership plus permanent Continuous Ecosystem Intelligence / Phase 7.
- `docs/AUTONOMOUS_OWNER_GOVERNANCE.md` defines normal repository autonomy, direction stewardship, upstream intake, license/security/provenance requirements, skill/MCP/connector policy, and project-completeness rules.
- `AGENTS.md` now requires future agents to recover this governance and to inspect relevant upstream changes before material implementation work.
- Normal reversible evidence-backed repository decisions should be made autonomously without repeatedly asking the user.
- Repository autonomy does not grant permission to expose secrets, make paid purchases/legal commitments, perform irreversible external actions, disclose sensitive findings, bypass deterministic risk, promote strategy stages without evidence, or enable live capital merely because a broker/tool supports it.

## Trading/runtime capabilities completed

### Safety and execution

- Explicit `replay`, `paper`, `broker-paper`, and `live` modes.
- Execution providers: local paper, Alpaca, IBKR.
- Live execution requires explicit enablement/confirmation and remains OFF by default.
- Deterministic risk is mandatory before execution.
- ACTIVE / REDUCING / HALTED state is persisted across restart.
- Unknown execution outcomes reconcile before retry; ambiguous results are not treated as definite failures.
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
- The lifecycle-race regression test was corrected so health is changed after application startup; production semantics remain request-time health truth.

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

CI `#428` on commit `b6834ead3ea22cf05b6ffc64221cac0eaab98c24` completed successfully after the operator-control lifecycle test correction.

Verified by that run:

- Ruff;
- full pytest on Python 3.12;
- full pytest on Python 3.13;
- application compileall;
- required engineering-skill check;
- Docker build.

At the prior failed run, the only failure was `test_activation_is_blocked_while_strategy_health_is_degraded`: the test changed the health gate before `TestClient` startup and the continuous-improvement startup path legitimately recalculated it. The corrected test changes the simulated degraded health inside the active lifespan, then proves ACTIVATE returns 409. No production bypass was added.

The documentation/governance commits after CI #428 trigger a newer CI and must be verified before those commits are described as fully green.

## Ecosystem intelligence state

First governed ecosystem scan is recorded in `docs/upstream/2026-08-25-ecosystem-scan.md`.

Current upstream evidence queue:

1. **NautilusTrader `d2b1221...`** — classify transport outcomes before rolling back pending commands; preserve ambiguous state for reconciliation. Strongly aligned with our UNKNOWN-execution architecture. NautilusTrader is LGPL-3.0, so conceptual reuse is preferred unless a future isolated adaptation deliberately satisfies license obligations.
2. **NautilusTrader `6cb6afc...`** — atomic WebSocket subscription state, request/connection epoch correlation, desired-subscription replay on reconnect. Evaluate only if local failure-injection exposes a concrete gap.
3. **Alpaca Python SDK `8b466396...`** — reconnect jitter, half-open socket cleanup, optional connected-but-mute timeout, control-vs-market-frame separation. Alpaca SDK is Apache-2.0. Review our Alpaca feed with RED tests before adopting any behavior.
4. **QuantConnect LEAN `78232af...`** — backup live-universe source pattern. LEAN is Apache-2.0. We will not silently substitute backup data for safety-critical primary truth; any fallback must retain explicit provenance and fail-closed risk semantics.
5. **QuantConnect LEAN `09e96f...`** — duplicate shared-bar correctness fix independently supports our existing revision/completed-cycle invariant; no local change needed now.

An hourly condition-based ecosystem watch is configured externally to inspect relevant public GitHub/provider/security developments and remain silent when nothing material changes. Any integration still has to pass the repository intake gate and CI; monitoring does not mean uncontrolled mutation.

## Immediate engineering queue

Priority order is now:

1. Audit every Alpaca/IBKR execution command path for explicit definite-vs-ambiguous outcome classification before pending state is cleared or retry is possible.
2. Review Alpaca WebSocket connect/auth/reconnect lifecycle against the latest upstream reliability findings: half-open cleanup, jitter bounds, and opt-in silence detection; add local failure-injection tests before changing production behavior.
3. Expand prospective OOS/walk-forward evidence with regime segmentation, realistic costs/slippage/latency, and provenance without retroactive holdout labeling.
4. Add regime-level strategy attribution after the completed per-symbol attribution layer.
5. Verify real NVDA/SPCX/KLAC market coverage end-to-end in monitor-only/paper-safe Alpaca configuration when runtime credentials are available outside Git.
6. Evaluate FINRA/off-exchange evidence with source/reporting-latency/classification methodology before integration.
7. Keep PR #8 Draft until evidence and operational readiness justify a different state.

## Known blockers / intentionally unfinished

- No current strategy is approved for autonomous live capital.
- Real broker credentials are not stored in Git.
- Real Alpaca end-to-end NVDA/SPCX/KLAC runtime evidence has not been produced from this execution environment.
- Dark-pool/off-exchange evidence is not yet integrated.
- Walk-forward/OOS evidence is not sufficient for live promotion.
- Alpaca reconnect jitter/half-open cleanup has not yet been locally regression-tested against our implementation.
- Complete command-by-command ambiguous-outcome audit across both live broker adapters is still pending.

## Future-agent rule

Do not interpret “live execution supported” as “strategy safe for live capital”. Broker capability, market-data quality, strategy evidence, health, deterministic risk, operator state, and reconciliation are independent gates.

Keep improving the platform autonomously, but only integrations that reduce uncertainty and survive local evidence/CI belong in the system.
