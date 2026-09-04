# Real-Time Context Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only, provenance-preserving, freshness-aware Context Intelligence Layer for each trading-universe symbol using streaming/official sources first, then expose it in the Trading Console without granting it execution authority.

**Architecture:** Normalize all external context into immutable typed evidence with source-specific freshness semantics. `ApplicationState` owns source loops and a persistent recent-event store; read-only APIs expose snapshots/status; the dashboard renders current news, SEC filings, government/regulatory developments, flow evidence, and an explicitly non-executable synthesis.

**Tech Stack:** Python 3.12/3.13, Pydantic, FastAPI, httpx, websockets, SQLite, vanilla JS dashboard, pytest.

**Spec:** `docs/superpowers/specs/2026-08-26-context-intelligence-design.md`

## Global Constraints

- Freshness is part of truth; delayed sources never masquerade as realtime.
- Prefer official/first-party and streaming sources.
- IEX coverage must be labeled single-exchange; SIP only when actually configured/available.
- Missing context is `NO VERIFIED DATA`, never zero or guessed.
- Context is read-only evidence; it cannot create `OrderIntent` or bypass promotion/risk.
- No secrets are committed; credentials come from runtime settings only.
- Every behavior change follows RED -> GREEN -> full CI.

---

### Task 1: Context evidence models and freshness policy

**Files:**
- Create: `app/intelligence/__init__.py`
- Create: `app/intelligence/models.py`
- Create: `app/intelligence/freshness.py`
- Test: `tests/test_context_intelligence_models.py`

**Interfaces:**
- Produces `EvidenceKind`, `FreshnessClass`, `ContextSource`, `ContextItem`, `SymbolContextSnapshot`.
- Produces `classify_freshness(item, now) -> FreshnessClass`.

- [ ] Write failing tests for UTC normalization, realtime/near-realtime/stale transitions, delayed-source hard classification, and negative-latency flagging.
- [ ] Run `pytest tests/test_context_intelligence_models.py -q` and verify RED because models/functions do not exist.
- [ ] Implement minimal immutable Pydantic models and source-specific freshness calculation.
- [ ] Re-run targeted test and verify GREEN.
- [ ] Commit.

### Task 2: Persistent recent-event store and deduplication

**Files:**
- Create: `app/intelligence/store.py`
- Test: `tests/test_context_intelligence_store.py`

**Interfaces:**
- `SQLiteContextStore(path)`
- `upsert(item: ContextItem) -> None`
- `recent(symbol: str, category: str | None, limit: int) -> list[ContextItem]`
- `latest_provider_event(provider: str) -> datetime | None`

- [ ] Write RED tests proving stable provider ids deduplicate updates and restart preserves recent verified evidence.
- [ ] Verify RED.
- [ ] Implement minimal SQLite schema/upsert/query with JSON model payloads.
- [ ] Verify targeted GREEN.
- [ ] Commit.

### Task 3: Alpaca real-time news normalization

**Files:**
- Create: `app/intelligence/alpaca_news.py`
- Test: `tests/test_alpaca_news_stream.py`

**Interfaces:**
- `AlpacaNewsStream(symbols, api_key, api_secret, connect=None)`
- `stream() -> AsyncIterator[ContextItem]`

- [ ] Write RED tests for auth/subscribe, symbol filtering, provider id, timestamps, publisher URL, realtime freshness policy, disconnect cleanup, and non-news frame ignore behavior.
- [ ] Verify RED.
- [ ] Implement minimal WebSocket adapter for `wss://stream.data.alpaca.markets/v1beta1/news`.
- [ ] Verify targeted GREEN.
- [ ] Commit.

### Task 4: SEC near-real-time filing adapter

**Files:**
- Create: `app/intelligence/sec.py`
- Test: `tests/test_sec_context.py`

**Interfaces:**
- `SecSubmissionClient(user_agent, transport=None)`
- ticker/CIK mapping cache
- `fetch_recent(symbol, since_accession=None) -> list[ContextItem]`

- [ ] Write RED tests for 8-K/10-Q/10-K normalization, accession-number dedupe key, official-source flag, filed timestamp, symbol mapping, and malformed/missing CIK fail-closed behavior.
- [ ] Verify RED.
- [ ] Implement minimal SEC submissions client using `data.sec.gov`, explicit User-Agent, bounded timeout, and no authentication.
- [ ] Verify targeted GREEN.
- [ ] Commit.

### Task 5: Flow context adapter from existing trusted market structure

**Files:**
- Create: `app/intelligence/flow.py`
- Test: `tests/test_flow_context.py`

**Interfaces:**
- `build_flow_context(symbol, structure, coverage, now) -> list[ContextItem]`

- [ ] Write RED tests proving VWAP/OFI/GEX/walls retain `derived` type, methodology/provenance, and freshness; missing metrics are omitted instead of zero-filled.
- [ ] Verify RED.
- [ ] Implement conversion from existing market-structure/coverage truth.
- [ ] Verify targeted GREEN.
- [ ] Commit.

### Task 6: Context service and source health

**Files:**
- Create: `app/intelligence/service.py`
- Modify: `app/api/state.py`
- Modify: `app/settings.py`
- Modify: `.env.example`
- Test: `tests/test_context_intelligence_runtime.py`

**Interfaces:**
- `ContextIntelligenceService.snapshot(symbol) -> SymbolContextSnapshot`
- background news stream and SEC delta polling
- source-health reports with last event/success/error/retry/freshness.

- [ ] Write RED tests for source-loop isolation, stale expiration, restart recovery, per-symbol snapshot assembly, and disabled/unconfigured providers.
- [ ] Verify RED.
- [ ] Implement runtime wiring with live-capital permissions unchanged.
- [ ] Verify targeted GREEN.
- [ ] Commit.

### Task 7: Read-only intelligence API

**Files:**
- Create: `app/api/intelligence.py`
- Modify: `app/api/main.py`
- Test: `tests/test_context_intelligence_api.py`

**Interfaces:**
- `GET /api/intelligence/{symbol}`
- `GET /api/intelligence/status`

- [ ] Write RED API tests for configured universe symbols, unknown symbol 404, source status, no-secret response, and absence of POST/write methods.
- [ ] Verify RED.
- [ ] Implement router.
- [ ] Verify targeted GREEN.
- [ ] Commit.

### Task 8: Government/regulatory official-source adapter

**Files:**
- Create: `app/intelligence/government.py`
- Test: `tests/test_government_context.py`

**Interfaces:**
- `GovernmentContextClient` with official-source records and deterministic topic/symbol mapping rules.

- [ ] Write RED tests proving publication/effective dates are distinct, official source is retained, delayed publication is never labeled realtime, and unmapped documents are not silently assigned to a stock.
- [ ] Verify RED.
- [ ] Implement first Federal Register/GovInfo-compatible metadata adapter with injected HTTP transport for deterministic tests.
- [ ] Verify targeted GREEN.
- [ ] Commit.

### Task 9: Trading Console context panel

**Files:**
- Modify: `app/web/index.html`
- Modify: `app/web/backend-actions.js`
- Create: `app/web/context-intelligence.js`
- Modify: `app/web/styles.css`
- Modify: `scripts/build_static_site.py` if needed to preserve observe-only behavior
- Test: `tests/test_trading_dashboard_contract.py`
- Test: `tests/test_dashboard_assets.py`

**Interfaces:**
- Reads only `/api/intelligence/{symbol}` and `/api/intelligence/status`.
- Follows current symbol switcher.

- [ ] Write RED dashboard contract for realtime news, SEC, government, flow, freshness strip, `FACT/DERIVED/INFERENCE/HYPOTHESIS`, `NO VERIFIED DATA`, and non-executable warning.
- [ ] Verify RED.
- [ ] Implement compact context panel; sort newest first; show age/source/freshness/coverage.
- [ ] Verify targeted GREEN.
- [ ] Commit.

### Task 10: Synthesis and confidence without execution authority

**Files:**
- Create: `app/intelligence/synthesis.py`
- Modify: `app/intelligence/service.py`
- Test: `tests/test_context_synthesis.py`

**Interfaces:**
- deterministic evidence-weighted synthesis for initial version; output text/flags/confidence only.

- [ ] Write RED tests proving stale/delayed evidence is down-weighted, official current facts outrank inference, contradictory evidence reduces confidence, and no `OrderIntent`/execution type is produced.
- [ ] Verify RED.
- [ ] Implement minimal deterministic synthesis.
- [ ] Verify targeted GREEN.
- [ ] Commit.

### Task 11: Durable direction/status/provenance

**Files:**
- Modify: `PROJECT_DIRECTION.md`
- Modify: `STATUS.md`
- Create: `docs/upstream/2026-08-26-context-intelligence-sources.md`

- [ ] Record official source capabilities and latency/coverage caveats: Alpaca realtime stock/news WebSockets, IEX-vs-SIP coverage, SEC submissions/XBRL update cadence, Federal Register/GovInfo publication cadence, FINRA daily short-volume delayed semantics.
- [ ] Add `Freshness is part of truth` and Context Intelligence Layer to the durable project direction.
- [ ] Update immediate queue and blockers.
- [ ] Commit.

### Task 12: Full verification

- [ ] Run targeted context tests.
- [ ] Run full `python -m ruff check .`.
- [ ] Run full `python -m pytest -q` on Python 3.12 and 3.13 via exact-head CI.
- [ ] Verify `python -m compileall -q app`.
- [ ] Verify Docker build.
- [ ] Keep PR #8 Draft unless strategy/operational evidence independently justifies promotion.
