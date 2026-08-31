# Bounded runtime task shutdown provenance

Date: 2026-08-31

## Upstream trigger

- Repository: `nautechsystems/nautilus_trader`
- Commit: `4c186912775c07c57c8630e807807b3932ead979`
- Commit title: `Standardize adapter task lifecycles`
- Upstream behavior reviewed: generation-safe task groups, bounded and observable shutdown, cancellation-safe teardown, and race/reconnect/failed-startup regression coverage.
- License: LGPL-3.0. No upstream source code was copied into this repository; only the verified behavioral principle was adopted.

## Local gap

`ApplicationState.stop()` cancelled the four top-level runtime tasks and then awaited each task without a timeout. A task that caught or otherwise failed to complete cancellation could therefore block application shutdown indefinitely. That is an operational-liveness failure and can also obscure whether an old runtime generation has actually relinquished authority.

The current Python runtime does not yet need NautilusTrader's broader task-group abstraction: it owns a small fixed set of top-level tasks and does not run parallel replacement generations. The smallest local correction is therefore a single bounded wait across the owned tasks plus explicit timeout evidence.

## RED evidence

- Deterministic RED commit: `fa6c6e86eb0b453fa71fc5adec8abe20711b7228`
- CI: `#697`
- Contract: `test_runtime_stop_is_bounded_when_task_ignores_cancellation`
- Observed failure on Python 3.12: shutdown took about `0.1503s` even though the test configured a `0.01s` shutdown timeout, proving that the existing implementation waited for the cancellation-resistant task to release instead of bounding shutdown.

An earlier RED draft (`cbafa49b2b217773c0012476754178e107de18d4`, CI `#695`) exposed a test-start race and was corrected before production behavior changed.

## Local implementation

- Production implementation commit: `ef6ba115967a24378417af0514f68b6082177962`
- Lint/minimalization follow-up: `f6ba1efbd818e67394663dd9b5f591eab1bfd4c6`

`ApplicationState.stop()` now:

1. cancels all owned top-level runtime tasks;
2. waits for them together under one bounded timeout rather than multiplying the timeout per task;
3. records `shutdown_timeout` per task that fails to terminate in time;
4. records unexpected shutdown exceptions instead of silently treating them as successful teardown;
5. clears the runtime task references and continues normal owned-resource cleanup.

The timeout is currently an internal five-second default. Tests override it to exercise the failure path quickly. No trading, strategy-promotion, broker, credential, or capital-permission semantics changed.

## Safety and rollback

This is a local operational-hardening change with no new dependency. It does not grant a replacement task or reconnect generation any additional authority. If later runtime architecture introduces overlapping generations or nested independently owned tasks, the stronger generation-token/task-group model must be evaluated separately with race and reconnect failure injection.

Rollback is a normal revert of the local shutdown handling and regression test. Reverting would restore the known unbounded-shutdown risk, so it should only be done together with an equivalent bounded teardown mechanism.
