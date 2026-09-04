# Global Market Autonomous Trading Platform — Agent Guide

This repository is the primary autonomous market monitoring and trading platform. It supports replay, paper, broker-paper, and deliberately enabled live execution. Safety-critical trading behavior must remain deterministic and fail closed.

## Mandatory context recovery

Durable project truth must not depend on conversation memory.

Whenever starting a new implementation session, resuming after a long interruption, handing work between agents, experiencing context pressure, or becoming uncertain about prior choices, recover in this order:

1. Read `PROJECT_DIRECTION.md` in full — durable product direction and safety invariants.
2. Read `STATUS.md` — current branch/workstream state, completed work, blockers, and immediate next steps.
3. Read this `AGENTS.md` — repository operating rules.
4. Read `docs/AUTONOMOUS_OWNER_GOVERNANCE.md` — autonomous project-owner authority, ecosystem-intelligence loop, and external-integration gate.
5. Read `docs/INNOVATION_DOCTRINE.md` when designing or changing a strategy, architecture premise, integration strategy, safety boundary, or durable workflow.
6. Read `CONTEXT.md` plus the newest relevant ADR/spec/plan/decision record.
7. Inspect the current branch, PR/CI state, current evidence, and the latest relevant upstream/ecosystem changes before editing code.

Do not ask the user to repeat stable direction the repository already records.

Do not silently drift away from canonical project truth. If durable direction changes, update the canonical document and `STATUS.md` in the same workstream; add a decision record when rationale would otherwise be lost.

## Autonomous project-owner operating rule

Within the repository and current authorized workstream, normal reversible evidence-backed engineering decisions should be made and executed autonomously instead of repeatedly asking the user for confirmation.

This includes architecture, implementation order, tests, refactors, documentation, issue/PR coordination, dependency choices, skills, MCP/connectors, and reviewed upstream integrations when they materially improve the project.

The agent must proactively acquire or use appropriate skills, MCP servers, connectors, or tooling when existing capabilities are insufficient and the additional tool is available and safe.

This autonomy does **not** grant permission to bypass capital-safety boundaries. It never implies permission to expose or rotate secrets, make paid purchases, create legal commitments, perform destructive/irreversible external actions, disclose sensitive security findings publicly, promote strategy maturity without evidence, or enable live capital merely because broker capability exists.

For the full operating model, follow `docs/AUTONOMOUS_OWNER_GOVERNANCE.md`.

## Continuous ecosystem intelligence

The project must not assume its current dependencies, broker APIs, data providers, or engineering patterns are permanently optimal.

Continuously inspect relevant public GitHub projects, official broker/data documentation, releases, security advisories, market-data interfaces, and credible engineering research. Prioritize changes related to Alpaca, IBKR, NautilusTrader, QuantConnect/LEAN, market-data/options/off-exchange sources, execution/reconciliation, replay/backtest/OOS correctness, transport/WebSocket reliability, and supply-chain security.

External discoveries enter the repository only through this evidence gate:

`discover -> classify -> verify -> license/security review -> compare -> smallest useful integration -> RED/GREEN -> full CI -> provenance -> PROJECT_DIRECTION/STATUS update`

Never copy a repository or source file merely because it is popular or new. Prefer adopting a proven pattern over copying code when practical. Record exact upstream repository/tag/commit and attribution for non-trivial adaptations.

## Product safety boundary

Live execution is a first-class capability but must be OFF by default. It may only be enabled by explicit runtime configuration and must never be inferred merely from the presence of broker credentials.

The mandatory execution path is:

`StrategySignal -> OrderIntent -> deterministic RiskDecision -> ExecutionAdapter -> reconciliation`

No LLM, research agent, strategy module, UI action, external signal, skill, MCP server, or upstream project may bypass deterministic risk approval.

The system must fail closed when market data, broker state, reconciliation state, or execution outcome is stale, missing, or uncertain.

## Strategy hypothesis and promotion boundary

Technical broker capability and strategy evidence maturity are independent gates.

Every durable strategy must have a version-specific hypothesis manifest recording:

`category default -> deleted constraint -> new axis`

plus observable inputs, provenance requirements, expected mechanism, falsification conditions, failure regimes, safety constraints, and current promotion stage.

Canonical stages are:

`idea -> research -> replay -> paper -> broker-paper -> live`

A strategy may not skip stages. A material strategy version change must return to the stage appropriate for the new uncertainty.

When autonomous execution is requested, the runtime promotion gate must be satisfied for the selected operating mode. If not, the system remains monitor-only even if the broker adapter is technically capable of sending orders.

Never mark a strategy as promoted merely because code exists, a backtest is profitable, or the broker connection works. Promotion requires persisted evidence for the exact strategy version.

## Innovation method

For material product/strategy changes, apply `docs/INNOVATION_DOCTRINE.md`:

- reframe before optimize;
- identify the category default;
- ask why the default constraint must exist;
- explore incremental improvement, observable-mechanism bridge, and constraint deletion;
- prefer the reframe only when it is more observable, falsifiable, specific, and safely operable;
- run the innovation review gate before turning a clever concept into durable architecture.

Do not add indicators, agents, data vendors, or abstractions merely because they are available.

## Agent skills

The engineering skill collection is pinned in `.agents/skills.lock.json`. Initialize it with `./scripts/bootstrap_agent_skills.sh`; skills are exposed through `.agents/skills/`.

If project work requires a capability not covered by the pinned collection, proactively discover and use a suitable skill/MCP/connector when available, then document any durable workflow dependency that future agents must know.

### Issue tracker

Work is tracked in GitHub Issues for `jinngimk-lang/global-market-agent-observatory`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the canonical triage vocabulary documented in `docs/agents/triage-labels.md`.

### Domain docs

Read `PROJECT_DIRECTION.md`, `STATUS.md`, this file, `docs/AUTONOMOUS_OWNER_GOVERNANCE.md`, `docs/INNOVATION_DOCTRINE.md` when relevant, `CONTEXT.md`, and relevant ADRs under `docs/adr/` before changing system behavior. See `docs/agents/domain.md`.

## Engineering rules

- Use a failing behavior test before implementation where a stable public seam exists.
- Keep strategy output separate from deterministic risk approval and broker execution.
- Keep strategy promotion separate from broker capability.
- Never commit credentials, account tokens, private keys, cookies, or real account identifiers.
- Live trading must be disabled by default and explicitly enabled at runtime.
- Unknown execution outcomes must reconcile before any retry that could duplicate an order.
- Orders must use idempotent client order identifiers.
- Kill-switch behavior must not depend on an LLM or research service.
- Broker/account reconciliation is mandatory for live execution.
- Inferred market structure such as dealer positioning must retain methodology/provenance and must not be represented as direct fact.
- External code may only be adapted after license/security review and must retain required attribution and upstream provenance.
- External discoveries must be evaluated for whether they reduce uncertainty or merely add dependencies.
- Run targeted tests during implementation, then the complete test suite and static checks before treating the work as complete.
- Review every change against repository standards, `PROJECT_DIRECTION.md`, `STATUS.md`, autonomous-owner governance, the innovation doctrine when relevant, and the originating requirement.
