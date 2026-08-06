from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / "app", ROOT / "tests", ROOT / "scripts"]
errors: list[str] = []

for target in TARGETS:
    for path in sorted(target.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            errors.append(f"{path.relative_to(ROOT)}:{exc.lineno}: syntax error: {exc.msg}")
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.rstrip() != line:
                errors.append(f"{path.relative_to(ROOT)}:{line_number}: trailing whitespace")
            if "\t" in line:
                errors.append(f"{path.relative_to(ROOT)}:{line_number}: tab character")
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: wildcard import is prohibited"
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec"}:
                    errors.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: {node.func.id} is prohibited"
                    )

if errors:
    raise SystemExit("\n".join(errors))
print("static-check-pass")
