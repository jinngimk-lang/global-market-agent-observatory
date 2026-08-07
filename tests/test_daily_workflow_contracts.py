from pathlib import Path

WORKFLOW = Path(".github/workflows/daily-research.yml")


def test_daily_research_skips_empty_updates_and_recovers_blocked_pr_creation():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "id: research_delta" in workflow
    assert "has_records" in workflow
    assert "steps.research_delta.outputs.has_records == 'true'" in workflow
    assert "id: research_pr" in workflow
    assert "continue-on-error: true" in workflow
    assert "steps.research_pr.outcome == 'failure'" in workflow
    assert "git ls-remote --exit-code origin refs/heads/automation/daily-official-research" in workflow
