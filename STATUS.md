# Global Market Autonomous Trading Platform — Status

Updated: 2026-08-21
Branch: `feature/autonomous-live-trading-platform`

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

## Completed on this branch

### Direction and recovery

- Added `PROJECT_DIRECTION.md` as the long-horizon project compass.
- Updated `AGENTS.md` with mandatory context recovery and live-trading safety rules.
- Added this `STATUS.md` as the short-horizon execution checkpoint.
- Added an implementation/design plan for the autonomous trading conversion.

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
- Added append-only audit events for signals, risk decisions, execution, reconciliation, system state, and kill switch transitions.

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

### Autonomous loop

- Added an autonomous market-cycle engine that processes bars through strategy -> allocation -> risk -> execution -> audit.
- Monitoring mode can generate signals without sending orders.
- Market-data revisions are stored but do not trigger duplicate execution.
- Added deterministic cycle identity/checkpoint work to prevent replay/restart duplicate processing.
- Main `ApplicationState` is being migrated to the new execution/orchestration architecture.
- Legacy unauthenticated `/api/orders` remains local-paper-only and must never become a live broker write path.

### Broker truth / reconciliation

- Added broker portfolio normalization so live risk can use broker cash/positions/equity rather than local guesses.
- Added daily account PnL support to broker snapshots.
- Live/broker modes treat missing critical broker state as invalid rather than silently substituting zero.

## Innovation-method integration — current workstream

The uploaded innovation skill is being adapted into a trading-system doctrine rather than copied literally.

Key project translation:

- `reframe before optimize` -> challenge the trading-system premise before optimizing indicators/parameters.
- `category default` -> identify the assumption conventional trading systems optimize.
- `constraint deletion` -> ask whether that assumption can disappear entirely.
- `new axis` -> define the new system property that becomes the competitive edge.
- three-direction exploration -> compare incremental improvement, observable-market bridge, and premise deletion before implementation.
- creative review gate -> deterministic innovation/hypothesis review gate.
- persistent project protocol -> `PROJECT_DIRECTION.md` + `STATUS.md` + decision records + recovery order.

The next implementation is a versioned Strategy Hypothesis / Promotion Gate so a strategy cannot jump from an appealing idea directly into live execution.

## Current strategy reframes

### VWAP strategy

- Category default: use position relative to VWAP as a generic bullish/bearish indicator.
- Deleted constraint: a strategy must predict direction from the level itself.
- New axis: trade observable state transitions across VWAP with explicit invalidation and abstain otherwise.
- Current promotion state: research/replay; not approved for live autonomous risk.

### Gamma wall strategy

- Category default: treat call wall / put wall as authoritative support or resistance.
- Deleted constraint: a wall estimate alone is sufficient evidence.
- New axis: wall interaction must be confirmed by observable flow, with GEX methodology/sign assumptions retained.
- Current promotion state: research/replay; not approved for live autonomous risk.

## Immediate next steps

1. Add `docs/INNOVATION_DOCTRINE.md` and a decision record for the reframing method.
2. Implement Strategy Hypothesis manifests and a deterministic promotion gate.
3. Enforce promotion stage when autonomous execution is enabled; current research strategies must not be allowed to jump directly to live.
4. Finish persistent HALT/trading-state recovery across process restarts.
5. Finish main API/runtime migration and expose read-only execution/promotion health.
6. Integrate real options OI/Greeks data with provenance for GEX/call-wall/put-wall features.
7. Add replay/backtest evidence collection with transaction costs and out-of-sample metrics.
8. Promote strategies only through replay -> paper -> broker-paper -> live based on recorded evidence.
9. Run full CI/static/container verification before merge.

## Known blockers / intentionally unfinished work

- No strategy is yet approved for live autonomous execution.
- Real options OI/Greeks provider ingestion is not yet complete.
- Dark-pool/off-exchange data is not yet integrated.
- Strategy performance evidence and walk-forward evaluation are not yet sufficient for live promotion.
- Authenticated operator write APIs for manual kill-switch/reactivation are not yet implemented; unauthenticated write paths must remain non-live.
- Live credentials are never stored in Git and are not part of this branch.

## Rule for future agents

Do not interpret "live execution supported" as "strategies are safe to run live". Broker connectivity and strategy promotion are separate gates. The live broker path may exist while every strategy remains blocked from autonomous live promotion until evidence is sufficient.
