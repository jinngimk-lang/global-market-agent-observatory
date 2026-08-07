from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


def run_node(source: str) -> dict:
    if NODE is None:
        pytest.skip("node is not available")
    result = subprocess.run(
        [NODE, "-e", source],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_action_runner_recovers_after_failure_and_can_retry() -> None:
    action_path = ROOT / "app" / "web" / "action-state.js"
    assert action_path.exists(), "action-state helper is required for recoverable UI actions"

    action_path_json = json.dumps(str(action_path))
    payload = run_node(
        f"""
const fs = require('fs');
const vm = require('vm');
const context = vm.createContext({{window: {{}}}});
vm.runInContext(fs.readFileSync({action_path_json}, 'utf8'), context);
const button = {{disabled: false, textContent: '刷新', dataset: {{}}}};
const runner = context.window.ObservatoryActionState.create(button, {{
  idle: '刷新',
  pending: '刷新中…',
  success: '已刷新',
  failure: '刷新失败 · 重试',
}});
(async () => {{
  const first = await runner.run(async () => {{ throw new Error('boom'); }});
  const afterFailure = {{
    ok: first.ok,
    disabled: button.disabled,
    text: button.textContent,
    state: button.dataset.state,
  }};
  const second = await runner.run(async () => 42);
  const afterRetry = {{
    ok: second.ok,
    value: second.value,
    disabled: button.disabled,
    text: button.textContent,
    state: button.dataset.state,
  }};
  console.log(JSON.stringify({{afterFailure, afterRetry}}));
}})();
"""
    )

    assert payload["afterFailure"] == {
        "ok": False,
        "disabled": False,
        "text": "刷新失败 · 重试",
        "state": "error",
    }
    assert payload["afterRetry"] == {
        "ok": True,
        "value": 42,
        "disabled": False,
        "text": "已刷新",
        "state": "success",
    }
