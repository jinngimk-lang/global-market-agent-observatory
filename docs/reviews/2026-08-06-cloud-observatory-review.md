# Cloud Observatory Two-Axis Review

- Review date: 2026-08-06
- Fixed point: `a262342` (`docs: design cloud observatory delivery`)
- Reviewed range: `a262342...HEAD`
- Specification: `docs/superpowers/specs/2026-08-06-cloud-observatory-dashboard-design.md`
- Standards sources: `AGENTS.md`, `CONTEXT.md`, `docs/SECURITY.md`, and repository tests

## Standards

**Result: pass; no hard violations found.**

- Browser responsibilities are separated into focused modules: runtime resolution, market transport, backend-only write actions, and presentation.
- The static build omits `backend-actions.js` and scans the generated bundle for credentials, private endpoints, and write-capable requests.
- Public market failures degrade to bounded reconnect attempts and deterministic replay instead of silently stopping the chart.
- Evidence text is rendered through DOM text nodes; no researched grade value is interpolated into HTML.
- Live trading remains fail-closed in settings and is checked by the release gate.
- Tests cover backend compatibility, runtime capability selection, replay OHLC invariants, static generation, workflow assets, and real HTTP startup probes.

**Judgement calls:**

- The dashboard still uses a third-party chart library from `unpkg.com`. This is permitted by a narrow CSP and does not receive credentials, but a future production hardening task should vendor and integrity-pin the asset.
- Public Binance availability varies by network and jurisdiction. The visible replay fallback prevents a blank dashboard but must never be represented as live exchange data.

## Spec

**Result: pass; all acceptance requirements are represented.**

- Backend mode preserves FastAPI REST/WebSocket behavior and paper-only actions.
- Static mode uses only Binance public HTTPS/WebSocket market endpoints and local deterministic replay fallback.
- Static mode disables account refresh, research refresh, and order submission in both capability logic and generated source composition.
- The generated site uses relative assets, carries an observe-only label, and contains no secrets or account identifiers.
- GitHub Pages build and deployment workflow assets are present.
- Verification now builds and scans the static output, probes the static server, probes FastAPI, and repeats the full release loop.
- Mainland China securities are not introduced by this change.

## Summary

Standards findings: 0 hard violations, 2 documented hardening considerations. Spec findings: 0 missing, 0 partial, 0 scope-creep findings.
