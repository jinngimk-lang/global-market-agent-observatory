# Security Model

## Non-negotiable defaults

- Live order submission is disabled in both configuration and code validation.
- The included execution adapter is a deterministic paper broker only.
- Alpaca, IBKR, and CCXT integrations are account observers: they issue read requests and never submit, replace, cancel, transfer, or withdraw.
- Credentials are accepted only through environment variables and are excluded from Git and Docker build context.
- Risk decisions fail closed when symbol, price, quantity, loss, notional, cash, or exposure checks fail.
- Daily automation may create draft pull requests but cannot auto-merge.
- Browser responses deny framing, MIME sniffing, sensitive browser capabilities, and non-allowlisted content sources.
- Third-party engines are pinned, disabled by default, and installed outside the core source tree.

## Credential guidance

Use paper or sandbox accounts first. For real accounts, create a dedicated API identity with the narrowest available permissions. Disable withdrawals, transfers, address-book changes, and key management. Use IP allowlists and short credential rotation intervals where the provider supports them.

Never paste credentials into issues, pull requests, chat transcripts, screenshots, log files, or research JSON. GitHub Actions secrets are appropriate for CI-only credentials; repository variables are appropriate only for non-secret configuration such as CIK lists.

## Network boundary

Expose the dashboard only behind an authenticated reverse proxy or private network. The application intentionally does not implement public multi-user authentication. Do not publish port 8000 directly to the internet.

IBKR Client Portal Gateway sessions require separate authentication and session maintenance. Keep the gateway on a trusted host or private network and do not disable TLS verification outside a local gateway context.

## Incident response

1. Stop the container or service.
2. Revoke all connected API keys and gateway sessions.
3. Preserve application logs and the SQLite database for investigation.
4. Review recent orders and account snapshots directly with each provider.
5. Rotate deployment secrets before restarting.
6. Open a private security issue with reproduction details and sanitized logs.

## Reporting

This repository is intended to remain private. Report vulnerabilities through a private GitHub security advisory rather than a public issue.

## Upstream code policy

`upstreams/catalog.json` is the source of truth for reviewed upstream engines. Do not replace
commit pins with floating branches in production. Run each engine with its own filesystem,
network policy, service identity, and credential set. A successful upstream backtest is not
permission to connect the engine to a live account. License obligations must be reviewed again
before distributing a combined deployment.
