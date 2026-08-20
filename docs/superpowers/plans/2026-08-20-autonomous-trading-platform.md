# Autonomous Trading Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the repository into a mode-aware autonomous monitoring and trading platform with deterministic risk, audited execution, broker reconciliation, and selectively enabled live trading.

**Architecture:** Keep existing market, paper broker, account observer, risk, store, API, and research seams where sound, but re-center the application around a trading orchestrator. Strategy output produces broker-neutral intents, deterministic risk gates them, execution adapters submit them, and reconciliation/audit closes the loop. The same contracts support replay, paper, broker-paper, and live modes.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, httpx, websockets, SQLite, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-08-20-autonomous-trading-platform-design.md`

## Global Constraints

- `PROJECT_DIRECTION.md` is the product compass and must be reread on context recovery.
- Live trading is disabled by default.
- `live` mode requires `LIVE_TRADING_ENABLED=true` and `LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING`.
- Strategy/LLM output never bypasses deterministic risk.
- Unknown market/account/execution state fails closed for new exposure.
- Secrets are runtime-injected only.
- All order submissions use idempotent client order ids.
- Unknown broker submit outcomes reconcile before retry.
- External code import requires license/security/provenance review.

---

### Task 1: Runtime modes and live-trading gate

**Files:**
- Modify: `app/settings.py`
- Modify: `app/domain/models.py`
- Create: `tests/test_trading_settings.py`
- Modify: `.env.example`
- Modify: `CONTEXT.md`

**Interfaces:**
- Produces: `TradingMode`, `TradingState`, `Settings.trading_mode`, `Settings.live_trading_enabled`, `Settings.live_trading_confirmation`, `Settings.live_execution_permitted`.

- [ ] Write failing tests proving paper mode remains the default, credentials alone do not enable live, live mode fails without both gates, and explicit live configuration is accepted.
- [ ] Run the targeted test and verify the new assertions fail because the new mode/gate API does not exist.
- [ ] Add `TradingMode`/`TradingState`, replace the current absolute live-trading prohibition with the explicit multi-gate configuration, and preserve a fail-closed default.
- [ ] Update `.env.example` and `CONTEXT.md` to describe the new product identity and gates.
- [ ] Run targeted tests, then the existing settings/API tests.

### Task 2: Execution adapter contract and trading state

**Files:**
- Modify: `app/broker/base.py`
- Create: `app/execution/__init__.py`
- Create: `app/execution/models.py`
- Create: `app/execution/controller.py`
- Create: `tests/test_execution_controller.py`

**Interfaces:**
- Consumes: `OrderIntent`, `RiskDecision`, `TradingMode`, `TradingState`.
- Produces: `ExecutionAdapter`, `ExecutionResult`, `ExecutionController.submit(intent, portfolio, market_state)`.

- [ ] Write failing tests proving halted state blocks new orders, reducing state blocks exposure increases, rejected risk decisions never reach an adapter, and duplicate client ids return the existing execution result.
- [ ] Run targeted tests and verify RED.
- [ ] Implement the smallest adapter protocol/result model/controller required to pass.
- [ ] Run targeted tests and the broker/risk suites.

### Task 3: Strengthen deterministic portfolio risk

**Files:**
- Modify: `app/domain/models.py`
- Modify: `app/risk/engine.py`
- Modify: `tests/test_risk_engine.py`

**Interfaces:**
- Produces extended `RiskLimits` and deterministic rule codes for per-symbol exposure, drawdown, state, stale market state, and stale account state.

- [ ] Add failing tests for max-symbol exposure, stale market/account state, halted/reducing states, and portfolio drawdown lockout.
- [ ] Verify RED.
- [ ] Implement deterministic checks without network/LLM dependencies.
- [ ] Run risk and paper broker suites.

### Task 4: Audit event model and persistence

**Files:**
- Modify: `app/domain/models.py`
- Modify: `app/store/sqlite.py`
- Create: `app/audit/__init__.py`
- Create: `app/audit/service.py`
- Create: `tests/test_audit_events.py`

**Interfaces:**
- Produces: append-only `AuditEvent` persistence and query APIs.

- [ ] Add failing tests showing signal, risk, execution, reconciliation, and kill-switch events can be appended and queried in order.
- [ ] Verify RED.
- [ ] Add schema migration/creation and append-only service.
- [ ] Run storage/API suites.

### Task 5: Trading orchestrator

**Files:**
- Create: `app/trading/__init__.py`
- Create: `app/trading/orchestrator.py`
- Create: `app/trading/health.py`
- Create: `tests/test_trading_orchestrator.py`
- Modify: `app/api/state.py`

**Interfaces:**
- Consumes market snapshots, strategy signals, portfolio snapshots, risk engine, execution controller, audit service.
- Produces a deterministic cycle result and health/trading-state transitions.

- [ ] Add failing tests for a complete paper cycle, kill-switch behavior, stale-data fail-closed behavior, and reconciliation-before-retry after uncertain execution.
- [ ] Verify RED.
- [ ] Implement the orchestrator with dependency-injected components.
- [ ] Run orchestrator, API, risk, broker, and audit tests.

### Task 6: Alpaca execution adapter

**Files:**
- Modify: `app/broker/alpaca.py`
- Create: `tests/test_alpaca_execution.py`

**Interfaces:**
- Produces an `ExecutionAdapter` implementation supporting submit, cancel, order lookup, and account reconciliation against Alpaca paper/live endpoints.

- [ ] Add HTTP-contract tests for submit/cancel/query and unknown-submit reconciliation.
- [ ] Verify RED.
- [ ] Implement broker-neutral request mapping, idempotent client order ids, and explicit endpoint mode selection.
- [ ] Run adapter contract and observer tests.

### Task 7: IBKR execution adapter

**Files:**
- Modify: `app/broker/ibkr.py`
- Create: `tests/test_ibkr_execution.py`

**Interfaces:**
- Produces an `ExecutionAdapter` implementation using IBKR Client Portal/Gateway endpoints with reply/confirmation handling and reconciliation.

- [ ] Add contract tests for order submission, reply confirmation, cancellation, lookup, and reconciliation.
- [ ] Verify RED.
- [ ] Implement the adapter while retaining existing observation behavior.
- [ ] Run IBKR and shared adapter tests.

### Task 8: Market-structure intelligence in mainline architecture

**Files:**
- Create/modify: `app/research/market_intelligence.py`
- Create: `app/market/features.py`
- Create: `app/market/options.py`
- Create: `tests/test_market_intelligence.py`

**Interfaces:**
- Produces versioned snapshots with VWAP, anchored VWAP, support/resistance, volume-profile levels, GEX methodology metadata, gamma flip, put wall, and call wall.

- [ ] Port the existing branch primitives through failing tests first.
- [ ] Add deterministic feature tests for VWAP/volume profile and explicit GEX assumptions.
- [ ] Implement normalized feature calculators with provenance and timestamps.
- [ ] Run feature/research suites.

### Task 9: Strategy signal framework and first strategy set

**Files:**
- Create: `app/strategy/__init__.py`
- Create: `app/strategy/base.py`
- Create: `app/strategy/gamma_levels.py`
- Create: `app/strategy/vwap.py`
- Create: `app/strategy/volume_profile.py`
- Create: `tests/test_strategies.py`

**Interfaces:**
- Produces immutable versioned `StrategySignal` objects only; never broker calls.

- [ ] Add replayable failing tests for put-wall support/breakdown, call-wall rejection/breakout, gamma-flip regime, VWAP reclaim/rejection, and LVN breakout.
- [ ] Verify RED.
- [ ] Implement minimal deterministic strategies.
- [ ] Run strategy and orchestrator suites.

### Task 10: Portfolio aggregation and correlated-exposure control

**Files:**
- Create: `app/portfolio/engine.py`
- Create: `tests/test_portfolio_engine.py`
- Modify: `app/risk/engine.py`

**Interfaces:**
- Produces ranked/order-sized intents from multiple signals and portfolio factor groups.

- [ ] Add failing tests showing a strong single-name signal can be resized/rejected when correlated technology exposure is too high.
- [ ] Verify RED.
- [ ] Implement factor/group exposure and conflict resolution.
- [ ] Run portfolio/risk/orchestrator tests.

### Task 11: API/dashboard operational controls

**Files:**
- Modify: `app/api/main.py`
- Modify: `app/api/state.py`
- Modify: `app/web/*`
- Modify: `tests/test_api.py`
- Modify: `tests/test_dashboard_assets.py`

**Interfaces:**
- Produces readouts for trading mode/state, broker health, reconciliation health, strategy signals, risk decisions, order lifecycle, and kill-switch control.

- [ ] Add failing API tests for state/status and kill switch.
- [ ] Verify RED.
- [ ] Implement endpoints and dashboard surfaces without exposing secrets.
- [ ] Run API/browser/static suites.

### Task 12: Full verification and live-readiness gate

**Files:**
- Modify: `README.md`
- Modify: `docker-compose.yml`
- Modify: `Dockerfile` if required
- Create: `docs/operations/live-trading-runbook.md`
- Create: `docs/operations/failure-recovery.md`

**Interfaces:**
- Produces operational instructions and explicit pre-live checklist.

- [ ] Run the complete pytest suite.
- [ ] Run `ruff check .`.
- [ ] Verify live mode fails closed with missing confirmation, stale data, unknown broker state, and kill switch.
- [ ] Verify paper and broker-paper modes remain usable without live credentials.
- [ ] Document deployment, kill switch, reconciliation recovery, secret injection, and rollback procedures.
