# Global Market Agent Observatory — Agent Guide

The system is a read-only market observatory and paper-trading research platform. Real-money order execution, withdrawals, transfers, and custody actions stay disabled unless a separately reviewed production change explicitly enables them.

## Agent skills

The engineering skill collection is pinned in `.agents/skills.lock.json`. Initialize it with `./scripts/bootstrap_agent_skills.sh`; skills are exposed through `.agents/skills/`.

### Issue tracker

Work is tracked in GitHub Issues for `jinngimk-lang/global-market-agent-observatory`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the canonical triage vocabulary documented in `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository. Read `CONTEXT.md` and relevant ADRs under `docs/adr/` before changing behavior. See `docs/agents/domain.md`.

## Engineering rules

- Use a failing behavior test before implementation where a stable public seam exists.
- Keep agent-generated intent separate from deterministic risk approval and broker execution.
- Never commit credentials, account tokens, private keys, cookies, or real account identifiers.
- Default all broker and exchange connectors to read-only or sandbox/paper mode.
- Run targeted tests during implementation, then the complete test suite and static checks before committing.
- Review every change against both repository standards and the originating requirement.
