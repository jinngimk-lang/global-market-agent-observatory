# IBKR Disconnect Fill Recovery — 2026-08-25

## Trigger

A fresh ecosystem scan found QuantConnect issue `Lean.Brokerages.InteractiveBrokers#249`, opened 2026-08-04, reporting that executions occurring during an IBKR 1100 disconnect window can be absent from the normal post-reconnect event flow unless execution history is explicitly reconciled.

Upstream repository: `QuantConnect/Lean.Brokerages.InteractiveBrokers`
Upstream issue: `#249`
License: Apache-2.0
Reuse mode: conceptual evidence only; no QuantConnect source code was copied or adapted.

## Official IBKR evidence

IBKR Trading Web API documentation exposes distinct views that are relevant to recovery:

- `GET /iserver/account/orders` — open-order state;
- `GET /iserver/account/trades` — recent execution reports/trade history, including `order_ref`, `order_id`, size, price, and account;
- `GET /iserver/account/order/status/{orderId}` — broker order status including cumulative fill and average price.

The local adapter previously used only the open-order endpoint for `get_order_by_client_id()`. That was fail-safe because an unresolved UNKNOWN execution halted the orchestrator, but it could not recover broker truth when a disconnected order had already filled and disappeared from open orders.

## Local RED

Commit: `f2133487bc6f0d2487ead646550120064b6d541f`
CI: `#458`

A new regression test modeled:

1. no matching open order;
2. a recent IBKR trade whose `order_ref` matches the local client order id;
3. the expectation that reconciliation must continue beyond the open-order view.

Exact RED evidence: Ruff passed and full pytest reported `1 failed, 228 passed`; the only failure was the new closed-fill recovery test because `/iserver/account/trades` was never queried.

The test was then strengthened in commit `0459b6be1cfc3d4bab3475242af50245a079cb08` so that seeing a trade is not itself sufficient to claim a fully filled order. A matching trade identifies the broker order; terminal state must come from the broker order-status endpoint.

## Local GREEN

Implementation commit: `06d809259fba3cf9d0b4fdcf6f5f493534cbba56`

`IBKRExecutionAdapter.get_order_by_client_id()` now:

1. checks open orders first;
2. if no matching open order exists, queries recent trade history;
3. matches executions by exact `order_ref` and account;
4. requires one unambiguous broker `order_id`;
5. queries `/iserver/account/order/status/{orderId}` for terminal broker truth;
6. maps `cum_fill` and `average_price` into the local execution result;
7. remains `UNKNOWN` if trade identity, transport, HTTP response, or terminal status cannot be established safely.

Trade history therefore acts as a recovery locator, not as permission to infer `FILLED`. Partial execution or uncertain terminal state remains fail-closed.

## Verification

The implementation was included in exact-head CI `#468`. Python 3.12 and Python 3.13 both passed Ruff, full pytest, compileall, and the engineering-skill check. The final repository head after this provenance/status update must also pass the full CI including Docker before the work is treated as complete.

## Safety impact

This change does not enable live trading, promote any strategy, modify credentials, or weaken risk limits. It reduces the time an ambiguous IBKR execution can remain unreconciled while preserving the invariant that uncertain broker truth cannot authorize a retry or new exposure.

## Durable rule

For broker recovery, do not assume that the provider's open-order view is a complete execution ledger. When an order may have crossed a disconnect boundary, reconcile against provider execution history and then confirm terminal order state from an authoritative broker endpoint before clearing UNKNOWN state.
