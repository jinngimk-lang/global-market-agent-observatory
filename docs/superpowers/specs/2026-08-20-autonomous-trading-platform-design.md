# Autonomous Trading Platform Design

**Status:** Approved direction, implementation in progress

**Project compass:** `PROJECT_DIRECTION.md`

## Objective

Transform the repository into the primary autonomous monitoring and trading platform with one controlled path from market observations to paper or live broker execution.

## Architecture

The runtime is event-driven and mode-aware. Market/provider events enter a normalized market layer, derived features are computed by market-intelligence modules, strategies emit structured signals, portfolio logic proposes order intents, deterministic risk evaluates every intent, and an execution adapter performs paper/broker-paper/live actions. Broker reconciliation and audit persistence close the loop.

The architecture borrows proven ideas without wholesale vendoring: plugin separation and research/live parity from QuantConnect LEAN; mandatory risk-before-execution and explicit trading states from NautilusTrader; controller/executor separation from Hummingbot; and event dispatch from vn.py. External implementation code is not copied unless license/security review explicitly permits it.

## Operating modes

- `replay`: historical data + deterministic paper fills.
- `paper`: current/replayed data + local paper broker.
- `broker-paper`: broker paper/sandbox execution.
- `live`: real broker execution.

`live` requires an explicit mode plus an explicit live-enable gate. Credentials alone can never select live mode.

## Core contracts

### StrategySignal

A versioned, immutable signal containing symbol, action, confidence, rationale codes, evidence references, entry/invalidation metadata, and timestamp.

### OrderIntent

A broker-neutral requested action derived from a strategy/portfolio decision. It contains an idempotent client order id and never directly executes.

### RiskDecision

A deterministic result that can approve, resize, or reject an intent. Risk controls must fail closed when data or account state is stale/unknown.

### ExecutionAdapter

Common asynchronous interface for submission, cancellation, order lookup, and account/position reconciliation. Adapters include local paper, Alpaca, and IBKR.

### TradingOrchestrator

Coordinates market state refresh, feature computation, strategy evaluation, portfolio aggregation, risk, execution, reconciliation, audit, and health transitions.

## Trading states

The runtime has explicit safety states:

- `active`: new exposure may be approved.
- `reducing`: only exposure-reducing actions may be approved.
- `halted`: no new/modified exposure; cancellation/reconciliation remain available.

A kill switch moves the runtime to `halted` without depending on an LLM.

## Live execution gate

Live execution requires all of:

1. `TRADING_MODE=live`.
2. `LIVE_TRADING_ENABLED=true`.
3. `LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING`.
4. a configured live-capable execution adapter.
5. fresh market/account state.
6. risk engine not halted.

Anything else fails closed.

## Initial universe

NVDA, SPCX, and KLAC are the first configured equity symbols, while symbol/universe support remains generic.

## Initial market intelligence

The first implementation wave will normalize and expose:

- price/volume and relative volume;
- VWAP/anchored VWAP;
- support/resistance zones;
- volume-profile POC/HVN/LVN;
- options OI/Greeks;
- GEX estimate with methodology metadata;
- gamma flip, put wall, call wall;
- order-flow imbalance where data allows;
- off-exchange/dark-pool reference data where provenance and latency are explicit.

## Risk requirements

Initial deterministic controls include:

- allowed universe;
- max order notional;
- max symbol exposure;
- max gross exposure;
- max correlated/group exposure;
- daily realized loss;
- mark-to-market drawdown;
- stale market/account data lockout;
- consecutive-error lockout;
- trading state/kill switch;
- reduce-only enforcement in reducing state;
- idempotent order identifiers.

## Reconciliation

Live broker state is authoritative. Unknown submit outcomes trigger reconciliation before retry. The system persists broker ids, client ids, status transitions, fills, and errors so duplicate execution can be prevented.

## Audit

Every strategy signal, order intent, risk decision, adapter request/result, fill, reconciliation, health state, configuration version, and kill-switch transition is recorded.

## External-source policy

Architecture ideas may be adopted from external projects. Code import requires explicit license compatibility, provenance, attribution, and focused tests. Apache-2.0/MIT sources are preferred for selective adaptation; LGPL/GPL sources are treated primarily as design references unless deliberate compliance work is performed.

## Verification

TDD is used for stable seams. Release gates include unit tests, adapter contract tests, stale-state/failure injection, idempotency tests, replay/backtests with fees/slippage, broker-paper soak tests, and reconciliation tests.
