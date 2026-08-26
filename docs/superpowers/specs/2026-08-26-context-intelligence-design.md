# Real-Time Context Intelligence Design

## Goal

Add a read-only Context Intelligence Layer that combines current company/news, official filings, government/regulatory developments, and observable capital-flow evidence for each configured symbol, while preserving the invariant that context never bypasses strategy promotion or deterministic risk.

## Product requirement

The console must optimize for **new, fast, accurate** information. Freshness is part of truth: every item carries source, provider timestamp, ingestion timestamp, latency class, freshness SLA, evidence type, confidence, and expiry semantics. Data that is delayed by nature must be labeled as delayed and must not be blended into minute-level real-time state as if it were current.

## Source classes and latency semantics

### Tier A — streaming / near-real-time

- Alpaca stock market WebSocket for price/volume/market context.
- Alpaca real-time news WebSocket for symbol-tagged news.
- SEC EDGAR submissions API for new filings; submissions are treated as near-real-time official disclosures.

Target display state: `REALTIME` or `NEAR-REALTIME` only while the item remains inside the source-specific freshness SLA.

### Tier B — official event sources with publication latency

- Federal Register / GovInfo official federal publications.
- SEC rules/releases and other official agency publications where relevant.
- Commerce/BIS and other official agency sources for semiconductor/export-control risk when integrated.

Target display state: `OFFICIAL-CURRENT` with the actual published/updated timestamp. These sources are not labeled streaming unless the upstream source actually pushes events.

### Tier C — delayed structural evidence

- FINRA daily short-sale volume and future off-exchange/ATS datasets.
- Institutional/ETF filings whose source cadence is daily, weekly, monthly, or quarterly.

Target display state: explicit delay label such as `D-1`; these items can provide background context but cannot satisfy minute-level freshness or live execution data requirements.

## Accuracy hierarchy

When sources disagree, rank evidence by:

1. first-party official filing/regulatory source;
2. first-party exchange/broker market-data source with known coverage;
3. reputable original news publisher via documented provider feed;
4. derived metric with reproducible methodology;
5. model inference;
6. hypothesis.

The UI must visually separate `FACT`, `DERIVED`, `INFERENCE`, and `HYPOTHESIS`.

## Coverage honesty

Fast does not imply complete. Alpaca IEX is a single-exchange feed; SIP is consolidated US-market coverage when the account/subscription permits it. The dashboard must display the active feed and coverage class. It must never describe IEX as full consolidated US market coverage.

## Core models

Create `app/intelligence/models.py` with immutable models:

- `EvidenceKind`: `fact`, `derived`, `inference`, `hypothesis`.
- `FreshnessClass`: `realtime`, `near-realtime`, `official-current`, `delayed`, `stale`, `unknown`.
- `ContextSource`: provider id, source type, official flag, coverage description, source URL where safe.
- `ContextItem`: id, symbol(s), headline/label, summary, event time, published time, ingested time, freshness SLA seconds, computed age/latency metadata, evidence kind, confidence, tags, source.
- `SymbolContextSnapshot`: symbol, generated_at, news, filings, government, flow evidence, aggregate flags, and a non-executable textual synthesis.

No model contains an order intent or execution method.

## Runtime architecture

Add focused modules:

- `app/intelligence/alpaca_news.py`: Alpaca real-time news stream normalization and reconnect-safe event ingestion.
- `app/intelligence/sec.py`: SEC company-CIK mapping plus submissions polling with conditional/delta fetch.
- `app/intelligence/government.py`: official government publication adapter interface; first implementation uses official Federal Register/GovInfo metadata and preserves publication latency.
- `app/intelligence/flow.py`: converts already-trusted market structure/coverage plus later FINRA data into typed flow context without inventing a single opaque "main fund flow" score.
- `app/intelligence/service.py`: deduplication, freshness evaluation, per-symbol snapshot assembly, and source health.
- `app/intelligence/store.py`: bounded persistent recent-event store for deduplication and restart recovery.

`ApplicationState` owns the service and background tasks. Source failures must not crash the trading process; they update source-health state and make the affected context stale/unavailable.

## API

Add read-only endpoints:

- `GET /api/intelligence/{symbol}` — latest snapshot for one symbol.
- `GET /api/intelligence/status` — source health, last event, last successful fetch/stream message, failure count, retry state, coverage/feed class.

No write/control endpoint is added.

## Dashboard

For the currently selected symbol, render:

- `实时新闻` — newest first, provider/publisher, age, symbol relevance, FACT/INFERENCE badge.
- `SEC/公司披露` — form type, filed time, official link/reference, age.
- `政府/监管` — agency, document type, publication/effective date, affected theme/symbol mapping, official-source badge.
- `资金行为` — VWAP/OFI/options/GEX/volume evidence plus clearly delayed FINRA/off-exchange evidence when available.
- `综合情报` — concise synthesis that cites the supporting context items and shows confidence; it is explicitly labeled non-executable context.
- `Freshness strip` — Market / News / SEC / Government / Flow ages and states.

Missing data is shown as `NO VERIFIED DATA`, never as zero or a guessed value.

## Freshness policy

Freshness is source-specific rather than global.

Initial defaults:

- market streaming: source cadence-aware, generally seconds; existing market freshness rules remain authoritative for capital safety;
- Alpaca news: `realtime` while age <= 120 seconds, `near-realtime` <= 15 minutes, then current-history/stale by policy;
- SEC submissions: `near-realtime` while age <= 120 seconds from observed dissemination when available; older filings remain valid historical facts but lose real-time status;
- government publications: freshness is relative to official publication/update time; do not claim sub-minute real-time unless the upstream source provides it;
- FINRA daily short-sale volume: always delayed structural evidence, typically D-1, never `realtime`.

These are configurable policy defaults, not universal truths.

## Synthesis safety

The synthesis layer may summarize and classify evidence but cannot directly create `OrderIntent`. Any future strategy use of context must be introduced as a versioned strategy input with provenance, replayability, falsification criteria, promotion evidence, and deterministic-risk review.

## Failure handling

- Streaming source disconnect: bounded reconnect, failure count, last error, freshness expires naturally.
- Polling source failure: retain last verified item as historical fact but mark source status degraded/stale.
- Duplicate news/filing: deduplicate by stable provider id/accession number plus update timestamp.
- Clock anomalies: compute age from timezone-aware UTC timestamps; negative latency is clamped and flagged.
- Missing symbol mapping: retain source event globally but do not assign it to a symbol without an explicit mapping rule.

## Verification

Use TDD for models, freshness, dedupe, source normalization, API, and dashboard contracts. Add failure-injection for stream disconnect and stale-source behavior. Full Python 3.12/3.13 CI, Ruff, compileall, and Docker must pass before the feature is treated as complete.

## Durable direction update

`PROJECT_DIRECTION.md` must be updated to define Context Intelligence and the principle **Freshness is part of truth**, while preserving: context proposes evidence, strategies propose trades, deterministic risk decides capital.