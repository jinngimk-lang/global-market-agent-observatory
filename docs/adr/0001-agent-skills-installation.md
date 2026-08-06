# ADR 0001: Pin the engineering skills collection

- Status: Accepted
- Date: 2026-08-06

## Context

The project needs a repeatable engineering workflow for setup, TDD, debugging, research, implementation, and review. Installing an unpinned moving branch would allow upstream behavior to change without review.

## Decision

Install `mattpocock/skills` as a Git submodule at `.agents/vendor/mattpocock-skills`, pinned to commit `8b36d4fb2635b3c21998dcd8144439c9e5ba7302` (release 1.2.2). Expose its `skills/` directory through `.agents/skills`. Record the source and expected commit in `.agents/skills.lock.json` and verify it in `scripts/bootstrap_agent_skills.sh`.

Updates are manual: review the upstream diff, update the gitlink and lock file together, run the repository test suite, and submit a pull request.

## Consequences

- Clones must initialize submodules before local agent discovery.
- Skill behavior is stable and auditable.
- Upstream security or quality fixes require an explicit reviewed update.
