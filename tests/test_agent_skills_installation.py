import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mattpocock_skills_are_pinned_and_bootstrappable() -> None:
    gitmodules = (ROOT / ".gitmodules").read_text(encoding="utf-8")
    lock = json.loads((ROOT / ".agents" / "skills.lock.json").read_text(encoding="utf-8"))
    bootstrap = (ROOT / "scripts" / "bootstrap_agent_skills.sh").read_text(encoding="utf-8")

    assert "mattpocock/skills" in gitmodules
    assert lock["source"] == "https://github.com/mattpocock/skills"
    assert lock["commit"] == "8b36d4fb2635b3c21998dcd8144439c9e5ba7302"
    assert "git submodule update --init --recursive" in bootstrap
    assert "8b36d4fb2635b3c21998dcd8144439c9e5ba7302" in bootstrap


def test_agent_setup_documents_the_project_workflow() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    issue_tracker = (ROOT / "docs" / "agents" / "issue-tracker.md").read_text(encoding="utf-8")
    triage = (ROOT / "docs" / "agents" / "triage-labels.md").read_text(encoding="utf-8")
    domain = (ROOT / "docs" / "agents" / "domain.md").read_text(encoding="utf-8")

    assert "## Agent skills" in agents
    assert "GitHub Issues" in issue_tracker
    assert "needs-triage" in triage
    assert "single-context" in domain
    assert "CONTEXT.md" in domain
