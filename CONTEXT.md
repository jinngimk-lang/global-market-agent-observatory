# Domain context

## Product

**Global Market Autonomous Trading Platform** is the primary market-monitoring and autonomous trading system in this repository. It supports replay, local paper trading, broker-paper execution, and deliberately enabled live execution through controlled broker adapters.

The long-horizon product direction lives in `PROJECT_DIRECTION.md`. Agents must reread that file whenever context is incomplete, work resumes after interruption, or a major architectural decision is made.

## Shared language

- **Market feed** — a source of candles, quotes, trades, order-book data, or options data. Feeds carry provenance and freshness state.
- **Market intelligence** — deterministic or explicitly modeled derived structure such as VWAP, volume profile, support/resistance, order-flow imbalance, GEX estimates, gamma flip, put wall, and call wall.
- **Strategy signal** — versioned analytical output proposing buy, sell, hold, reduce, or exit with evidence and invalidation metadata. A signal is never executable by itself.
- **Order intent** — broker-neutral structured output proposed after strategy/portfolio processing. It is not an executable order until deterministic risk approves it.
- **Risk decision** — deterministic approval, resize, or rejection of an order intent according to configured limits and runtime trading state.
- **Execution adapter** — a broker-specific boundary for submit, cancel, query, and reconciliation. Paper and live adapters implement the same controlled contract.
- **Reconciliation** — comparison of internal state with broker-authoritative cash, positions, orders, fills, and execution outcomes.
- **Evidence item** — a sourced, dated research record with provenance and confidence metadata.
- **Kill switch** — deterministic control that moves the runtime to halted state, preventing new exposure while preserving cancellation and reconciliation capabilities.
- **Trading mode** — explicit runtime mode: replay, paper, broker-paper, or live.
- **Trading state** — active, reducing, or halted safety state independent of strategy logic.

## Safety invariants

1. Live trading is OFF by default.
2. `TRADING_MODE=live` alone is insufficient; live execution also requires `LIVE_TRADING_ENABLED=true` and `LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING`.
3. Strategy/LLM output never bypasses the deterministic risk engine.
4. Unknown or stale market/account state blocks new live exposure.
5. Unknown execution outcomes reconcile before any retry that could duplicate an order.
6. Orders use idempotent client order identifiers.
7. Broker state is authoritative for live reconciliation.
8. No withdrawal, transfer, custody, or account-administration capability is exposed by the autonomous trading loop.
9. Secrets are injected at runtime and never stored in the repository or browser bundle.
10. Kill-switch and fail-closed behavior do not depend on an LLM or external research service.
11. Claims about institutions, individuals, partnerships, flow, dealer positioning, or performance retain dated evidence and model assumptions where applicable.
