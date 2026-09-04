# Alpaca single-leg options stop-order capability — 2026-08-27

## Upstream evidence

- Provider: Alpaca
- Source: official Alpaca API changelog
- Published: 2026-08-27
- Change: the `OrderType` schema now documents `stop` and `stop_limit` as supported for **single-leg options** in addition to `market` and `limit`.
- Official capability matrix in the same change:
  - equities: `market`, `limit`, `stop`, `stop_limit`, `trailing_stop`
  - single-leg options: `market`, `limit`, `stop`, `stop_limit`
  - multileg options: `market`, `limit`
  - crypto: `market`, `limit`, `stop_limit`
- Relevant Trading API operations include `/v2/orders` submit/list/get/replace and lookup by client order id.
- Source URL: https://docs.alpaca.markets/us/changelog/2026-08-27-options-stop-orders-08e9371

## Local comparison

At exact head `3e9fcd0bd5a72c6b1baebde340274f3ecccff8ff`, the local domain `OrderType` intentionally contains only `market` and `limit`, and `AlpacaExecutionAdapter.submit()` serializes only those two forms. The project currently consumes options data for market-structure evidence but does not expose a dedicated options execution path or an asset-class-aware order capability model.

Therefore this upstream change does **not** justify adding stop/stop-limit runtime behavior now. Doing so would expand the execution surface before there is a local options-execution hypothesis, deterministic risk policy, contract-test matrix, or promotion evidence for such orders.

## Durable design implication

Future execution capability must be modeled as a provider + asset-class + leg-structure capability matrix rather than assuming that every `OrderType` enum member is valid for every instrument. A future options-execution workstream should fail closed when an order type is unsupported for the selected asset/leg structure, and should add RED contract tests before enabling any new order form.

The canonical execution path remains:

`StrategySignal -> OrderIntent -> deterministic RiskDecision -> ExecutionAdapter -> reconciliation`

No live-capital permission, strategy maturity, or broker authority changes as a result of this provider capability update.

## Integration decision

- Code copied from upstream: none.
- New dependency: none.
- Runtime behavior changed: none.
- Rollback: delete this provenance note.
- Follow-up trigger: revisit only when the repository intentionally introduces options execution or a generic capability-negotiation layer.
