# IBKR trade-history retention and reconciliation completeness

Date: 2026-08-27

## Trigger

NautilusTrader commit `5a2d9801eac2133689c555441f6b4bd6e8e634ba` (LGPL-3.0) fixed Binance Futures reconciliation that treated history outside the venue's retained execution window as complete. No NautilusTrader source code was copied; only the completeness principle was reused.

Upstream: `nautechsystems/nautilus_trader@5a2d9801eac2133689c555441f6b4bd6e8e634ba`.

## Official IBKR boundary

IBKR Client Portal / Trading Web API `GET /iserver/account/trades` returns trade history for up to seven prior days. The `days` parameter accepts up to `7`; omitting it returns only current-day executions.

Reference: IBKR Campus, Trading Web API, **Trade History** (`/v1/api/iserver/account/trades`).

## Local gap

The IBKR execution adapter already used open orders first, then trade history only as a locator, then authoritative order status for terminal truth. However, its recovery query requested only `days=1` even though IBKR supports seven days. A closed order two to seven days old could therefore disappear from both the open-order view and the locally requested trade-history window, reducing idempotency/recovery coverage below the provider-supported maximum.

## RED

Commit `9b33efee2a5c9b570cfb990ff67f82ac7facffcd` added a regression test requiring the full supported trade-history window. CI `#594` failed exactly at this contract on both Python versions: `observed_days == ["1"]` instead of `["7"]`; Python 3.12 reported `1 failed, 266 passed` with Ruff passing.

## GREEN

Production IBKR construction now routes through `IBKRRetentionAwareExecutionAdapter`, which preserves the existing adapter behavior but forces `/iserver/account/trades` recovery queries to `days=7`. The change does not treat trade-history evidence as terminal truth: matching executions still only locate one broker order id, and the existing order-status endpoint remains authoritative for final state.

Implementation commits:

- `c512b6c08f8b8c7219e6c3c4444404040a4f7f27` — retention-aware adapter.
- `33c91ae108f812fb2d69e246ebdfff194bc361d1` — regression test targets the production-safe adapter.
- `1aa32b1c3e2cd7594dbf774694fef85713c8ffc0` — execution factory routes IBKR through it.

## Safety and limits

This expands recovery evidence only to the provider's documented maximum. It does not claim that absence from seven-day trade history proves an order never existed outside that window. The project must continue to rely on durable local audit/checkpoint identity and broker reconciliation rather than treating finite provider history as globally complete.

No new dependency, credential scope, paid service, strategy promotion, or live-capital permission was introduced.
