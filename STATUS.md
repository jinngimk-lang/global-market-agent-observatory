# Global Market Autonomous Trading Platform — Status

Updated: 2026-08-21
Branch: `feature/autonomous-live-trading-platform`
Draft PR: `#8`

## Recovery order

When resuming after context pressure, a new session, an agent handoff, or uncertainty about prior decisions, read in this order:

1. `PROJECT_DIRECTION.md` — durable product direction and safety invariants.
2. `STATUS.md` — current execution state, completed work, blockers, and next steps.
3. `AGENTS.md` — repository operating rules.
4. `docs/INNOVATION_DOCTRINE.md` — innovation/reframing method and strategy promotion doctrine.
5. newest relevant spec/plan/decision record.
6. current branch diff, PR/CI state, and live evidence.

Do not ask the user to repeat durable direction already recorded in these files.

## Current product state

The repository is being converted from a read-only observatory into the primary autonomous market-monitoring and trading platform.

The intended runtime chain is:

`market data -> market structure -> strategy hypothesis/signal -> portfolio allocation -> deterministic risk -> execution -> reconciliation -> audit -> evaluation/promotion`

Live execution is a first-class capability but remains disabled by default and must fail closed.

A second independent gate now exists: **broker execution capability does not imply strategy execution eligibility**. Strategies must be promoted for the selected runtime mode using persisted evidence for the exact strategy version.

## Completed on this branch

### Direction and recovery

- Added `PROJECT_DIRECTION.md` as the long-horizon project compass.
- Added `STATUS.md` as the short-horizon execution checkpoint.
- Updated `AGENTS.md` with mandatory recovery order, live-trading safety rules, innovation doctrine, and strategy-promotion rules.
- Added `docs/INNOVATION_DOCTRINE.md`.
- Added `docs/decisions/0001-constraint-deletion-strategy-promotion.md`.
- Opened draft PR `#8` to force full CI/container verification before merge.

### Trading modes and execution boundary

- Added explicit `replay`, `paper`, `broker-paper`, and `live` modes.
- Added explicit execution providers: local paper, Alpaca, IBKR.
- Added deliberate live-trading enable/confirmation gates; credentials alone cannot enable live execution.
- Added a common execution adapter contract.
- Added local paper execution through the same execution boundary used by broker modes.
- Added Alpaca order submission, client-order-id lookup, cancellation, status mapping, and unknown-result handling.
- Added IBKR execution with contract lookup, `cOID`, precautionary reply allowlisting, cancellation semantics, and unknown-result handling.

### Deterministic safety kernel

- Added active/reducing/halted trading states.
- Added stronger risk checks for symbol exposure, gross exposure, stale market data, stale account state, daily loss, and portfolio drawdown.
- Added idempotent client-order-id behavior.
- Added reconciliation-before-retry behavior for uncertain broker outcomes.
- Unknown execution state causes fail-closed HALT.
- Added persistent trading-state storage: HALT/REDUCING/ACTIVE survive process restart; corrupt/unknown persisted state fails closed to HALTED.
- Added persistent completed-cycle checkpoints so the same finished market observation is skipped after replay or process restart; UNKNOWN execution outcomes are intentionally not checkpointed.
- Added append-only audit events for signals, risk decisions, execution, reconciliation, system state, and kill-switch transitions.

### Market data and market structure

- Added Alpaca real-time multi-symbol minute-bar feed with authentication, subscriptions, and updated-bar handling.
- Added VWAP / anchored-VWAP primitives.
- Added volume-profile primitives.
- Added order-flow-imbalance primitives.
- Added transparent options/GEX proxy models with explicit sign assumptions.
- Added call-wall/put-wall estimation without pretending the proxy is known dealer inventory.

### Strategy and portfolio layers

- Added versioned strategy signals with confidence, rationale, invalidation, and timestamps.
- Added VWAP reclaim/rejection strategy.
- Added gamma-level strategy for put-wall support/breakdown and call-wall rejection/breakout with order-flow confirmation.
- Added portfolio allocation based on loss budget, invalidation distance, per-order caps, and correlated/group exposure.
- Cost basis is portfolio state only; it does not cause averaging down.

### Innovation / strategy promotion

- Added `StrategyHypothesis` manifests with:
  - problem;
  - category default;
  - deleted constraint;
  - new axis;
  - expected mechanism;
  - observable inputs;
  - provenance requirements;
  - falsification conditions;
  - failure regimes;
  - safety constraints;
  - exact strategy version and promotion stage.
- Added deterministic `StrategyPromotionGate` with canonical stages:
  `idea -> research -> replay -> paper -> broker-paper -> live`.
- Added persisted `PromotionEvidence` keyed by exact strategy id + version.
- Runtime strategy code version must match its manifest version.
- Missing manifest, missing evidence, version mismatch, or insufficient stage fails closed.
- `ApplicationState` now separates:
  - `AUTO_TRADING_ENABLED` requested by the operator;
  - promotion eligibility for the selected mode;
  - effective autonomous execution.
- `/api/health` and `/api/trading/status` expose promotion blockers read-only.
- Current VWAP and gamma-level strategies are explicitly at `replay` maturity; they cannot autonomously execute in `paper`, `broker-paper`, or `live` merely because broker connectivity exists.

### Autonomous loop

- Added an autonomous market-cycle engine that processes bars through strategy -> allocation -> risk -> execution -> audit.
- Monitoring mode can generate signals without sending orders.
- Market-data revisions are stored but do not trigger duplicate execution.
- Completed market cycles have persistent identities/checkpoints to prevent replay/restart duplicate processing.
- Main `ApplicationState` now builds the unified execution/orchestration/promotion architecture.
- Legacy unauthenticated `/api/orders` remains local-paper-only and must never become a live broker write path.

### Broker truth / reconciliation

- Added broker portfolio normalization so live risk can use broker cash/positions/equity rather than local guesses.
- Added daily account PnL support to broker snapshots.
- Live/broker modes treat missing critical broker state as invalid rather than silently substituting zero.

## Innovation-method application

The uploaded innovation skill is adapted as a trading-system method, not copied as branding logic.

Project translation:

- `reframe before optimize` -> challenge the trading-system premise before optimizing indicators/parameters.
- `category default` -> identify the assumption conventional trading systems optimize.
- `constraint deletion` -> ask whether that assumption can disappear entirely.
- `new axis` -> define the new measurable system property that becomes the edge.
- three-direction exploration -> compare incremental improvement, observable-market bridge, and premise deletion before implementation.
- creative review gate -> deterministic hypothesis/innovation review gate.
- persistent project protocol -> `PROJECT_DIRECTION.md` + `STATUS.md` + decision records + recovery order.

## Current strategy reframes

### VWAP v1.0.0

- Category default: use position relative to VWAP as a generic bullish/bearish indicator.
- Deleted constraint: every VWAP observation must predict direction.
- New axis: trade observable state transitions across VWAP with explicit invalidation and abstain otherwise.
- Current promotion stage: `replay`.
- Paper/broker-paper/live autonomous execution: blocked until version-specific evidence is persisted and promotion criteria pass.

### Gamma Levels v1.0.0

- Category default: treat call wall / put wall estimates as authoritative support or resistance.
- Deleted constraint: a wall estimate alone is sufficient evidence.
- New axis: wall interaction must be confirmed by observable flow while GEX methodology/sign assumptions remain explicit.
- Current promotion stage: `replay`.
- Paper/broker-paper/live autonomous execution: blocked until version-specific evidence is persisted and promotion criteria pass.

## Verification state

Draft PR `#8` is active.

CI run `#196` for code head `f68c8b4e3f9e6268a6aac145d634cde7bb5ed8dd` completed successfully on 2026-08-21.

Verified green:

- Ruff static checks;
- full pytest suite: **169 passed** on Python 3.12;
- full pytest suite: **169 passed** on Python 3.13;
- `compileall` on application code;
- required engineering skill file check;
- Docker container build.

This `STATUS.md` update is documentation-only after that verified code head. Keep PR #8 draft because product evidence/promotion work is intentionally incomplete, not because the current code fails CI.

## Immediate next steps

1. Integrate real options OI/Greeks data with provenance for GEX/call-wall/put-wall features.
2. Add replay/backtest evidence collection with transaction costs and out-of-sample metrics.
3. Feed those metrics into `PromotionEvidence` instead of manually asserting promotion.
4. Add strategy degradation/automatic-disable evidence and policies.
5. Add authenticated operator controls for kill-switch/reactivation; unauthenticated write paths remain non-live.
6. Integrate dark-pool/off-exchange evidence only after source/methodology/latency are explicit.
7. Promote strategies only through replay -> paper -> broker-paper -> live based on recorded evidence.
8. Keep PR #8 draft until evidence, review, and operational readiness justify merge/readiness.

## Known blockers / intentionally unfinished work

- No strategy is approved for live autonomous execution.
- Real options OI/Greeks provider ingestion is not complete.
- Dark-pool/off-exchange data is not integrated.
- Strategy performance evidence and walk-forward evaluation are not sufficient for paper/live promotion.
- Authenticated operator write APIs for manual kill-switch/reactivation are not implemented; unauthenticated write paths remain non-live.
- Live credentials are never stored in Git and are not part of this branch.

## Rule for future agents

Do not interpret "live execution supported" as "strategies are safe to run live". Broker connectivity and strategy promotion are separate gates. The live broker path may exist while every strategy remains blocked from autonomous live promotion until evidence is sufficient.
