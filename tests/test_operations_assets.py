from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cloud_and_ci_assets_exist_and_keep_live_trading_disabled() -> None:
    required = [
        "Dockerfile",
        "docker-compose.yml",
        ".env.example",
        ".dockerignore",
        ".github/workflows/ci.yml",
        ".github/workflows/daily-research.yml",
        ".github/workflows/pages.yml",
        "README.md",
        "docs/SECURITY.md",
        "scripts/loop_verify.sh",
    ]
    for relative in required:
        assert (ROOT / relative).exists(), relative

    env_text = (ROOT / ".env.example").read_text(encoding="utf-8")
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    workflow_text = (ROOT / ".github/workflows/daily-research.yml").read_text(
        encoding="utf-8"
    )

    assert "LIVE_TRADING_ENABLED=false" in env_text
    assert "WITHDRAW" not in env_text.upper()
    assert "no-new-privileges:true" in compose_text
    assert "pull-requests: write" in workflow_text
    assert "create-pull-request" in workflow_text
    assert "python -m pip install '.[dev]'".replace(" ", "") in workflow_text.replace(" ", "")

    verify = (ROOT / "scripts/loop_verify.sh").read_text(encoding="utf-8")
    assert "python scripts/build_static_site.py --output site" in verify
    assert "site/backend-actions.js" in verify
    assert "PUBLIC DATA / OBSERVE ONLY" in verify
    assert "BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY" in verify


def test_repository_never_contains_example_secret_values() -> None:
    env_path = ROOT / ".env.example"
    env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    forbidden = ["sk_live_", "AKIA", "BEGIN PRIVATE KEY", "api_secret=secret"]
    assert not any(value.lower() in env_text.lower() for value in forbidden)


def test_upstream_projects_are_pinned_and_isolated() -> None:
    import json
    import re

    catalog_path = ROOT / "upstreams/catalog.json"
    bootstrap_path = ROOT / "scripts/bootstrap_upstreams.sh"
    assert catalog_path.exists()
    assert bootstrap_path.exists()

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    projects = catalog["projects"]
    assert {project["name"] for project in projects} == {
        "lean",
        "freqtrade",
        "hummingbot",
        "ccxt",
        "nautilus-trader",
    }
    for project in projects:
        assert re.fullmatch(r"[0-9a-f]{40}", project["commit"])
        assert project["enabled_by_default"] is False
        assert project["integration"] in {"container", "library-process-isolated"}
        assert project["license"] in {"Apache-2.0", "MIT", "GPL-3.0", "LGPL-3.0"}

    bootstrap = bootstrap_path.read_text(encoding="utf-8")
    assert "git checkout --detach" in bootstrap
    assert "catalog.json" in bootstrap


def test_pages_workflow_builds_and_deploys_observe_only_site() -> None:
    workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v4" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "python scripts/build_static_site.py --output site" in workflow
    assert "path: site" in workflow
    assert "environment:" in workflow
    assert "github-pages" in workflow
    assert "observe-only" in readme.lower()
    assert "jinngimk-lang.github.io/global-market-agent-observatory" in readme
