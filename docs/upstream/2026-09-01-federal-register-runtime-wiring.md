# Federal Register runtime wiring

Date: 2026-09-01
Branch: `feature/autonomous-live-trading-platform`
PR: `#8`

## Why this change exists

The repository already contained a read-only `FederalRegisterClient`, polling support in `ContextIntelligenceService`, SQLite context persistence/deduplication, source-health/freshness reporting, and dashboard/API rendering for government context. The missing link was runtime composition: `ApplicationState` never instantiated or injected the client, and `Settings` exposed no explicit per-symbol government-topic mapping.

That meant the code for the provider existed while `/api/intelligence/status` correctly reported `federal-register` as unconfigured at runtime.

## RED evidence

Commit `b9ce7bf0e78ab079fabddca067d9deb21b41ff1d` added two boundary contracts in `tests/test_government_runtime_wiring.py`:

1. `CONTEXT_GOVERNMENT_TERMS` must parse into explicit per-symbol search terms.
2. `ApplicationState` with Context Intelligence enabled must inject a real `FederalRegisterClient`, making `federal-register` configured.

CI `#789` produced exactly `317 passed, 2 failed`. Ruff, dependency audit, and Docker remained healthy. The two failures were the intended boundaries: missing `Settings.context_government_terms` and a `None` runtime `government_client`.

## GREEN implementation

The runtime now has an explicit, reviewable mapping contract:

```text
CONTEXT_GOVERNMENT_TERMS="NVDA=NVIDIA|advanced computing|semiconductor|export control;KLAC=KLA|semiconductor equipment|advanced computing|export control;SPCX=SpaceX|Starlink|commercial space"
```

The built-in initial map covers only the current primary universe:

- `NVDA`: NVIDIA, advanced computing, semiconductor, export control
- `KLAC`: KLA, semiconductor equipment, advanced computing, export control
- `SPCX`: SpaceX, Starlink, commercial space

Unknown/unmapped symbols are not assigned inferred policy topics. `FederalRegisterClient.fetch_recent()` raises `LookupError` for an unmapped symbol and the polling service skips it.

`ApplicationState` creates the Federal Register client only when Context Intelligence is enabled and the explicit topic map is non-empty. With Context Intelligence disabled, the source remains fail-closed as `configured=false` and no Federal Register client is created.

The existing `ContextIntelligenceService` then owns the rest of the path:

`FederalRegisterClient -> 300s government poll -> ContextItem normalization -> SQLiteContextStore upsert/dedupe -> freshness/source health -> /api/intelligence/{symbol} + /api/intelligence/status -> Chinese government/regulatory panel`

No broker credential, strategy permission, execution permission, or live-capital gate is introduced by this source.

## Source authority boundary

FederalRegister.gov is used as a timely search/metadata interface. It explicitly states that its web presentation is not the official legal edition of the Federal Register. Normalized items therefore retain the existing metadata caveat `legal_status=verify-official-edition-on-govinfo`; legal authority must be verified against GovInfo when material.

No Federal Register source code was copied and no new runtime dependency was added.

## Verification

Implementation commits:

- `c3f95a465fd042e6002fd6adddcda49396db697e` — settings + explicit government topic mapping
- `0de5d5cd157d5178cdcfd1ede7b82e386ebc5402` — `FederalRegisterClient` runtime injection
- `bed2ea797a246050483044d6bdf94eff032b06f5` — `.env.example` mapping contract

Diff audit from RED head `b9ce7bf0...` to behavior/doc head `bed2ea797...` showed only three intended files changed, with 59 additions and zero deletions.

CI `#795` completed successfully. Python 3.12 full pytest reported `319 passed, 1 warning`; Python 3.13 also passed the full suite. Ruff, compileall, engineering-skill verification, dependency audit, and Docker build all completed successfully.

The remaining warning is the pre-existing FastAPI/Starlette TestClient deprecation warning and is unrelated to this change.
