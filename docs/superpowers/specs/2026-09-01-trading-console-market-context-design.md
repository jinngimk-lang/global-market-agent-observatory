# Trading Console Market Context Design

## Goal

Make the primary Trading Console useful as a stock decision surface for each configured US-equity symbol by combining verified multi-timeframe price history with provenance-aware Context Intelligence, while preserving the boundary that context and charts never grant execution permission.

## User-facing requirements

For NVDA, KLAC, SPCX, and future configured equities, the selected-symbol view must provide:

- 分时 / 日K / 周K / 月K;
- candlesticks plus volume;
- MA20 and MA60;
- algorithmic support and resistance levels derived from verified candles;
- current source/feed/coverage labeling;
- Chinese UI for real-time news, SEC/company filings, government/regulatory events, observable capital-flow evidence, and freshness/latency;
- the original provider headline/document title and source URL when available, so localization never replaces the source fact;
- explicit `NO VERIFIED DATA` when evidence is unavailable.

The interaction model is inspired by common Chinese stock terminals, including Xueqiu-style period switching, but no Xueqiu code, visual assets, or proprietary data are copied.

## Market chart architecture

The read-only historical endpoint is:

`GET /api/market/history/{symbol}?timeframe=1Min|1Day|1Week|1Month&limit=N`

For verified US-equity history the server uses Alpaca market-data credentials. The active feed and coverage class are returned with every payload. IEX is labeled single-exchange; SIP is labeled consolidated only when the configured feed is actually SIP.

Minute history may fall back to already-verified local runtime candles. Daily, weekly, and monthly views must not synthesize fake history from deterministic replay or silently aggregate an unrelated feed.

The chart renders:

- OHLC candlesticks;
- volume histogram;
- MA20 / MA60 from the displayed verified series;
- algorithmic support / resistance from pivot-based historical levels;
- source and coverage labels.

If the third-party Lightweight Charts CDN is unavailable, a first-party SVG renderer provides the same core periods, candlesticks, volume, moving averages, and support/resistance so CDN availability is not a single point of failure.

## Context Intelligence architecture

The selected-symbol read-only endpoints are:

- `GET /api/intelligence/{symbol}`
- `GET /api/intelligence/status`

The panel renders four evidence groups:

1. 实时新闻
2. SEC / 公司披露
3. 政府 / 监管
4. 资金行为

Every item retains evidence kind (`FACT`, `DERIVED`, `INFERENCE`, `HYPOTHESIS`), source identity, official-source flag, provider/publication timestamps, ingestion latency, and freshness state.

Freshness display states are bilingual and explicit:

- `REALTIME · 实时`
- `NEAR-REALTIME · 近实时`
- `OFFICIAL-CURRENT · 官方当前`
- `DELAYED · 延迟`
- `STALE · 已过期`

Delayed sources are never relabeled realtime merely because the application fetched them recently.

## Chinese localization policy

Interface labels, evidence categories, freshness explanations, source/latency labels, empty states, and deterministic synthesis are Chinese-first.

Source facts remain auditable: news and official documents preserve their original headline/title and source URL. A future machine-translation layer may add a clearly labeled Chinese translation, but it must never overwrite the original text or become the sole provenance record.

This preserves the project priority: **new, fast, accurate**. Accuracy outranks cosmetic translation.

## Symbol-following behavior

The chart and Context Intelligence controller initialize from the selected runtime symbol. A symbol switch reload or in-page decision-card change updates the selected symbol context. Stale async responses are generation-guarded so a slow prior-symbol request cannot overwrite a newer selection.

## Truth and safety invariants

- Missing market history is empty/unavailable, never fabricated.
- Missing context is `NO VERIFIED DATA`, never zero-filled.
- Support/resistance is labeled algorithmic, not predictive certainty.
- News/filings/regulation are context evidence, not trade signals by themselves.
- Context endpoints are GET-only.
- No dashboard component creates `OrderIntent`.
- Strategy promotion, deterministic risk, operator state, and live-capital gates remain unchanged.
- `AUTO_TRADING_ENABLED=false` and live-off defaults are unaffected by enabling read-only market/context observation.

## Verification

Required checks include:

- market-history API contracts for all four periods;
- Alpaca history normalization and coverage labeling;
- support/resistance calculation tests;
- advanced chart and CDN-blocked native fallback contracts;
- Context Intelligence API and Chinese dashboard contracts;
- static observe-only build asset completeness;
- Python 3.12 and 3.13 full test suite;
- Ruff, compileall, dependency audit, and Docker build.
