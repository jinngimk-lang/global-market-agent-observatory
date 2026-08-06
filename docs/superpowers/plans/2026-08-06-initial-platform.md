# Initial Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a runnable private repository containing a safe paper-trading observability dashboard, real-time market feed, deterministic risk controls, account adapter interfaces, and source-graded research ingestion.

**Architecture:** FastAPI serves REST/WebSocket APIs and a static dashboard. Domain models, storage, market feeds, broker adapters, risk controls, and research collectors are isolated behind small interfaces. SQLite is the default store; replay data is the default source, while Binance public WebSocket data is enabled by configuration.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, websockets, SQLite, vanilla JavaScript, TradingView Lightweight Charts, pytest, ruff, Docker.

## Global Constraints

- Exclude mainland China securities markets.
- Default to replay/public market data and paper execution.
- Never commit credentials.
- Live order submission remains disabled.
- Risk rejection is fail-closed.
- Evidence records must include source URL, observation time, evidence grade, and content hash.
- Daily automated changes use a branch and draft PR; never auto-merge.

---

### Task 1: Domain contracts and risk engine

**Files:**
- Create: `app/domain/models.py`
- Create: `app/risk/engine.py`
- Test: `tests/test_risk_engine.py`

**Interfaces:**
- Produces: `OrderIntent`, `RiskLimits`, `PortfolioSnapshot`, `RiskDecision`, and `RiskEngine.evaluate(intent, portfolio)`.

- [ ] Write tests for allowlist, positive quantity, maximum order notional, maximum gross exposure, and daily loss lockout.
- [ ] Run the focused test and verify failure because the modules do not exist.
- [ ] Implement immutable Pydantic domain models and a fail-closed risk engine.
- [ ] Run the focused test and verify all cases pass.
- [ ] Commit the task.

### Task 2: SQLite persistence and paper broker

**Files:**
- Create: `app/store/sqlite.py`
- Create: `app/broker/base.py`
- Create: `app/broker/paper.py`
- Test: `tests/test_paper_broker.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: domain contracts from Task 1.
- Produces: `SQLiteStore`, `PaperBroker.submit(intent, market_price)`, and `PaperBroker.snapshot()`.

- [ ] Write failing persistence and paper-fill tests.
- [ ] Verify failures are caused by missing implementation.
- [ ] Implement schema creation, candle/order/fill/evidence persistence, and average-cost paper positions.
- [ ] Run focused tests and refactor with all tests green.
- [ ] Commit the task.

### Task 3: Market hub and feeds

**Files:**
- Create: `app/market/hub.py`
- Create: `app/market/replay.py`
- Create: `app/market/binance.py`
- Test: `tests/test_market_hub.py`

**Interfaces:**
- Produces: `MarketHub.publish(candle)`, `MarketHub.subscribe()`, `ReplayFeed.run()`, and `BinanceKlineFeed.run()`.

- [ ] Write failing fan-out and normalization tests.
- [ ] Verify the tests fail because the market classes are absent.
- [ ] Implement bounded subscriber queues, deterministic replay candles, and Binance kline normalization with reconnect backoff.
- [ ] Run focused tests and keep all tests green.
- [ ] Commit the task.

### Task 4: Evidence model and research collectors

**Files:**
- Create: `app/research/evidence.py`
- Create: `app/research/sec.py`
- Create: `app/research/github_releases.py`
- Create: `app/research/daily.py`
- Test: `tests/test_research.py`

**Interfaces:**
- Produces: `grade_evidence`, `parse_sec_submissions`, `SECCollector.collect_company`, and `GitHubReleaseCollector.collect`.

- [ ] Write failing tests using local SEC and GitHub fixtures.
- [ ] Verify parsing and grading tests fail for missing functions.
- [ ] Implement deterministic grading, partnership keyword classification, date filtering for the latest three years, source hashing, and daily JSON export.
- [ ] Run focused tests and refactor with all tests green.
- [ ] Commit the task.

### Task 5: API and WebSocket service

**Files:**
- Create: `app/settings.py`
- Create: `app/api/main.py`
- Create: `app/api/state.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Exposes: `/api/health`, `/api/candles/{symbol}`, `/api/orders`, `/api/portfolio`, `/api/evidence`, `/api/research/refresh`, and `/ws/market`.

- [ ] Write failing API tests for readiness, history, accepted/rejected paper orders, portfolio state, and WebSocket candles.
- [ ] Verify the failures are caused by missing routes.
- [ ] Implement lifespan startup, feed selection, structured errors, and REST/WebSocket routes.
- [ ] Run focused tests and the complete suite.
- [ ] Commit the task.

### Task 6: Browser dashboard

**Files:**
- Create: `app/web/index.html`
- Create: `app/web/app.js`
- Create: `app/web/styles.css`
- Test: `tests/test_dashboard_assets.py`

**Interfaces:**
- Consumes the API and WebSocket interfaces from Task 5.

- [ ] Write failing asset tests that require chart, account mode, positions, orders, evidence, and risk controls.
- [ ] Verify tests fail because the assets do not exist.
- [ ] Implement a responsive dashboard with live K-lines, order markers, account panels, evidence table, and paper-order controls.
- [ ] Run asset and API tests.
- [ ] Commit the task.

### Task 7: Packaging, operations, and CI

**Files:**
- Create: `pyproject.toml`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/daily-research.yml`
- Create: `README.md`
- Create: `docs/SECURITY.md`

**Interfaces:**
- Provides local, Docker, CI, and scheduled-research entrypoints.

- [ ] Add packaging and operations files without credentials.
- [ ] Install dependencies and run `ruff check .`.
- [ ] Run `pytest -q`.
- [ ] Build the Docker image.
- [ ] Start the container and verify `/api/health`.
- [ ] Commit the task.

### Task 8: Loop verification and publication preparation

**Files:**
- Create: `scripts/loop_verify.sh`
- Create: `docs/VERIFICATION.md`

**Interfaces:**
- Produces repeatable lint, unit, integration, import, and container checks.

- [ ] Run the verification loop repeatedly until three consecutive passes.
- [ ] Record exact verification commands and results.
- [ ] Create an archive for handoff.
- [ ] Attempt GitHub publication using available authorization; if repository creation is unavailable, provide the minimum required authorization step.
