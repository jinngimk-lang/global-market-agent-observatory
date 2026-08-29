# Wheel-only third-party install policy — 2026-08-29

## Trigger

- Upstream: `nautechsystems/nautilus_trader`
- Commit: `338c28efd15085f28a97391972fe1a0f09718100`
- Date: 2026-08-29
- Commit signature: verified by GitHub
- License: LGPL-3.0
- Relevant upstream behavior: security checks keep a `no-build-package` policy aligned with the dependency lock so newly introduced third-party packages cannot silently fall back to source builds.
- Reuse mode: behavior/principle only. No NautilusTrader source code was copied.

## Local gap

The repository's GitHub Actions test/audit jobs and production Docker build used ordinary `pip install` commands. pip permits index-resolved source distributions unless binary-only selection is requested. A malicious or compromised sdist can therefore execute its build backend during dependency installation, creating an avoidable supply-chain execution surface before application tests or runtime startup.

The local project itself is intentionally built from this checked-out source tree; the restriction applies to third-party distributions selected from package indexes.

## RED evidence

- Contract test: `tests/test_supply_chain_install_policy.py`.
- RED test commit: `d3be319c9cadd49553f42fb088a88175896bf7d4` (after formatting-only follow-up to the initial test commit).
- CI: `#636`.
- Ruff passed and Python 3.12 full pytest failed at the new policy contract because CI/Docker dependency installs did not contain `--only-binary=:all:`.

## GREEN behavior

- CI test installs use `python -m pip install --only-binary=:all: '.[dev]'`.
- The dependency-audit environment uses the same restriction, including the pinned `pip-audit==2.10.1` tool.
- The production Docker build uses `python -m pip install --only-binary=:all: .`.
- If a newly resolved third-party dependency has no compatible wheel for the target Python/platform, installation now fails instead of silently building its sdist.

## Security and compatibility review

`pip --only-binary=:all:` is an official pip format-control option that disables source packages and fails installation for packages without a binary distribution. This adds no runtime dependency and does not copy upstream code. The change is reversible by removing the option, but doing so would deliberately reopen the source-build trust boundary and should require security review.

The policy does not claim that wheels are intrinsically trustworthy; existing vulnerability auditing, dependency review, and provenance remain required. It specifically removes unsolicited third-party build-backend execution as an installation fallback.

## Validation requirement

Treat the change as complete only after the exact PR head passes Python 3.12/3.13 tests and Ruff, dependency audit, compileall/engineering-skill verification, and the Docker build under the binary-only policy.
