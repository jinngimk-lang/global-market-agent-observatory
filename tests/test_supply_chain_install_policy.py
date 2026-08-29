from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ci_dependency_installs_reject_source_distributions() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()

    assert "python -m pip install --only-binary=:all: '.[dev]'" in workflow
    assert "python -m pip install --only-binary=:all: '.[dev]' 'pip-audit==2.10.1'" in workflow


def test_container_dependency_install_rejects_source_distributions() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert "python -m pip install --only-binary=:all: ." in dockerfile
