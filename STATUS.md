# Global Market Autonomous Trading Platform — Status

Updated: 2026-08-24
Branch: `feature/autonomous-live-trading-platform`
Draft PR: `#8`

## Recovery order

When resuming after context pressure, a new session, an agent handoff, or uncertainty about prior decisions, read in this order:

1. `PROJECT_DIRECTION.md` — durable product direction and safety invariants.
2. `STATUS.md` — current execution state, completed work, blockers, and next steps.
3. `AGENTS.md` — repository operating rules.
4. `docs/INNOVATION_DOCTRINE.md` — innovation/reframing method and strategy-promotion doctrine.
5. newest relevant spec/plan/decision record.
6. current branch diff, PR/CI state, and live evidence.

Do not ask the user to repeat durable direction already recorded in these files.

## Current product state

This repository is now being built as the primary autonomous market-monitoring and trading platform, not as a read-only observatory.

Primary runtime chain:

`market data -> market structure -> strategy hypothesis/signal -> portfolio allocation -> deterministic risk -> execution -> reconciliation -> audit -> continuous evaluation/promotion`

Continuous processes:

- market-feed loop;
- options-structure loop when configured;
- account-observer/reconciliation loop when configured;
- continuous-improvement loop;
- autonomous market-cycle processing for each accepted market observation.

Core operating rule:

**Processes should recover and continue where safe; capital permission must fail closed.** A data/feed failure may reconnect automatically, but autonomous risk permission can HALT and remains latched until a separate controlled recovery path exists.

Live execution is a first-class capability but remains disabled by default. Broker execution capability never implies strategy eligibility.

## Completed on this branch

### Direction, recovery, and innovation doctrine

- `PROJECT_DIRECTION.md` is the long-horizon project compass.
- `STATUS.md` is the short-horizon execution checkpoint.
- `AGENTS.md` contains mandatory recovery and safety rules.
- `docs/INNOVATION_DOCTRINE.md` adapts constraint deletion / reframing to trading-system design.
- Strategy design records `category default -> deleted constraint -> new axis` before promotion.
- Draft PR `#8` remains the integration/verification surface.

### Trading modes and broker boundary

- Explicit `replay`, `paper`, `broker-paper`, and `live` modes.
- Explicit execution providers: local paper, Alpaca, IBKR.
- Live mode requires deliberate enable/confirmation; credentials alone cannot enable live execution.
- Common execution-adapter boundary across paper and broker modes.
- Alpaca submit/query-by-client-id/cancel/status handling.
- IBKR submit/`cOID`/reply-confirmation allowlist/cancel/status handling.
- Unknown broker outcomes reconcile before retry and can trigger HALT.

### Deterministic safety kernel

- ACTIVE / REDUCING / HALTED trading states.
- Persisted trading state survives restart; invalid persisted state fails closed.
- Risk checks for allowlist, order notional, symbol exposure, group exposure, gross exposure, stale market data, stale account state, daily loss, and portfolio drawdown.
- Deterministic client-order-id behavior and execution idempotency.
- Persistent completed-cycle checkpoints prevent duplicate handling after replay/restart.
- UNKNOWN execution results are deliberately not checkpointed until reconciliation resolves them.
- Append-only audit trail records signal, risk, execution, reconciliation, system, and kill-switch events.
- Legacy unauthenticated order API remains restricted to local paper/replay and cannot route to live brokers.

### Market data and resilient loops

- Alpaca multi-symbol stock minute-bar stream.
- Updated/revised bars update history but do not create a second trade decision.
- Market-feed supervisor reconnects after stream-level failures with bounded backoff.
- A stream-level failure while autonomous execution is enabled triggers persisted HALT; feed reconnection continues but does **not** auto-reactivate capital permission.
- Replay feed restart resumes from the latest persisted candle time and close instead of rolling the synthetic market clock backwards.
- Browser market streaming distinguishes transport/JSON errors from chart-render failures.
- Browser stream handling ignores older out-of-order candles per symbol+interval rather than sending them into the chart.
- Runtime loop status exposes running state, failure count, and last error read-only.
- Loop failures are observable rather than silently killing a task.
- `/api/market/coverage` independently reports per-symbol raw feed coverage as fresh/stale/missing and strategy-cycle handling as observed/waiting/error.
- Feed coverage is derived from the persisted candle store, so a received candle and a failed strategy cycle remain distinguishable states.

### Market structure and options provenance

- VWAP and anchored-VWAP primitives.
- Volume-profile primitives.
- Order-flow-imbalance primitives.
- Transparent GEX proxy with explicit dealer/sign assumptions.
- Put-wall / call-wall estimation does not claim known dealer inventory.
- Alpaca options ingestion combines contract metadata/open interest with option snapshot Greeks.
- Options provenance retains OI date, Greeks timing/source/feed, fetch timing, contract/expiration/strike/multiplier context.
- Options-structure service converts verified chain data into market-structure snapshots.
- Structure snapshots have freshness/TTL behavior.
- Stale or failed options data is invalidated rather than reused as if current.
- Options-structure loop self-recovers after loop-level exceptions, records failure state, invalidates stale structure, and continues future refresh attempts.
- `TradingCycleResult` now retains the exact market-structure snapshot that strategies actually evaluated, including observation time, market source, reference price, and methodology/provenance.
- `/api/market/structure` exposes that exact strategy-used structure read-only instead of recomputing a potentially different view after the fact.
- Missing structure values stay null/`missing`; the API does not convert absent OFI/options data into zero.

### Strategies and portfolio allocation

- Versioned strategy signals include action, confidence, rationale, invalidation, and observation timestamp.
- VWAP reclaim/rejection strategy.
- Gamma-level strategy requires wall interaction plus observable order-flow confirmation.
- Portfolio allocation uses loss budget, invalidation distance, per-order caps, and correlated/group exposure.
- Cost basis is portfolio state only and cannot by itself trigger averaging down.

### Strategy promotion and continuous improvement

- `StrategyHypothesis` manifests record problem, default premise, deleted constraint, new axis, expected mechanism, required inputs/provenance, falsification, failure regimes, safety constraints, version, and stage.
- Canonical maturity path: `idea -> research -> replay -> paper -> broker-paper -> live`.
- Promotion evidence is persisted by exact strategy id + version.
- Runtime code version must match manifest version.
- Missing manifest/evidence, version mismatch, or insufficient maturity fails closed.
- `AUTO_TRADING_ENABLED`, broker capability, promotion eligibility, and strategy-health eligibility are independent conditions.
- Continuous-improvement loop settles historical strategy observations against future prices, applies configured transaction costs, and updates rolling expectancy/win-rate/drawdown evidence.
- Runtime evidence merges monotonically and cannot replace stronger historical OOS/walk-forward evidence with a tiny new sample.
- Degraded strategies can force REDUCING.
- Health recovery clears a health blocker but does not automatically restore ACTIVE from REDUCING/HALTED.
- The system does not self-modify strategy code/parameters or automatically skip promotion stages in live operation.

### Broker truth / reconciliation

- Broker modes normalize cash, positions, equity, open orders, and daily account PnL into portfolio/risk state.
- Missing critical broker state is invalid; the system does not substitute zero and continue increasing risk.
- Alpaca and IBKR account truth remain separate from local paper state.

### Autonomous Trading Console — current frontend

The old Observatory-style homepage has been replaced with a focused autonomous-trading console.

The homepage now answers these questions directly:

1. Is each configured symbol actually receiving fresh market candles?
2. Did the strategy cycle successfully process the observation?
3. What exact market structure did the strategies see?
4. What did each strategy decide and why?
5. Did portfolio/risk permit an order?
6. What actually happened at execution/runtime level?

Visible panels now focus on:

- system conclusion and execution/promotion state;
- per-symbol decision cards;
- separate `FEED FRESH / FEED STALE / FEED MISSING` and `OBSERVED / WAITING / CYCLE ERROR` state;
- exact strategy-used VWAP / OFI / Put Wall estimate / Call Wall estimate / Net GEX Proxy values;
- structure freshness and provenance, with missing values shown as `未观测` rather than zero;
- strategy action, confidence, rationale, invalidation, allocation, execution result, and current position context;
- compact market chart for the selected symbol;
- append-only decision-chain/audit timeline;
- portfolio equity/cash/gross exposure/P&L and positions;
- recent execution history;
- strategy health and promotion state;
- runtime-loop liveness, failures, and last error.

Removed from the main frontend as unrelated clutter:

- manual simulated-order form;
- crisis-winner showcase;
- partnership-research showcase;
- evidence-library table;
- research refresh button;
- external-account showcase table.

The browser backend adapter used by the console is read-only (GET-only). The static observe-only build excludes this adapter entirely.

Important truthfulness behavior: a moving replay chart is never presented as proof that `NVDA / SPCX / KLAC` have corresponding live market cycles. Feed coverage and market-structure availability are displayed independently for each symbol.

## Current strategy reframes

### VWAP v1.0.0

- Category default: price above/below VWAP is treated as generic directional prediction.
- Deleted constraint: every VWAP observation must predict direction.
- New axis: trade observable state transitions across VWAP with explicit invalidation and abstain otherwise.
- Current maturity remains replay unless version-specific promotion evidence proves otherwise.

### Gamma Levels v1.0.0

- Category default: call wall / put wall estimates are treated as authoritative support/resistance.
- Deleted constraint: a wall estimate alone is sufficient evidence.
- New axis: wall interaction requires observable flow confirmation while GEX methodology/sign assumptions and provenance remain explicit.
- Current maturity remains replay unless version-specific promotion evidence proves otherwise.

## Verification state

Draft PR `#8` is active and remains draft.

Latest relevant full verification: GitHub Actions CI `#352` on 2026-08-24 completed green for the market-truth / market-coverage console head.

Verified green in that run:

- Ruff;
- full pytest suite on Python 3.12;
- full pytest suite on Python 3.13;
- application `compileall`;
- required engineering-skill check;
- Docker container build;
- replay restart monotonic-time regression tests;
- browser invalid-stream/render-error/out-of-order regression tests;
- exact strategy-used market-structure contract tests;
- provenance-aware `/api/market/structure` API tests;
- per-symbol `/api/market/coverage` fresh/stale/missing tests;
- read-only browser adapter contract tests;
- frontend truthfulness contract for structure, coverage, and cycle state.

A separate local browser session against the user's real Alpaca credentials has not been executed from this environment. Do not claim real Alpaca end-to-end verification until actual credentials/runtime evidence exist outside Git.

## Immediate next steps

1. Expand replay/walk-forward/OOS evidence generation and promotion metrics with held-out partitions, realistic costs/latency, provenance, and regime segmentation.
2. Add strategy attribution/degradation diagnostics by symbol/regime so one weak regime does not hide inside aggregate expectancy.
3. Run the console against actual Alpaca multi-symbol stock market data for `NVDA / SPCX / KLAC` in monitor-only/paper-safe configuration and verify source/coverage/decision cards end-to-end when credentials are available locally.
4. Add authenticated operator controls for explicit HALT/reactivation; no unauthenticated live-control writes.
5. Integrate dark-pool/off-exchange evidence only after source, classification methodology, and reporting latency are explicit.
6. Continue replay -> paper -> broker-paper -> live promotion only from recorded evidence.
7. Keep PR #8 draft until evidence and operational readiness justify merge/readiness.

## Known blockers / intentionally unfinished work

- No current strategy is approved for autonomous live capital.
- Real broker credentials are never stored in Git and are not part of the branch.
- Real Alpaca end-to-end market coverage for `NVDA / SPCX / KLAC` has not been verified from this execution environment.
- Dark-pool/off-exchange evidence is not yet integrated.
- Strategy walk-forward/OOS evidence is not yet sufficient for live promotion.
- Authenticated operator write APIs for controlled reactivation are not implemented.
- Default local `.env` may remain replay-oriented; seeing a moving chart is not equivalent to receiving real stock market data.

## Rule for future agents

Do not interpret “live execution supported” as “strategies are safe to run live”. Broker connectivity and strategy promotion are separate gates. Keep improving data, evidence, runtime resilience, and observability while preserving fail-closed capital permissions.
