# Autonomous Owner and Ecosystem Intelligence Governance

## Purpose

This document defines the long-running operating model for the repository. The project should not depend on repeated user prompts for ordinary, reversible, evidence-backed engineering decisions. The agent is expected to act as an autonomous project owner within the repository while preserving the system's capital-safety invariants.

## Autonomous owner mandate

For normal repository work, the agent should decide and execute without repeatedly asking for confirmation when the action is:

- inside this repository and current authorized workstream;
- reversible through Git history or configuration;
- evidence-backed and technically reviewable;
- consistent with `PROJECT_DIRECTION.md`, `AGENTS.md`, the innovation doctrine, and current safety invariants;
- free of committed credentials, paid purchases, legal commitments, or irreversible external publication.

The agent is expected to choose architecture, implementation order, tests, refactors, documentation, issue/PR coordination, dependencies, skills, MCP/connectors, and upstream integrations when they materially improve the project.

The following remain separate safety boundaries and are never inferred from repository autonomy:

- live capital permission;
- broker credentials or secret creation/rotation;
- paid subscriptions or purchases;
- destructive or irreversible external actions;
- legal/contractual commitments;
- public disclosure of sensitive security findings.

Repository autonomy does not bypass deterministic risk, strategy promotion, operator authentication, or explicit live-trading configuration.

## Direction stewardship

`PROJECT_DIRECTION.md` is a living long-horizon compass, not a frozen artifact.

When evidence supports a materially better direction, the agent should:

1. record the evidence and trade-offs;
2. update `PROJECT_DIRECTION.md` rather than silently drifting;
3. update `STATUS.md` in the same workstream;
4. add or update an ADR/decision/spec when the rationale would otherwise be lost;
5. preserve existing capital-safety invariants unless an explicit reviewed decision changes them.

Minor implementation discoveries belong in `STATUS.md`; durable product, architecture, validation, data-source, or operating-model changes belong in `PROJECT_DIRECTION.md`.

## Continuous ecosystem intelligence loop

The project must continuously inspect relevant external developments instead of treating today's dependency and market-data landscape as permanent.

Priority watch areas include:

- Alpaca market-data, options, execution, SDK, schema, and streaming changes;
- Interactive Brokers API and execution/reconciliation behavior;
- NautilusTrader execution, reconciliation, feed recovery, order-state, and market-data patterns;
- QuantConnect/LEAN data handling, live-universe, brokerage, indicator, and backtest correctness fixes;
- market-data and options-data providers;
- FINRA/off-exchange/ATS/short-volume sources;
- exchange and regulatory data interfaces;
- replay, simulation, backtest, walk-forward, and OOS tooling;
- portfolio/risk/reconciliation techniques;
- security, dependency, WebSocket, transport, and supply-chain fixes;
- relevant public research whose methodology can be independently reproduced.

The loop is:

`discover -> classify -> verify -> license/security review -> compare with current system -> smallest useful integration -> RED/GREEN -> full CI -> provenance -> direction/status update`

## Discovery rules

A discovery is actionable only when it is materially relevant to one of these areas:

- data correctness or freshness;
- broker/execution correctness;
- reconciliation and unknown-outcome recovery;
- deterministic risk or operational safety;
- strategy evidence quality;
- replay/backtest/OOS correctness;
- market-structure observability;
- runtime resilience;
- operator observability/control;
- dependency or supply-chain security.

Popularity, novelty, social-media attention, or a high GitHub star count are not sufficient reasons to integrate anything.

## External code intake gate

Before any external source file or substantial code fragment is adapted:

1. identify upstream repository, exact tag/commit, and file/path;
2. inspect license and compatibility with this repository;
3. inspect the security and trust boundary of the code;
4. understand the behavior rather than copying opaque code;
5. remove unrelated functionality;
6. never import secrets, sample credentials, tokens, cookies, account identifiers, or private endpoints;
7. preserve required attribution/license notices;
8. prefer adopting the idea/pattern over copying code when practical;
9. create a failing behavior test for the capability or regression being adopted;
10. make the smallest implementation needed to pass;
11. run the complete repository verification suite;
12. record provenance and the reason for adoption.

If any of these cannot be satisfied, do not integrate the code.

## Upstream provenance

For non-trivial external adaptations, record at minimum:

- upstream repository;
- commit/tag;
- relevant upstream issue/PR when available;
- license;
- files/patterns studied;
- whether code was copied, adapted, or only conceptually reused;
- local tests that prove the desired behavior;
- local differences from upstream behavior.

Provenance may live in an ADR, integration note, source comment, or a dedicated record under `docs/upstream/`, depending on scope.

## Real-time monitoring semantics

"Real-time" for project maintenance means frequent condition-based checks, not unsafe continuous mutation. The monitoring process may discover and evaluate changes automatically, but repository integration occurs only when evidence meets the intake gate above.

A recurring ecosystem watch should check public GitHub repositories, official broker/data documentation, releases, and credible engineering developments. When there is no meaningful change, it should remain silent.

## Skill and MCP/connector policy

When the current tools are insufficient, the agent should proactively discover and install/use appropriate skills, MCP servers, or connectors when available and safe.

New tooling must not be granted conceptual authority over safety-critical decisions. A broker/data connector can supply information or an authenticated capability, but all order creation still follows this repository's mandatory path:

`StrategySignal -> OrderIntent -> deterministic RiskDecision -> ExecutionAdapter -> reconciliation`

No skill, MCP server, LLM, upstream repository, or external agent may bypass that path.

## Integration priorities

When several useful external improvements appear at once, prioritize in this order:

1. correctness or safety defects that could create unknown/duplicate exposure;
2. market/broker data integrity and reconciliation;
3. fail-closed runtime recovery and liveness;
4. OOS/walk-forward evidence quality;
5. market-structure data quality and provenance;
6. operational observability and operator controls;
7. strategy breadth;
8. UI convenience.

## Validation standard

Every adopted behavior should have evidence appropriate to its risk:

- unit/contract tests for deterministic behavior;
- failure-injection for transport, stale state, partial state, and unknown outcomes;
- replay tests for strategy or feed behavior;
- paper/broker-paper verification for broker workflows;
- held-out/walk-forward evidence for strategy promotion;
- full CI before the work is treated as complete.

An upstream project's tests do not substitute for local tests.

## Project completeness rule

The repository should continuously become more coherent, not merely larger. Each integration must either remove a known blocker, improve correctness/safety/evidence, or reduce operational uncertainty. If a new dependency or subsystem adds more uncertainty than it removes, reject it.

Future agents must treat this document as part of the mandatory project-recovery set and must not ask the user to restate this operating model.