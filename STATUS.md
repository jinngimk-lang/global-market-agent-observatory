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
- Idempotent client-order identifiers and completed-cycle checkpoints prevent duplicate decisions/orders.
- Alpaca submit/cancel and IBKR submit/confirmation/cancel classify HTTP 408/429 as ambiguous `UNKNOWN`, not definite rejection.
- Unknown execution outcomes reconcile before retry; feed/cycle failures can HALT capital while process recovery continues.
- IBKR reconciliation now checks open orders first, then recent execution history when an order has disappeared from the open-order view, then confirms authoritative terminal state via the order-status endpoint. Trade history is a recovery locator, never proof of a full fill.
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
- Runtime never self-modifies strategy code/parameters or automatically skips promotion stages.

## Latest verification baseline

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

The status-only commit that records this baseline must itself remain CI-clean before becoming the next exact-head baseline.

## Ecosystem intelligence state

Canonical scan: `docs/upstream/2026-08-25-ecosystem-scan.md`.
IBKR follow-up: `docs/upstream/2026-08-25-ibkr-disconnect-fill-recovery.md`.

Current evidence queue:

1. QuantConnect IBKR issue #249 — local analogous open-order blind spot addressed with official IBKR trade-history + terminal-status recovery; continue auditing reconnect/recovery semantics.
2. NautilusTrader `d2b1221...` — ambiguous transport outcome classification; current 408/429 broker mutation gaps are closed, preserve invariant for future mutations.
3. NautilusTrader `6cb6afc...` — connection epoch / desired-vs-acknowledged subscription recovery; adopt only if local failure injection proves a gap.
4. Alpaca Python SDK `8b466396...` — reconnect jitter, half-open cleanup, optional silence timeout, control/data frame separation. Half-open/auth cleanup is covered locally; jitter/silence behavior remains evidence-gated.
5. QuantConnect LEAN `78232af...` — backup live data pattern; no invisible fallback may satisfy safety-critical live freshness.
6. QuantConnect LEAN `09e96f...` — duplicate shared-bar correctness independently supports the existing revision/completed-cycle invariant.

No external repository is integrated merely because it is new or popular. Every external adaptation must retain provenance/license review and local RED/GREEN evidence.

## Immediate engineering queue

1. Preserve exact-head CI on the current branch after this status update.
2. Continue Alpaca WebSocket resilience review: bounded jitter and cadence-aware connected-but-mute detection only when local failure injection justifies change.
3. Extend OOS evidence with realistic slippage/latency/cost modeling and regime-aware diagnostics without retroactive labeling.
4. Verify real NVDA/SPCX/KLAC coverage in monitor-only/paper-safe Alpaca configuration when runtime credentials are available outside Git.
5. Evaluate FINRA/off-exchange evidence with explicit source, reporting-latency, classification, and provenance methodology.
6. Keep auditing broker mutation/recovery endpoints for definite-vs-ambiguous outcomes and post-disconnect execution recovery.
7. Keep PR #8 Draft until strategy evidence and operational readiness justify otherwise.

## Known blockers / intentionally unfinished

- No current strategy is approved for autonomous live capital.
- Real broker credentials are never stored in Git.
- Real Alpaca end-to-end NVDA/SPCX/KLAC runtime evidence has not been produced from this execution environment.
- Dark-pool/off-exchange evidence is not yet integrated.
- Walk-forward/OOS evidence is still insufficient for live promotion.
- Alpaca reconnect jitter/connected-but-mute behavior has not yet been justified for production change.

## Future-agent rule

Do not interpret “live execution supported” as “safe for live capital”. Continue improving autonomously, but only changes that reduce uncertainty and survive local evidence, provenance, and exact-head CI belong in the system.
