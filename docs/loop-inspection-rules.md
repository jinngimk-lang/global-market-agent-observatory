# Loop Inspection Rules

## From page load to system behavior

A passing loop requires more than rendering a page.

Required checks:

1. Critical action has a visible result.
2. Navigation has a return path.
3. Failed states expose recovery.
4. Refresh/re-entry does not create dead ends.
5. Observe-only boundaries remain enforced.

## Priority flows

- Dashboard -> Market data -> Dashboard
- Dashboard -> Research -> Dashboard
- Dashboard -> Broker status -> Dashboard
- Error state -> Recovery -> Stable view

## Forbidden regression

- Any UI path implying live execution.
- Any action without result state.
- Any route without recovery.
