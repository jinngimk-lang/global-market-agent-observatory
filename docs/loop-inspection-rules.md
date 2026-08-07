# Loop inspection rules

The loop is not allowed to pass because a page merely returns HTTP 200 or renders its shell. A critical user action passes only when its entire trigger chain is observable and recoverable.

## Critical-action gate

For every enabled primary action, trace the full chain:

`control -> event listener -> handler -> async boundary -> state mutation -> visible result -> recovery/return path`

The action is **PASS** only when all of the following are true:

1. **Trigger is wired** — the enabled control has a reachable handler.
2. **Pending state is visible** — repeated submission is prevented while the action is running.
3. **Success has a durable result** — the user can tell that the action completed without inferring from unrelated UI changes.
4. **Failure has a durable result** — failures are caught and surfaced; no unhandled rejection or silent timeout is accepted.
5. **Recovery is direct** — retry, reconnect, back, or another explicit safe path is available from the failed state.
6. **Controls recover** — buttons/forms return to their capability-derived enabled/disabled state after success or failure.
7. **Partial failure is isolated** — one failed data source must not prevent independent sources or the market connection from continuing.
8. **No navigation island** — a routed view or modal must have a deterministic return path and browser back/refresh must not strand the user.
9. **Safety state is preserved** — recovery must never enable live trading, bypass server-side risk checks, or expose unavailable capabilities.

## Required smoke scenarios

Each loop should exercise, or have an automated test for, the following paths before calling the UI healthy:

| Scenario | Required result |
| --- | --- |
| Static observe-only boot | Market view remains reachable; account/order/research write controls remain disabled. |
| Initial data failure | Failure is visible and market connection/replay still starts. |
| Account refresh success | Visible completion state; control restored. |
| Account refresh partial failure | Failed count is visible; retry is available; successful panels remain usable. |
| Research refresh success | Stored-count result remains visible; evidence reload is attempted. |
| Research refresh failure | Persistent error plus direct retry; button state restores. |
| Paper-order rejection | Server rejection is visible; form remains usable for a corrected paper-only request. |
| Backend action module unavailable | Action fails visibly rather than producing an unhandled promise rejection. |
| Market disconnect | Connection state is visible and reconnect/replay behavior leaves a usable page. |

## Loop stop-the-line conditions

Treat these as priority regressions:

- an enabled button with no result surface;
- an async event handler that can reject without a visible failure state;
- a loading/disabled state that can persist after an error;
- a retry path that repeats the same dead state without restoring controls;
- startup failure that prevents independent market/replay connection;
- navigation with no deterministic return path;
- any recovery code that widens trading permissions or weakens risk gates;
- CI that reports success without exercising the action/recovery contract.

## Evidence required in a PR

A UI-recovery PR should include:

- a failing regression test or contract added before the fix;
- evidence that the test failed for the intended missing behavior;
- the minimal production change;
- a fresh green CI run covering tests, lint/compile checks, and container build;
- explicit confirmation that observe-only / `LIVE DISABLED` boundaries were unchanged.

Browser-level smoke tests are the target state. Until the repository has a pinned browser-test dependency and CI job, static action-contract tests are only an interim guard and must not be described as full end-to-end coverage.
