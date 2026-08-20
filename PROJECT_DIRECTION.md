# Global Market Autonomous Trading Platform — Project Direction

## Purpose

This repository is being transformed from a market observatory into the primary autonomous trading system.

The system's core mission is:

1. Continuously monitor markets and portfolio state.
2. Convert observable market structure and capital-flow evidence into explicit trading signals.
3. Route every signal through deterministic portfolio and risk controls.
4. Support both paper and live execution through broker adapters.
5. Keep live execution disabled by default until explicitly enabled in runtime configuration.
6. Maintain complete auditability: every signal, risk decision, order intent, order, fill, rejection, data source, and system state transition must be reconstructable.

This file is the repository's long-horizon project compass. Agents must reread it whenever resuming work after context loss, starting a new implementation session, or making an architectural decision that could alter the product direction.

## Product Identity

This is not primarily a dashboard, research archive, alert bot, or paper-trading demo.

It is an **autonomous market monitoring and trading platform** whose main loop is:

`market data -> market structure -> strategy signals -> portfolio context -> deterministic risk -> order intent -> execution -> reconciliation -> audit -> learning/evaluation`

Research, dashboards, backtests, replay, and paper trading exist to improve and validate that loop.

## Initial Trading Universe

The first explicitly managed US equity names are:

- NVDA
- SPCX
- KLAC

The architecture must not hard-code these symbols. The universe must be configurable and extensible to other equities, ETFs, options, futures, and crypto where broker/data support exists.

## Core Principles

### 1. Capital flow and market structure first

The system should prioritize directly observable market structure and flow evidence rather than relying only on narrative explanations such as sector labels or news themes.

Important inputs include:

- price and returns
- volume and relative volume
- bid/ask and spread
- order-book imbalance when available
- executed trade imbalance
- VWAP and anchored VWAP
- volume profile, POC, HVN, LVN
- support and resistance zones
- options open interest
- implied volatility and Greeks
- gamma exposure estimates
- gamma flip / zero-gamma levels
- put wall / call wall estimates
- unusual options activity and sweeps when reliable data exists
- off-exchange / ATS / dark-pool prints where sourced and timestamped
- short interest / short volume where relevant
- ETF and institutional positioning data where available
- corporate events, earnings, lockups, splits, and macro events

Do not collapse all of these into a vague "main fund flow" number. Every metric must retain provenance, timestamp, methodology, and confidence.

### 2. Evidence over market folklore

Trading methods may originate from common market language, but implementation must separate:

- directly observed facts
- calculated metrics
- model assumptions
- inferred dealer positioning
- strategy hypotheses

For example, GEX calculations must preserve the sign convention and dealer-inventory assumption used. A calculated put wall or call wall is an estimate, not an oracle.

### 3. Strategies propose; risk decides

No strategy, LLM, research agent, or signal source may directly place a broker order.

The required path is:

`StrategySignal -> OrderIntent -> RiskDecision -> ExecutionAdapter`

The deterministic risk engine has final authority.

### 4. Live trading is a first-class capability, but fails closed

Live broker execution is part of the main system design, not a separate demo subsystem.

However:

- live execution must be disabled by default
- a deliberate runtime flag must enable it
- credentials must come only from runtime secret injection
- missing/stale market data must block new live risk
- unknown account state must block new live risk
- failed reconciliation must block new live risk
- kill switch must block all new orders immediately
- repeated execution or data errors must trigger automatic lockout

### 5. Portfolio decisions beat isolated-symbol decisions

The system must understand correlated exposure.

A valid single-stock buy signal can still be rejected because the portfolio already has excessive exposure to the same factor, industry, volatility regime, or event risk.

Risk should eventually cover:

- per-order loss budget
- per-symbol exposure
- correlated/group exposure
- gross and net exposure
- leverage
- cash/buying power
- daily realized loss
- daily mark-to-market drawdown
- trailing portfolio drawdown
- volatility-adjusted sizing
- event risk
- consecutive-loss lockout
- liquidity / spread constraints
- stale-data lockout

### 6. No averaging down merely because price is below cost basis

Cost basis is portfolio state, not a buy signal.

Additional risk requires a fresh strategy signal and risk approval.

### 7. Reconciliation is mandatory

The broker is the source of truth for live account state.

The system must continuously reconcile:

- cash
- buying power
- positions
- open orders
- partial fills
- fills
- cancellations
- rejections

Internal state must never silently diverge from broker state.

## Main Runtime Architecture

The target architecture is organized around these runtime responsibilities.

### Market Data Layer

Responsibilities:

- live/replayed quotes, trades, candles, and options data
- normalized timestamps and symbols
- data freshness checks
- provider health
- provenance

Potential providers/brokers may include Alpaca, IBKR, Longbridge, exchange/vendor feeds, and other reviewed sources.

### Market Intelligence Layer

Produces deterministic or explicitly modeled features such as:

- support / resistance
- VWAP / anchored VWAP
- volume profile POC, HVN, LVN
- realized volatility
- relative volume
- order-flow imbalance
- options OI distribution
- GEX estimates
- gamma flip
- call wall
- put wall
- unusual options activity
- dark-pool/off-exchange reference levels

### Strategy Layer

Strategies consume normalized market intelligence and portfolio context and emit structured signals.

Every signal should contain at least:

- strategy id and version
- symbol
- action: buy / sell / hold / reduce / exit
- confidence
- rationale codes
- observed evidence references
- intended entry region
- invalidation / stop condition
- target or exit logic where applicable
- maximum holding horizon where applicable
- generated timestamp

Initial strategy families to research and implement include:

- put-wall support / breakdown
- call-wall rejection / breakout
- gamma-flip regime changes
- positive-gamma mean reversion
- negative-gamma trend continuation
- VWAP reclaim / rejection
- anchored-VWAP support / resistance
- volume-profile POC reversion
- LVN breakout / rejection
- order-flow imbalance
- absorption / liquidity-defense patterns where data supports them
- unusual options flow with price confirmation
- breakout / pullback momentum
- overnight and close-to-open effects
- event-aware risk reduction

Strategies must be backtestable and replayable wherever data permits.

### Portfolio Engine

Responsibilities:

- aggregate signals across symbols
- rank opportunities
- understand current positions and cost bases
- detect correlated exposure
- translate signal strength into requested risk
- avoid contradictory simultaneous intents

### Deterministic Risk Engine

Responsibilities:

- approve, resize, or reject order intents
- enforce all hard limits
- fail closed under uncertain state
- implement kill switch and lockouts

The LLM must never be able to bypass this engine.

### Execution Layer

A common execution interface should support:

- paper broker
- Alpaca execution adapter
- IBKR execution adapter
- future broker adapters

Execution must handle:

- market and limit orders
- idempotent client order IDs
- partial fills
- cancellation
- rejection
- retry rules that cannot duplicate an order
- reconciliation

### Orchestrator / Trading Loop

The main process coordinates:

1. refresh market and broker state
2. validate data freshness and system health
3. compute market intelligence
4. evaluate strategies
5. aggregate portfolio intent
6. run deterministic risk checks
7. submit approved order intents
8. reconcile broker state
9. persist audit events
10. emit monitoring metrics and alerts

### Audit and Event Store

Persist enough information to reconstruct why every action occurred.

At minimum record:

- source market observations / references
- derived feature snapshots
- strategy signals
- rejected and approved order intents
- risk decisions and rule codes
- broker requests/responses
- order lifecycle
- fills
- portfolio snapshots
- kill-switch transitions
- configuration version
- strategy version

## Operating Modes

The main system should support:

- `replay`: historical deterministic playback
- `paper`: live/replayed market data with simulated execution
- `broker-paper`: broker-provided paper account execution where available
- `live`: real broker execution

Mode selection must be explicit and visible in logs/UI.

`live` must never be inferred from credentials alone.

## Live-Trading Safety Invariants

These are architectural invariants unless the project direction is deliberately changed and reviewed.

1. Live trading is OFF by default.
2. Strategy output alone cannot execute.
3. A deterministic risk decision is mandatory for every new order.
4. Orders require idempotent client identifiers.
5. Stale or missing market data blocks new positions.
6. Stale or missing broker/account state blocks new positions.
7. Unknown execution result triggers reconciliation before retry.
8. Secrets are never committed to Git.
9. Kill switch is available independent of strategy logic.
10. The system must be able to stop creating new exposure without requiring an LLM or external research service.

## External Project Reuse Policy

External GitHub projects may be studied and selected components may be adapted when they materially improve this system.

Before importing code:

- inspect license compatibility
- identify upstream repository and commit/tag
- understand the security model
- remove unrelated code
- avoid vendoring secrets or example credentials
- preserve attribution/license requirements
- add tests around adapted behavior
- prefer small reviewed adaptations over blindly copying entire projects

Good external ideas may be adopted even when code is not copied.

## Data and Broker Priorities

Near-term priorities:

1. robust US equity quote/trade data
2. options chain + Greeks + OI for GEX-style analysis
3. reliable portfolio/account reconciliation
4. one fully working live broker execution adapter
5. a second broker adapter for portability
6. off-exchange/FINRA and institutional evidence sources where latency is appropriate

Existing Alpaca, IBKR, and paper components should be reused when sound, but their roles may be substantially rewritten.

## Testing and Validation

All behavior changes should follow TDD where practical.

Required validation layers:

- unit tests for calculations and risk rules
- contract tests for broker adapters
- replay tests for strategies
- idempotency tests for order submission
- failure-injection tests for stale feeds and broker outages
- reconciliation tests
- paper/broker-paper soak tests
- backtests with transaction costs and slippage
- walk-forward / out-of-sample evaluation for strategies

Do not promote a strategy to live solely because its in-sample backtest is profitable.

## Delivery Order

The intended implementation sequence is:

### Phase 1 — Trading Core

- redefine product identity and configuration modes
- add execution adapter contract
- add explicit live-trading enable gate
- add trading orchestrator
- add audit event model
- strengthen risk limits and kill switch
- preserve paper trading as a fully supported mode

### Phase 2 — Broker Execution and Reconciliation

- implement Alpaca execution adapter
- implement/order lifecycle reconciliation
- implement IBKR execution adapter or select another broker based on operational fit
- add broker contract tests and failure handling

### Phase 3 — Market Intelligence

- integrate `MarketStructureSnapshot` work into main branch architecture
- VWAP / anchored VWAP
- support/resistance
- volume profile
- options OI / Greeks
- GEX / gamma flip / call wall / put wall with explicit methodology metadata
- order-flow features

### Phase 4 — Strategy Library

- implement strategies as isolated versioned modules
- replay/backtest each one
- add regime filters
- combine via portfolio engine

### Phase 5 — Autonomous Portfolio Operation

- ranking and capital allocation
- correlated exposure controls
- automatic exits and risk reduction
- continuous broker reconciliation
- operational alerts and dashboards

### Phase 6 — Evidence and Optimization

- dark-pool/off-exchange evidence
- institutional/ETF flow evidence
- strategy attribution
- walk-forward evaluation
- parameter governance
- automatic disabling of degraded strategies

## Current User Portfolio Context

The first user-facing monitoring use case includes roughly equal initial allocations to:

- NVDA, user cost basis around USD 195
- SPCX, user cost basis around USD 159
- KLAC, user cost basis around USD 244

These values are initial portfolio context only. They must never be treated as automatic support/resistance or reasons to average down.

## Definition of Success

The project is successful when it can:

1. run continuously without an LLM being required for safety-critical operation
2. observe live markets and account state reliably
3. compute transparent market-structure features
4. emit reproducible strategy signals
5. apply deterministic portfolio/risk limits
6. execute paper and live orders through the same controlled workflow
7. reconcile broker state after every uncertain execution outcome
8. provide a complete audit trail
9. measure strategy performance out of sample
10. automatically stop or reduce risk when data, execution, or strategy health deteriorates

## Context-Recovery Protocol for Agents

When an agent loses conversational context, starts a new session, resumes after a long interruption, or is unsure whether a proposed change fits the project:

1. Read `PROJECT_DIRECTION.md` in full.
2. Read `AGENTS.md`.
3. Read `CONTEXT.md` and any relevant ADRs/specs/plans for the current change.
4. Inspect current branch status and recent commits before modifying code.
5. Reconcile the requested change against the Purpose, Core Principles, Live-Trading Safety Invariants, and Delivery Order above.
6. If implementation conflicts with this document, do not silently drift. Either preserve the documented direction or explicitly update this document as part of a deliberate project-direction change.

This protocol is part of the project architecture, not optional documentation hygiene.
