# Domain context

## Product

**Global Market Agent Observatory** is a cloud-oriented market research and paper-trading observatory. It combines live/replayed candles, read-only account observers, evidence-backed crisis research, strategic-partnership research, deterministic risk controls, and a browser dashboard.

## Shared language

- **Market feed** — a source of candles or quotes. A feed may be replayed or live and must not imply execution authority.
- **Observer** — a read-only connector that retrieves balances, positions, orders, or fills without placing or modifying orders.
- **Paper broker** — a deterministic simulator used to test order workflows without real capital.
- **Order intent** — structured output proposed by an agent or strategy. It is not an executable order.
- **Risk decision** — deterministic approval or rejection of an order intent according to configured limits.
- **Execution adapter** — a broker- or exchange-specific boundary. Production adapters remain disabled until separately approved.
- **Evidence item** — a sourced, dated research record with provenance and confidence metadata.
- **Crisis case** — a verified historical episode describing behavior during a major drawdown; it must distinguish public evidence from inference.
- **Kill switch** — a deterministic control that prevents new executions and cancels eligible outstanding paper/sandbox orders.

## Safety invariants

1. The default runtime is replay or public market data plus paper trading.
2. Agent output never bypasses the deterministic risk engine.
3. No withdrawal, transfer, custody, or account-administration capability is exposed.
4. Secrets are injected at runtime and never stored in the repository or browser bundle.
5. Claims about institutions, individuals, partnerships, or performance require dated primary-source evidence where available.
