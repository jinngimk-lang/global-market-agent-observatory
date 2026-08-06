# Global Market Agent Observatory

A private, cloud-deployable market observability and research platform for global brokers and crypto exchanges, excluding mainland China securities markets.

The repository starts in **replay market data + paper execution** mode. Live order submission is intentionally absent. Real broker and exchange integrations are read-only account observers.

## What is included

- Real-time candlestick dashboard over WebSocket.
- Binance public kline feed and deterministic replay feed.
- Paper broker with average-cost positions, realized P&L, idempotent client order IDs, and persistent audit records.
- Fail-closed risk engine: symbol allowlist, positive quantity and price, order notional, cash, projected gross exposure, and daily loss lockout.
- Read-only account observers for Alpaca, IBKR Client Portal Gateway, and CCXT-compatible exchanges.
- SEC submissions collector for recent material agreements and strategic-cooperation evidence.
- Official GitHub release collector for trading engines and exchange libraries.
- Evidence grades A–D with source URL, observation time, event time, and SHA-256 content hash.
- Crisis-window detection and import of only A/B-evidence trade cases that remain profitable after explicit costs.
- Strategic-partnership assessment based on maturity and future validation metrics, without price targets.
- Docker, CI, daily official-source research, and draft-PR automation.

## Architecture

```text
Market feeds ──> normalized candles ──> SQLite ──> REST/WebSocket ──> dashboard
                                          │
Read-only account observers ──────────────┤
                                          │
SEC / official project releases ─> evidence library
                                          │
Verified trade cases ────────────> crisis winners

Paper order request ─> deterministic risk engine ─> paper broker ─> audit trail
```

No language model is allowed to bypass the risk engine. No included component can withdraw funds or submit a live order.

## Cloud observe-only dashboard

The repository includes a GitHub Pages build for a browser-only market monitor. After Pages is enabled with **GitHub Actions** as its source and this change reaches `main`, the expected address is:

```text
https://jinngimk-lang.github.io/global-market-agent-observatory/
```

This site is intentionally **observe-only**. It loads public BTCUSDT candles, falls back to deterministic replay when the public feed is unavailable, does not connect a brokerage account, and disables order and research-write controls. The private FastAPI deployment remains the full paper-trading and research application.

GitHub Pages availability for a private repository depends on the account plan. If Pages cannot be enabled for this private repository, deploy the generated `site/` directory to another static host or make only the dashboard repository public; do not expose backend secrets or account endpoints.

Build the same site locally:

```bash
python scripts/build_static_site.py --output site
python -m http.server 8080 --directory site
```

Open `http://127.0.0.1:8080`.

## Run locally

Requirements: Python 3.12 or 3.13.

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
python -m pip install '.[dev]'
python -m uvicorn app.api.main:app --reload
```

Open `http://127.0.0.1:8000`.

Use real public Binance candles instead of replay data:

```bash
MARKET_SOURCE=binance python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

## Run with Docker

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

The container runs as a non-root user, drops Linux capabilities, uses a read-only root filesystem, and writes only to the named database volume. Browser responses include a restrictive content-security policy and anti-framing headers.

Place an authenticated reverse proxy or private VPN in front of the service before any remote deployment.

## Read-only account connections

### Alpaca

Set `ALPACA_API_KEY` and `ALPACA_API_SECRET`. The default endpoint is the paper environment. The observer reads account, positions, and recent orders. It contains no POST, PATCH, or DELETE request paths.

### Interactive Brokers

Run and authenticate an IBKR Client Portal Gateway separately, then set:

```bash
IBKR_ENABLED=true
IBKR_ACCOUNT_ID=U1234567
IBKR_BASE_URL=https://host.docker.internal:5000/v1/api
```

The observer reads account summary, positions, and orders. Gateway authentication and session renewal remain outside this service.

### CCXT-compatible crypto exchanges

Install the optional dependency:

```bash
python -m pip install '.[crypto]'
```

Then configure `CCXT_EXCHANGE_ID` and a dedicated read-only API key. Keep `CCXT_SANDBOX=true` until the observer is validated. Disable trading, withdrawals, transfers, and address management on the exchange key itself.

## Optional upstream engines

The repository records five reviewed upstream projects in `upstreams/catalog.json`: LEAN,
Freqtrade, Hummingbot, CCXT, and NautilusTrader. Each entry is pinned to an exact commit,
disabled by default, and assigned an isolation mode based on its license and runtime risk.
No upstream receives account credentials automatically.

Install one reviewed source tree into the ignored `.upstreams/` directory:

```bash
./scripts/bootstrap_upstreams.sh lean
```

Install every catalogued source tree:

```bash
./scripts/bootstrap_upstreams.sh all
```

This only checks out pinned source. It does not start an engine, enable a strategy, or grant
network/account access. Freqtrade and NautilusTrader remain container-isolated because of
their copyleft license boundaries; all engines should begin in backtest or dry-run mode.

## Research configuration

SEC automated access requires an identifying user agent containing a monitored contact email:

```bash
SEC_USER_AGENT='GlobalMarketObservatory research@example.com'
SEC_CIKS=0000320193,0000789019
```

Run a refresh:

```bash
python -m app.research.daily
```

The scheduled GitHub workflow runs daily at 08:00 Asia/Tokyo equivalent and opens a **draft pull request** for new official-source metadata. It never auto-merges.

## Import verified crisis winners

Prepare a JSON file containing crisis windows and trade cases. Each accepted case must overlap a crisis window, have positive net P&L after costs, include at least one evidence URL, and carry evidence grade A or B.

```json
{
  "windows": [
    {
      "name": "example-selloff",
      "start": "2025-04-01T00:00:00Z",
      "end": "2025-04-30T00:00:00Z",
      "market": "GLOBAL",
      "max_drawdown": "-0.12"
    }
  ],
  "cases": [
    {
      "case_id": "audited-case-001",
      "actor_name": "Verified Fund",
      "actor_type": "institution",
      "instrument": "INDEX FUTURE",
      "opened_at": "2025-04-03T00:00:00Z",
      "closed_at": "2025-04-20T00:00:00Z",
      "gross_pnl": "120000",
      "costs": "5000",
      "evidence_grade": "A",
      "evidence_urls": ["https://source.example/audit"],
      "strategy_tags": ["tail-risk-hedge"]
    }
  ]
}
```

```bash
python -m app.research.import_cases verified-cases.json
```

Screenshots and self-reported returns are grade D and are rejected by this importer.

## Primary API routes

| Route | Purpose |
|---|---|
| `GET /api/health` | Runtime and safety status |
| `GET /api/candles/{symbol}` | Stored normalized candles |
| `WS /ws/market` | Live candle stream |
| `POST /api/orders` | Paper order through deterministic risk controls |
| `GET /api/portfolio` | Paper account snapshot |
| `GET /api/orders` | Paper execution audit trail |
| `GET /api/accounts` | Read-only external account snapshots |
| `GET /api/evidence` | Source-graded research evidence |
| `POST /api/research/refresh` | Refresh configured official sources |
| `GET /api/research/crisis-winners` | Verified positive crisis cases |
| `GET /api/research/partnerships` | Partnership maturity and validation metrics |
| `GET /docs` | Interactive OpenAPI documentation |

## Verification

```bash
python -m pip install '.[dev]'
./scripts/loop_verify.sh
```

The release process requires three consecutive successful verification runs. Docker verification can be included with:

```bash
LOOP_VERIFY_DOCKER=1 ./scripts/loop_verify.sh
```

## Security and limitations

Read `docs/SECURITY.md` before connecting any real account.

Public disclosures cannot reconstruct every institution or individual trade in real time. The system distinguishes observed account data, regulator disclosures, official announcements, and unverified claims rather than presenting them as equivalent. This software is a research and observability tool, not investment advice or a promise of returns.
