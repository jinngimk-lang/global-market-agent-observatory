# Unknown execution outcome must remain fail-closed through reconciliation

Date: 2026-08-27

## External trigger

- Upstream: `nautechsystems/nautilus_trader`
- Commit: `f2b2addb99527e3c9465573a596284f47b9edf10`
- Commit time: 2026-08-27 12:24:23 UTC
- Upstream behavior: Kraken Spot request correlation is retained after timeouts until definitive evidence or shutdown, with late-response and reconnect recovery coverage.
- License: LGPL-3.0.
- Reuse mode: behavior/invariant only; no NautilusTrader source code was copied or adapted.

## Local gap

`ExecutionController` already classified ambiguous broker submission outcomes as `UNKNOWN` and immediately reconciled by deterministic client-order identity. However, after an unknown submit, if reconciliation itself returned an `ExecutionResult` whose status was still `UNKNOWN`, the controller replaced the result but did not transition capital state to `HALTED`. Only a `None` reconciliation result halted.

That allowed an unresolved execution outcome to coexist with `TradingState.ACTIVE`, contrary to the repository invariant that unknown execution results must fail closed before further exposure can be created.

## RED evidence

- RED commit: `12895075a5d07debcb147244ff6c0ad8beba0a10`
- CI: `#605`
- Added contract: an ambiguous submit followed by an authoritative lookup that is itself still `UNKNOWN` must return `UNKNOWN` and transition the controller to `HALTED`.
- CI evidence: Ruff and Docker passed; Python 3.13 full pytest failed on the new contract before the implementation change.

## GREEN behavior

- GREEN commit: `c2870a1687a31d66eaf102b3ad44703848c96b4a`
- After an `UNKNOWN` submit, reconciliation may restore a definite broker result. If reconciliation is absent or still `UNKNOWN`, capital state becomes `HALTED`.
- No retry semantics, broker endpoint behavior, deterministic risk rules, or live-enable permissions were broadened.

## Durable invariant

An execution outcome is unresolved until reconciliation produces definite evidence. `UNKNOWN -> UNKNOWN` is not progress and must preserve a fail-closed capital state. Process recovery may continue, but new risk remains blocked until the existing controlled recovery path restores authoritative state.

## Rollback

The implementation is isolated to the post-submit unknown-outcome branch in `app/execution/controller.py` and its regression test. It can be reverted independently if a stronger state machine replaces it, provided the replacement preserves the same fail-closed invariant.
