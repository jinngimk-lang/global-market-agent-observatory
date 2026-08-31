# Multi-Timeframe Market Chart + Chinese Context Dashboard Design

## Goal

Upgrade the Trading Console so each configured US-equity symbol has a useful, truthful chart and a Chinese Context Intelligence panel. The design is inspired by the interaction model of mainstream stock pages such as Xueqiu (intraday plus day/week/month switching), but no Xueqiu code, visual assets, or proprietary styling are copied.

## User-visible outcome

For `NVDA`, `KLAC`, `SPCX`, and future configured symbols, the selected-symbol area provides:

- `分时` / `日K` / `周K` / `月K` switching;
- real candlesticks from the matching provider timeframe;
- volume histogram;
- MA20 and MA60 overlays when enough verified bars exist;
- derived algorithmic support and resistance levels with methodology/source disclosure;
- explicit source/feed coverage and a visible no-data state;
- a Chinese `综合情报` panel containing realtime news, SEC/company filings, government/regulatory events, observable capital-flow/market-structure evidence, and per-source freshness/latency.

## Truth constraints

1. A period selector must change the actual requested timeframe, not only the title.
2. Daily/weekly/monthly history must not be fabricated by stretching the local 1-minute replay database. For equities, verified higher-timeframe history comes from a reviewed server-side market-data provider.
3. Alpaca credentials stay server-side. They are never sent to browser JavaScript.
4. If higher-timeframe history is unavailable, the UI renders `无可验证历史数据` and the reason; it does not synthesize bars.
5. Support/resistance are `DERIVED` algorithmic estimates, never promises or trade instructions.
6. Missing MA/support/resistance values remain absent rather than zero-filled.
7. Context Intelligence is read-only evidence and cannot create `OrderIntent` or bypass promotion/risk.
8. Freshness is part of truth. Delayed official datasets are not labeled realtime merely because they were fetched recently.
9. Audit/context from another symbol must not silently look like selected-symbol evidence. Selected-symbol views filter by symbol or visibly label global/system events.

## Market-history architecture

Add a server-side historical market client using Alpaca Stock Historical Data REST for US equities. Supported UI periods map to provider timeframes:

- `分时` -> local/realtime `1m` candles already persisted by the running feed;
- `日K` -> Alpaca `1Day`;
- `周K` -> Alpaca `1Week`;
- `月K` -> Alpaca `1Month`.

The new read-only endpoint is:

`GET /api/market/history/{symbol}?timeframe=1Day|1Week|1Month&limit=N`

Response includes symbol, timeframe, source, feed/coverage, generated time, normalized candles, and derived levels. Only configured/allowed symbols may be queried. Missing credentials/provider failure returns an explicit unavailable response/error; it never falls back to fake equity history.

## Support / resistance methodology

The first deterministic display methodology uses confirmed price pivots over verified historical bars:

- swing low: a bar whose low is lower than its neighboring bars in the configured pivot window;
- swing high: analogous high pivot;
- support: nearest confirmed swing-low level at or below the latest close;
- resistance: nearest confirmed swing-high level at or above the latest close;
- fallback, only when no qualifying pivot exists: lookback minimum low / maximum high;
- methodology, lookback, pivot width, observation count, and computed-at time are returned with the values.

These are chart reference levels only. A strategy may not consume them until introduced through a versioned, replayable strategy-input contract and promotion evidence.

## Chart architecture

Add a focused browser module rather than expanding the already-large dashboard controller. It owns:

- candlestick series;
- volume histogram;
- MA20/MA60 line series;
- support/resistance price lines;
- period buttons and loading/empty/error state;
- source/coverage legend.

Realtime WebSocket updates only mutate the active `分时` view. Higher-timeframe views remain historical snapshots and are refreshed explicitly/periodically rather than being mutated by a 1-minute event with incompatible semantics.

## Context Intelligence architecture

Finish the existing Context Intelligence plan rather than creating a competing subsystem:

- `app/intelligence/service.py`: snapshot assembly, source health, news/SEC/government source-loop isolation;
- `app/intelligence/government.py`: official government/regulatory records with deterministic symbol/theme mapping;
- `app/api/intelligence.py`: read-only `GET /api/intelligence/{symbol}` and `GET /api/intelligence/status`;
- existing `alpaca_news.py`, `sec.py`, `flow.py`, `freshness.py`, `models.py`, and `store.py` remain the canonical evidence layer.

Initial source tiers:

- Alpaca News WebSocket: realtime/near-realtime;
- SEC submissions: official near-realtime filings;
- Federal Register / selected agency official publications: official-current, not falsely streaming;
- existing market structure / coverage: realtime-derived flow only while market data remains fresh;
- future FINRA daily/off-exchange evidence: explicitly delayed (`D-1`) and never used to satisfy minute-level freshness.

## Chinese dashboard

The new full-width `综合情报` section follows the selected symbol and contains:

- `新鲜度` strip: 行情 / 新闻 / SEC / 政府监管 / 资金行为;
- `实时新闻`: original source headline, Chinese evidence/freshness/source labels, published/update/ingest age;
- `SEC / 公司披露`: form, filed time, official source link/reference;
- `政府 / 监管`: agency, publication/effective time, mapped theme/symbol, official badge;
- `资金行为`: VWAP, OFI, GEX proxy, put/call wall and feed coverage with methodology/provenance;
- `综合判断`: deterministic, evidence-citing Chinese synthesis with confidence and `仅供上下文，不代表交易许可` warning.

Original English headlines may remain verbatim unless a separately verified translation capability is added; the UI around them is Chinese so the system does not invent translations.

## Failure behavior

- no equity minute feed -> selected equity chart shows no verified intraday data;
- no historical provider credentials -> day/week/month view reports provider unavailable;
- source disconnect -> retain last verified item as history while freshness expires naturally;
- source error -> source health becomes degraded without crashing the trading loop;
- stale flow -> excluded from current synthesis weighting;
- no verified context -> `NO VERIFIED DATA / 暂无可验证信息`.

## Safety

The market-history and intelligence endpoints are GET-only. This work does not enable automatic execution, change strategy maturity, change risk limits, or grant live-capital permission. Existing order path remains `StrategySignal -> OrderIntent -> deterministic RiskDecision -> ExecutionAdapter -> reconciliation`.

## Durable direction

`PROJECT_DIRECTION.md` must treat truthful multi-timeframe market context and freshness-aware official/news context as first-class observability of the trading system. The invariant remains: context proposes evidence; strategies propose trades; deterministic risk decides capital.
