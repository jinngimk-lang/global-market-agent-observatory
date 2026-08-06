# Production Readiness Baseline

Updated: 2026-08-06

## Current operating mode

The platform remains in **paper trading / read-only observation mode**. Live-order execution is disabled by default and must not be enabled through configuration-only changes.

## Non-negotiable controls

1. Broker and exchange credentials must be injected at runtime through a managed secret store. They must never be committed to GitHub, emitted in logs, included in build artifacts, or exposed to the browser.
2. Withdrawal, transfer, address-book, beneficiary-management, and account-administration permissions are unsupported.
3. An agent may produce a structured order proposal, but a deterministic risk engine must approve the proposal before any execution adapter can receive it.
4. Every order intent, risk decision, outbound request, broker acknowledgement, fill, cancellation, reconciliation result, and operator action must have an immutable audit event.
5. Paper and live environments must use separate credentials, endpoints, databases, queues, dashboards, and alert channels.
6. The emergency kill switch must be independent of the strategy process and must be tested before each production release.

## Release gates

### Gate 1 — Repository and supply chain

- [ ] Branch protection requires passing CI and reviewed pull requests.
- [ ] Dependency lock files are present and reproducible.
- [ ] Dependency, license, secret, and container vulnerability scans pass.
- [ ] Third-party trading engines run in isolated containers with pinned versions.
- [ ] GitHub Actions use minimum required permissions and pinned action revisions.

### Gate 2 — Data integrity

- [ ] Market-data freshness, sequence gaps, duplicate events, and clock drift are monitored.
- [ ] K-line aggregation is covered by deterministic tests across interval boundaries.
- [ ] Corporate-action and symbol-mapping changes cannot silently corrupt positions.
- [ ] SEC, CFTC, company-IR, and GitHub ingestion preserve source URL, publication time, retrieval time, content hash, and evidence grade.
- [ ] Crisis-period performance records clearly separate verified fills, regulatory holdings, audited reports, interviews, and unverified claims.

### Gate 3 — Connector safety

- [ ] Alpaca sandbox/read-only contract tests pass.
- [ ] IBKR paper-account/read-only contract tests pass.
- [ ] Each CCXT venue has a documented capability matrix and sandbox test result.
- [ ] Disconnect, reconnect, rate-limit, stale-session, partial-fill, and duplicate-client-order scenarios are tested.
- [ ] Reconciliation detects broker state that differs from internal state and blocks new orders until resolved.

### Gate 4 — Risk and execution

- [ ] Symbol whitelist, per-order notional, gross exposure, leverage, concentration, daily loss, and stale-price limits are enforced outside the agent.
- [ ] Order identifiers are idempotent across retries.
- [ ] Market orders are disabled unless a separately reviewed policy permits them.
- [ ] Short selling, options writing, margin, and derivatives remain disabled unless explicitly approved per account and strategy.
- [ ] Kill-switch tests prove that new orders are blocked and open orders can be cancelled without the strategy process.

### Gate 5 — Operations

- [ ] Dashboard authentication and role-based access control are enabled.
- [ ] Alerts cover stale data, connector failures, rejected orders, reconciliation mismatches, risk-limit breaches, and abnormal latency.
- [ ] Backups, restore tests, retention, disaster recovery, and incident procedures are documented.
- [ ] A paper-trading soak test runs continuously for at least 30 calendar days before any live-order review.

## Promotion policy

Passing this baseline does not automatically authorize live trading. Live execution requires a separate threat model, broker-specific sandbox evidence, reconciliation report, kill-switch exercise, explicit human approval, and a limited-capital rollout plan.
