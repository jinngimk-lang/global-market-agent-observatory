from pathlib import Path


INDEX = Path("app/web/index.html")
APP = Path("app/web/app.js")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_every_enabled_primary_action_has_a_result_surface():
    html = _read(INDEX)
    js = _read(APP)

    assert 'id="refresh-button"' in html
    assert 'id="research-button"' in html
    assert 'id="order-form"' in html
    assert 'id="order-message"' in html

    assert "refresh-button').addEventListener('click'" in js
    assert "research-button').addEventListener('click'" in js
    assert "order-form').addEventListener('submit'" in js

    # Refresh must expose an explicit result state rather than silently finishing.
    assert "refresh-status" in html
    assert "setRefreshStatus" in js


def test_refresh_and_startup_failures_have_recovery_paths():
    js = _read(APP)

    # A failed action must not leave an unhandled rejection/dead UI state.
    assert "async function runRefresh" in js
    assert "try {" in js
    assert "catch" in js
    assert "finally" in js
    assert "retry-button" in js


def test_observe_only_boundary_remains_visible_and_non_executable():
    html = _read(INDEX)
    js = _read(APP)

    assert "LIVE DISABLED" in html
    assert "GLOBAL KILL SWITCH · PAPER ONLY" in html
    assert "if (!runtime.capabilities.paperOrders)" in js
    assert "control.disabled = true" in js
