# Cloud Observatory Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a safe static cloud K-line dashboard while preserving the existing private FastAPI observatory.

**Architecture:** Introduce an explicit browser runtime configuration, isolate market-source behavior behind a small client adapter, and generate a GitHub Pages-ready `site/` directory from shared assets. Static mode uses only public market data and deterministic replay fallback; backend mode retains existing APIs.

**Tech Stack:** Python 3.12+, FastAPI, vanilla JavaScript, TradingView Lightweight Charts, GitHub Actions/Pages, pytest.

## Global Constraints

- Live trading remains disabled.
- Static mode performs no authenticated or write-capable requests.
- No credentials, account identifiers, cookies, or private keys enter generated browser assets.
- Mainland China securities markets remain excluded.
- Public claims must preserve evidence provenance and confidence grading.

---

### Task 1: Runtime Mode Contract

**Files:**
- Create: `app/web/runtime.js`
- Modify: `app/web/index.html`
- Test: `tests/test_dashboard_assets.py`

**Interfaces:**
- Produces: `window.ObservatoryRuntime.resolve(config)` returning a frozen runtime descriptor with `mode`, `apiBase`, `market`, and capability flags.
- Consumes: optional `window.OBSERVATORY_CONFIG` supplied before `runtime.js` loads.

- [ ] Write assertions that the dashboard loads `config.js` and `runtime.js`, exposes static labels, and defaults to backend mode when no config is supplied.
- [ ] Run `python -m pytest tests/test_dashboard_assets.py -q` and verify failure.
- [ ] Implement the runtime descriptor and update script ordering in `index.html`.
- [ ] Run the targeted test and verify pass.
- [ ] Commit with `feat: add explicit dashboard runtime modes`.

### Task 2: Static Market Adapter and Replay Fallback

**Files:**
- Create: `app/web/market-client.js`
- Modify: `app/web/app.js`
- Test: `tests/test_dashboard_assets.py`

**Interfaces:**
- Produces: `window.ObservatoryMarketClient.create(runtime)` with `loadHistory()` and `connect(onCandle, onStatus)`.
- Consumes: the runtime descriptor from Task 1.

- [ ] Add tests asserting public Binance endpoints, bounded reconnect behavior, deterministic fallback, and absence of authenticated headers.
- [ ] Run the targeted test and verify failure.
- [ ] Implement backend and static adapters; route all candle history and streaming through the adapter.
- [ ] Disable order/research actions when capabilities are false and show a visible observe-only state.
- [ ] Run the targeted test and verify pass.
- [ ] Commit with `feat: add public static market observer`.

### Task 3: Reproducible Static Site Build

**Files:**
- Create: `scripts/build_static_site.py`
- Create: `tests/test_static_site_build.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `build_static_site(source_root: Path, output_root: Path) -> None`.
- Output: `site/index.html`, `site/styles.css`, `site/runtime.js`, `site/market-client.js`, `site/app.js`, `site/config.js`, `site/demo-data.js`, and `.nojekyll`.

- [ ] Write a test building into a temporary directory and asserting relative asset paths, static mode config, no secrets, and disabled write capabilities.
- [ ] Run `python -m pytest tests/test_static_site_build.py -q` and verify failure.
- [ ] Implement the build function and CLI.
- [ ] Run the targeted test and verify pass.
- [ ] Commit with `build: generate static observatory site`.

### Task 4: GitHub Pages Delivery

**Files:**
- Create: `.github/workflows/pages.yml`
- Modify: `README.md`
- Test: `tests/test_operations_assets.py`

**Interfaces:**
- Workflow builds `site/` and uploads it with `actions/upload-pages-artifact` before `actions/deploy-pages`.
- README documents the expected Pages URL and the distinction between static observe-only and private backend modes.

- [ ] Add workflow-asset assertions for permissions, build command, artifact path, and deployment environment.
- [ ] Run `python -m pytest tests/test_operations_assets.py -q` and verify failure.
- [ ] Add the Pages workflow and documentation.
- [ ] Run the targeted test and verify pass.
- [ ] Commit with `ci: deploy observe-only dashboard to pages`.

### Task 5: Release Verification and Source Publication

**Files:**
- Modify: `scripts/loop_verify.sh`
- Modify: `docs/VERIFICATION.md`
- Create: `docs/reviews/2026-08-06-cloud-observatory-review.md`

**Interfaces:**
- Verification builds the static site, scans it for secret-like tokens and write endpoints, then runs backend startup probes.

- [ ] Extend verification assertions and run them before implementation to observe failure.
- [ ] Add static build and safety scans to `loop_verify.sh`.
- [ ] Run targeted tests, full tests, static checks, compile checks, and three consecutive loop verification runs.
- [ ] Review the diff against repository standards and the design specification; record both axes.
- [ ] Publish the complete verified source to the GitHub feature branch, open a draft PR, and verify remote files and CI status.
- [ ] Commit with `chore: verify cloud observatory release`.
