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
- Alpaca submit/cancel and IBKR submit/confirmation/cancel explicitly classify HTTP 408/429 as `UNKNOWN` mutation outcomes rather than definite `REJECTED` outcomes; transport errors and 5xx remain reconciliation-required UNKNOWN paths.
- IBKR client-order reconciliation now checks open orders first, then recent execution history when the order is no longer open, and finally verifies terminal broker state through the order-status endpoint before clearing ambiguity. Trade history is a recovery locator, not proof of a full fill.
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
- Strategy observations now lock a prospective market-regime label from the exact strategy-used structure before outcome settlement. Current regime key combines gamma sign with VWAP location.
- Strategy health includes per-symbol and per-regime attribution with sample count, net expectancy, win rate, and drawdown.
- A sufficiently sampled degraded symbol can degrade overall strategy health; regime-local degradation remains attribution evidence and does not silently become a global kill condition.
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

## Latest verification state

IBKR disconnect-fill recovery RED:

- commit `f2133487bc6f0d2487ead646550120064b6d541f`;
- CI `#458`;
- Ruff passed and full pytest reported exactly `1 failed, 228 passed` because the adapter stopped after the open-order query instead of consulting execution history.

The test was strengthened at `0459b6be1cfc3d4bab3475242af50245a079cb08` to require broker terminal-order status after trade-history identification, preventing a partial execution from being mislabeled as a full fill.

IBKR GREEN implementation:

- commit `06d809259fba3cf9d0b4fdcf6f5f493534cbba56`;
- exact-head CI `#464` confirmed the IBKR recovery regression no longer failed; that run was blocked only by two independent regime-attribution RED tests already present in the branch.

Regime-attribution GREEN:

- model commit `83784fbedb2f2183de359ac647850ef75098c9bb`;
- service commit `56d702ed29975ee16275cc46f11e9bda9865bc42`;
- CI `#468` passed Ruff, full pytest, compileall, and engineering-skill verification on both Python 3.12 and 3.13. Docker was still completing when this status update was written.

Provenance for the IBKR recovery change is recorded in `docs/upstream/2026-08-25-ibkr-disconnect-fill-recovery.md`. The final head after this status/provenance update must pass the complete CI, including Docker, before it is treated as the new verified baseline.

## Ecosystem intelligence state

The governed ecosystem scan is recorded in `docs/upstream/2026-08-25-ecosystem-scan.md`; the IBKR disconnect-fill recovery follow-up is recorded separately in `docs/upstream/2026-08-25-ibkr-disconnect-fill-recovery.md`.

Current upstream evidence queue:

1. **QuantConnect Interactive Brokers issue #249 (2026-08-04)** — reports fill events that can be missed across IBKR 1100 disconnect windows without explicit execution-history recovery. The local Client Portal adapter now addresses the analogous open-order blind spot by using official IBKR trade history to recover broker order identity and the official order-status endpoint to verify terminal truth. QuantConnect's repository is Apache-2.0; no source code was copied.
2. **NautilusTrader `d2b1221...`** — transport-outcome classification pattern. The concrete local Alpaca/IBKR 408/429 mutation gap is closed. Continue applying the invariant to future broker mutation endpoints.
3. **NautilusTrader `6cb6afc...`** — atomic WebSocket subscription state, request/connection epoch correlation, desired-subscription replay on reconnect. Evaluate only if local failure-injection exposes a concrete gap.
4. **Alpaca Python SDK `8b466396...`** — reconnect jitter, half-open socket cleanup, optional connected-but-mute timeout, control-vs-market-frame separation. The local half-open/auth-failure cleanup regression has already been added; continue evaluating bounded jitter and cadence-aware silence handling only when justified by a local failure.
5. **QuantConnect LEAN `78232af...`** — backup live-universe source pattern. We will not silently substitute backup data for safety-critical primary truth; any fallback must retain explicit provenance and fail-closed risk semantics.
6. **QuantConnect LEAN `09e96f...`** — duplicate shared-bar correctness fix independently supports the existing revision/completed-cycle invariant; no local change needed.

The ecosystem watch remains silent when there is no material delta. Monitoring does not mean uncontrolled mutation: every integration still passes relevance, license/security, provenance, RED/GREEN, and exact-head CI gates.

## Immediate engineering queue

Priority order is now:

1. Complete and preserve exact-head CI after the IBKR recovery + regime-attribution + provenance/status changes.
2. Continue Alpaca WebSocket resilience review: bounded reconnect jitter and cadence-aware connected-but-mute detection only if local failure injection proves a gap.
3. Expand prospective OOS/walk-forward evidence with realistic costs/slippage/latency and stronger regime segmentation without retroactive holdout labeling.
4. Verify real NVDA/SPCX/KLAC market coverage end-to-end in monitor-only/paper-safe Alpaca configuration when runtime credentials are available outside Git.
5. Evaluate FINRA/off-exchange evidence with source/reporting-latency/classification methodology before integration.
6. Keep auditing every new broker mutation/recovery endpoint for definite-vs-ambiguous outcome semantics and post-disconnect execution recovery before pending state can clear or retry.
7. Keep PR #8 Draft until evidence and operational readiness justify a different state.

## Known blockers / intentionally unfinished

- No current strategy is approved for autonomous live capital.
- Real broker credentials are not stored in Git.
- Real Alpaca end-to-end NVDA/SPCX/KLAC runtime evidence has not been produced from this execution environment.
- Dark-pool/off-exchange evidence is not yet integrated.
- Walk-forward/OOS evidence is not sufficient for live promotion.
- Alpaca reconnect jitter/connected-but-mute behavior has not yet been locally justified for production change.

## Future-agent rule

Do not interpret “live execution supported” as “strategy safe for live capital”. Broker capability, market-data quality, strategy evidence, health, deterministic risk, operator state, and reconciliation are independent gates.

Keep improving the platform autonomously, but only integrations that reduce uncertainty and survive local evidence/CI belong in the system.
