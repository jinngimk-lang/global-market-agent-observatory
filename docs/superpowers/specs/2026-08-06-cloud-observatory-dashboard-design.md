# Cloud Observatory Dashboard Design

- Status: Accepted from prior conversation and user-delegated implementation authority
- Date: 2026-08-06

## Goal

Deliver a browser-accessible K-line observatory that can run in two safe modes:

1. **Private application mode** — FastAPI, replay or public live market data, paper execution, read-only account observers, evidence research, and audit records.
2. **Static cloud mode** — GitHub Pages-compatible dashboard using public market data only, with all order and write operations disabled.

The work also makes the complete source tree reproducibly publishable to the user's GitHub repository despite the current execution environment lacking direct Git network access.

## Non-goals

- No real-money order placement.
- No withdrawals, transfers, custody, or account administration.
- No claim that public disclosures reconstruct every institution or person's trading record.
- No automated strategy selection based on grade C/D evidence.
- No secrets embedded in the static site or browser bundle.

## Architecture

### Shared dashboard shell

`app/web/index.html` and `app/web/styles.css` remain the shared presentation layer. A small runtime configuration object selects either `backend` or `static` mode. The browser code exposes the same chart and observability panels in both modes, but capabilities are explicit.

### Backend mode

The existing REST and WebSocket interfaces remain authoritative:

- `GET /api/health`
- `GET /api/candles/{symbol}`
- `WS /ws/market`
- paper-only order and portfolio APIs
- read-only external account APIs
- evidence and research APIs

If the backend is available, the dashboard behaves as it does today.

### Static cloud mode

A generated `site/` directory contains relative-path assets and a `config.js` file declaring static mode. The client:

- loads recent Binance public klines over HTTPS;
- opens the Binance public kline WebSocket;
- reconnects with bounded exponential backoff;
- falls back to deterministic local replay candles when public network access is unavailable;
- displays an explicit `PUBLIC DATA / OBSERVE ONLY` state;
- disables order submission, research refresh, and account actions;
- uses local demonstration data only for non-market panels and labels it as demo data.

### Build and deployment

`scripts/build_static_site.py` copies the shared dashboard into `site/`, rewrites asset paths to relative paths, and writes static configuration plus demo datasets. A GitHub Pages workflow builds and deploys `site/`. The full FastAPI application remains deployable by Docker behind an authenticated reverse proxy.

### Repository publication

The canonical repository is `jinngimk-lang/global-market-agent-observatory`. Normal development uses Git commits. If direct Git transport is unavailable, a source-pack bootstrap workflow may be used once to materialize the complete verified source tree; the bootstrap payload must be removed after successful materialization.

## Safety and error handling

- Static mode never sends POST, PATCH, PUT, or DELETE requests.
- Static mode never reads browser-stored credentials.
- Market network failures degrade to replay data and show a visible degraded badge.
- Backend mode keeps existing fail-closed risk controls.
- All source claims retain evidence grade, event date, observation date, and source URL.
- The content security policy permits only required chart CDN and public market endpoints.

## Testing

- Unit-test runtime mode selection and static capability disabling.
- Test deterministic fallback candle generation.
- Test static build output uses relative assets and contains no private endpoints or secrets.
- Test FastAPI dashboard remains functional in backend mode.
- Run Python tests, static checks, compile checks, and a live startup health probe.
- Review changes on both standards and specification axes.
