# Python dependency vulnerability audit — 2026-08-29

## Upstream trigger

- Upstream: `nautechsystems/nautilus_trader`
- Commit: `26e2b143de667bcc2cf103600046c6f0bf2fccde`
- Date: 2026-08-29
- Upstream license: LGPL-3.0
- Upstream change: centralized Cargo, Python, OSV, and publication security checks behind a fail-closed audit policy.
- Reuse mode: behavioral principle only. No NautilusTrader source code was copied or adapted.

The upstream change highlighted a local supply-chain gap rather than an application-runtime defect: this repository's CI installed the Python project and development dependencies but did not query a vulnerability advisory database before treating an exact head as verified.

## Local gap

The project depends on FastAPI, Uvicorn, Pydantic, HTTPX, WebSockets, and optional/dev packages with transitive dependencies. Existing CI covered Ruff, pytest, compileall, engineering-skill presence, and the container build, but had no known-vulnerability gate for the resolved Python environment.

A dependency vulnerability can therefore enter through a direct or transitive package without causing tests or static checks to fail. This is especially relevant to a long-running broker-connected process with network-facing HTTP/WebSocket dependencies.

## Integration

CI now includes an independent `dependency-audit` job on Python 3.13. It installs the project plus development dependencies and a pinned `pip-audit==2.10.1`, then runs `python -m pip_audit --local` against the resolved environment.

`pip-audit` is maintained by the Python Packaging Authority and is licensed Apache-2.0. Version 2.10.1 is the current stable release observed during this integration and includes the OSV-record parsing fix released on 2026-06-10.

The audit tool is CI-only and is not added to the application runtime dependency set or container image. The pin makes the audit runner itself an explicit reviewed input instead of floating on every CI execution.

## Security and operating boundary

- The audit is advisory-database based; a clean result is not proof that dependencies are vulnerability-free.
- A newly disclosed vulnerability can make an unchanged exact head fail later. That is desired fail-closed behavior and must be triaged rather than silently ignored.
- Vulnerability ignores must not be added merely to restore green CI. Any exception requires an explicit rationale, affected-version analysis, compensating controls, expiry/review condition, and provenance.
- This change does not alter broker credentials, live-capital permission, deterministic risk, strategy promotion, execution behavior, or runtime network privileges.

## Rollback

The integration is isolated to the `dependency-audit` CI job and this provenance record. If the audit service/tool becomes unavailable or materially unreliable, replace it with a reviewed equivalent or temporarily remove the job through an explicit documented decision; do not weaken application safety gates as a workaround.
