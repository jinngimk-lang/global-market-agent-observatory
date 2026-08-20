# Global Market Autonomous Trading Platform — Agent Guide

This repository is the primary autonomous market monitoring and trading platform. It supports replay, paper, broker-paper, and deliberately enabled live execution. Safety-critical trading behavior must remain deterministic and fail closed.

## Mandatory context recovery

`PROJECT_DIRECTION.md` is the long-horizon source of truth for product direction.

Every agent must read `PROJECT_DIRECTION.md` in full:

- at the start of a new implementation session;
- when resuming after a long interruption;
- when conversational/model context is incomplete or uncertain;
- before a major architectural decision;
- whenever implementation appears to conflict with the project's intended direction.

After reading `PROJECT_DIRECTION.md`, read `CONTEXT.md` and relevant ADRs/specs/plans for the current change. Inspect the current branch and recent commits before editing code.

Do not silently drift away from `PROJECT_DIRECTION.md`. If the product direction genuinely changes, update that document deliberately as part of the change.

## Product safety boundary

Live execution is a first-class capability but must be OFF by default. It may only be enabled by explicit runtime configuration and must never be inferred merely from the presence of broker credentials.

The mandatory execution path is:

`StrategySignal -> OrderIntent -> deterministic RiskDecision -> ExecutionAdapter -> reconciliation`

No LLM, research agent, strategy module, UI action, or external signal may bypass deterministic risk approval.

The system must fail closed when market data, broker state, reconciliation state, or execution outcome is stale, missing, or uncertain.

## Agent skills

The engineering skill collection is pinned in `.agents/skills.lock.json`. Initialize it with `./scripts/bootstrap_agent_skills.sh`; skills are exposed through `.agents/skills/`.

### Issue tracker

Work is tracked in GitHub Issues for `jinngimk-lang/global-market-agent-observatory`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the canonical triage vocabulary documented in `docs/agents/triage-labels.md`.

### Domain docs

Read `PROJECT_DIRECTION.md`, `CONTEXT.md`, and relevant ADRs under `docs/adr/` before changing system behavior. See `docs/agents/domain.md`.

## Engineering rules

- Use a failing behavior test before implementation where a stable public seam exists.
- Keep strategy output separate from deterministic risk approval and broker execution.
- Never commit credentials, account tokens, private keys, cookies, or real account identifiers.
- Live trading must be disabled by default and explicitly enabled at runtime.
- Unknown execution outcomes must reconcile before any retry that could duplicate an order.
- Orders must use idempotent client order identifiers.
- Kill-switch behavior must not depend on an LLM or research service.
- Broker/account reconciliation is mandatory for live execution.
- External code may only be adapted after license/security review and must retain required attribution.
- Run targeted tests during implementation, then the complete test suite and static checks before committing.
- Review every change against repository standards, `PROJECT_DIRECTION.md`, and the originating requirement.
