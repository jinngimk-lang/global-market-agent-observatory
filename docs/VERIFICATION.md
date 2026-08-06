# Verification

The release gate is `scripts/loop_verify.sh`. It performs:

1. Shell syntax validation for operational and agent-skill bootstrap scripts.
2. Upstream catalog validation, including disabled-by-default policy.
3. A reproducible static-site build into `site/`.
4. Static bundle checks for secret-like tokens, backend write endpoints, POST requests, and backend-only assets.
5. Python bytecode compilation for `app/` and `scripts/`.
6. Ruff linting when available, with an offline AST/static fallback.
7. The complete pytest suite, including Node-backed browser runtime tests when Node is available.
8. Fail-closed validation that live trading cannot be enabled.
9. A real HTTP smoke test of the static dashboard.
10. A live Uvicorn smoke test against `/api/health`.
11. An optional Docker build when `LOOP_VERIFY_DOCKER=1` and Docker is available.

## Release evidence — 2026-08-06

The finalized cloud-observatory branch completed three consecutive clean verification runs:

| Round | Tests | Static bundle scan | Static HTTP probe | Backend health probe | Safety state |
|---|---:|---|---|---|---|
| 1 | 44 passed | passed | passed | passed | paper; live disabled |
| 2 | 44 passed | passed | passed | passed | paper; live disabled |
| 3 | 44 passed | passed | passed | passed | paper; live disabled |

Additional release checks:

- `node --check` passed for the shared browser modules.
- Deterministic replay history and streaming candles were exercised in a Node VM.
- The generated Pages bundle contains no backend order or research-refresh endpoint and no backend action module.
- The generated Pages index includes a restrictive content security policy for the required chart CDN and public market endpoints.
- Dynamic evidence grades are inserted with `textContent`, not HTML interpolation.
- The editable package import and bare `pytest` invocation both pass from the repository root.

Docker configuration and CI image build steps are present, but the current execution environment does not provide a Docker daemon. The container image was therefore not built locally; the repository CI remains responsible for that build.
