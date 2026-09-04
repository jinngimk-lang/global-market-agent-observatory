# Multi-Timeframe Chart + Chinese Context Dashboard Implementation Plan

> Execute inline on `feature/autonomous-live-trading-platform` with RED -> GREEN -> exact-head CI for every behavior slice.

**Goal:** Give every selected US-equity symbol truthful multi-timeframe charts and surface the existing/finalized Context Intelligence evidence on the Chinese Trading Console.

**Spec:** `docs/superpowers/specs/2026-08-31-market-chart-context-dashboard-design.md`

## Global constraints

- No fabricated equity history, support/resistance, news, government events, or translations.
- Credentials stay server-side.
- IEX is labeled single-exchange; SIP only when actually used.
- Freshness/latency/source are visible.
- GET/read-only additions cannot create execution authority.
- Context does not bypass promotion or deterministic risk.
- PR #8 remains Draft.

### Task 1 — Historical equity bars client

Files:
- Create `app/market/alpaca_history.py`
- Test `tests/test_alpaca_historical_bars.py`

Contracts:
- validate symbol/timeframe/limit;
- call official single-stock historical bars REST with APCA headers and configured feed;
- normalize `1Day`, `1Week`, `1Month` responses into repository candle shape;
- support injected transport for deterministic tests;
- provider errors/malformed payloads fail explicitly, never generate fallback stock bars.

### Task 2 — Derived support/resistance levels

Files:
- Create `app/market/levels.py`
- Test `tests/test_market_levels.py`

Contracts:
- confirmed pivot methodology;
- nearest support below/equal latest close and resistance above/equal latest close;
- deterministic fallback to lookback extrema;
- insufficient history returns missing values;
- methodology/lookback/pivot width retained.

### Task 3 — Read-only market-history API

Files:
- Create `app/api/market_history.py`
- Modify `app/api/main.py`
- Modify `app/api/state.py` only if runtime ownership is required
- Test `tests/test_market_history_api.py`

Contracts:
- `GET /api/market/history/{symbol}`;
- only allowed/configured symbols;
- `1Day|1Week|1Month` only for historical provider;
- no credentials/provider -> explicit unavailable response;
- response includes candles, source, coverage, levels, generated timestamp;
- no POST/write counterpart.

### Task 4 — Xueqiu-inspired multi-timeframe chart UI

Files:
- Modify `app/web/index.html`
- Create `app/web/advanced-market-chart.js`
- Modify `app/web/backend-actions.js`
- Modify `app/web/app.js` minimally to delegate chart updates
- Modify `app/web/styles.css`
- Modify `scripts/build_static_site.py` as required
- Test `tests/test_trading_dashboard_contract.py`
- Test `tests/test_dashboard_assets.py`
- Test `tests/test_symbol_switching_dashboard.py`

Contracts:
- Chinese buttons `分时 / 日K / 周K / 月K`;
- actual timeframe requests change;
- candlestick + volume + MA20 + MA60;
- support/resistance price lines labeled `算法支撑` / `算法压力`;
- selected symbol drives chart;
- websocket only updates intraday view;
- empty/error reason visible rather than blank panel;
- source/feed coverage visible.

### Task 5 — Finish Context Intelligence runtime service

Files:
- Create `app/intelligence/service.py`
- Modify `app/api/state.py`
- Modify `app/settings.py`
- Modify `.env.example`
- Test `tests/test_context_intelligence_runtime.py`

Contracts:
- persistent `SQLiteContextStore`;
- Alpaca realtime news loop when credentials/config enable it;
- SEC delta polling;
- isolated source health/failure counts/retry state;
- source failures do not crash trading runtime;
- snapshot assembly uses existing typed evidence/freshness.

### Task 6 — Government/regulatory official-source adapter

Files:
- Create `app/intelligence/government.py`
- Test `tests/test_government_context.py`

Contracts:
- official Federal Register-compatible source;
- publication/effective dates kept distinct;
- deterministic topic -> configured symbol/theme mapping;
- no symbol assignment when mapping confidence/rule absent;
- official-current/delayed freshness semantics, never falsely realtime.

### Task 7 — Read-only intelligence API

Files:
- Create `app/api/intelligence.py`
- Modify `app/api/main.py`
- Test `tests/test_context_intelligence_api.py`

Contracts:
- `GET /api/intelligence/{symbol}`;
- `GET /api/intelligence/status`;
- unknown symbol fail closed;
- no secrets in payload;
- flow context built from exact current market structure/coverage;
- no POST/write method.

### Task 8 — Deterministic Chinese synthesis

Files:
- Create `app/intelligence/synthesis.py`
- Modify `app/intelligence/service.py`
- Test `tests/test_context_synthesis.py`

Contracts:
- official current facts outrank inference;
- stale/delayed evidence down-weighted;
- contradictory evidence reduces confidence;
- output is Chinese text/flags/confidence only;
- no order/execution types.

### Task 9 — Chinese Context Intelligence homepage panel

Files:
- Modify `app/web/index.html`
- Modify `app/web/backend-actions.js`
- Create `app/web/context-intelligence.js`
- Modify `app/web/styles.css`
- Modify static build asset list
- Test dashboard/static contracts

Contracts:
- `综合情报`, `实时新闻`, `SEC / 公司披露`, `政府 / 监管`, `资金行为`, `新鲜度`;
- follows selected symbol;
- shows published/updated/ingested age and source;
- Chinese freshness names;
- `FACT / DERIVED / INFERENCE / HYPOTHESIS` visibly separated;
- missing = `暂无可验证信息`;
- `仅供上下文，不代表交易许可` visible.

### Task 10 — Selected-symbol audit coherence

Files:
- Modify `app/web/app.js` or focused audit module
- Test dashboard contract

Contracts:
- selected-symbol audit chain does not silently show BTCUSDT events as KLAC/NVDA/SPCX evidence;
- system-wide events may remain visible only when explicitly labeled `全局`.

### Task 11 — Durable direction/status/provenance

Files:
- Modify `PROJECT_DIRECTION.md`
- Modify `STATUS.md`
- Create/update `docs/upstream/2026-08-31-market-chart-context-sources.md`

Record:
- Xueqiu interaction inspiration only, no code reuse;
- official Alpaca historical timeframe/coverage facts;
- Context Intelligence freshness/source rules;
- current limitations and required runtime credentials.

### Task 12 — Full verification

- targeted chart/history/context tests;
- `python -m ruff check .`;
- full pytest Python 3.12 and 3.13 exact-head CI;
- `python -m compileall -q app`;
- dependency audit / engineering skill verification required by workflow;
- Docker build;
- PR #8 remains Draft.
