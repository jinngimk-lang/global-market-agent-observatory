# Global Market Agent Observatory — Design

## Goal

Build a private, cloud-deployable observability and research platform for global broker and crypto accounts, excluding mainland China securities markets. The platform must show live candles and account activity, enforce deterministic paper-trading risk limits, maintain a source-graded evidence library, and support daily safe iteration.

## Safety boundary

The default mode is public market data plus paper execution. Live order submission is disabled in code and configuration. Broker and exchange credentials are read from environment variables only and never stored in Git. Read-only adapters may import positions and orders. Any future live adapter must pass through the deterministic risk engine and an explicit deployment-level enable switch.

## Architecture

A FastAPI service hosts REST and WebSocket APIs, a static browser dashboard, a market-data hub, account adapters, a paper broker, a risk engine, and research collectors. SQLite is the default local store so the system runs immediately; the storage boundary is isolated so a production database can replace it later. Binance public WebSocket data and a deterministic replay stream are the initial live/replay market sources.

## Core components

- `market`: normalizes candles and broadcasts them to connected dashboards.
- `broker`: exposes a common account snapshot interface and a paper execution implementation.
- `risk`: validates symbol allowlists, order notional, position exposure, and daily loss limits.
- `store`: persists candles, orders, fills, positions, and evidence records.
- `research`: collects SEC company submissions and GitHub release metadata, then assigns evidence grades.
- `api`: exposes health, candles, orders, portfolio, evidence, research refresh, and WebSocket endpoints.
- `web`: renders live K-lines, fills, portfolio state, orders, and evidence.

## Evidence rules

Grade A requires broker/account exports, signed on-chain transactions, audited records, or regulator-originated transaction disclosures. Grade B covers regulator-originated aggregate holdings and issuer filings. Grade C covers attributable company releases and verified interviews. Grade D is an unverified lead and cannot drive an automated order.

## Failure handling

Market streams reconnect with bounded exponential backoff. API failures return structured error responses. Research collectors preserve source URLs, timestamps, hashes, and failure details. Risk rejection is fail-closed. The dashboard clearly labels replay, paper, read-only, and live modes.

## Testing

Unit tests cover risk decisions, paper fills, evidence grading, SEC parsing, and store behavior. API tests cover health, market history, order submission, portfolio state, and WebSocket payloads. A smoke test starts the service and verifies readiness.
