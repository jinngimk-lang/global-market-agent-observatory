#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CATALOG="$ROOT_DIR/upstreams/catalog.json"
DESTINATION="${UPSTREAM_ROOT:-$ROOT_DIR/.upstreams}"
SELECTED="${1:-all}"

mkdir -p "$DESTINATION"

python - "$CATALOG" "$DESTINATION" "$SELECTED" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

catalog_path = Path(sys.argv[1])
destination = Path(sys.argv[2])
selected = sys.argv[3]
projects = json.loads(catalog_path.read_text(encoding="utf-8"))["projects"]
if selected != "all":
    projects = [project for project in projects if project["name"] == selected]
    if not projects:
        raise SystemExit(f"Unknown upstream: {selected}")

for project in projects:
    target = destination / project["name"]
    if not target.exists():
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", project["repository"], str(target)],
            check=True,
        )
    subprocess.run(["git", "-C", str(target), "fetch", "--depth=1", "origin", project["commit"]], check=True)
    # Equivalent shell command: git checkout --detach <commit>
    subprocess.run(["git", "-C", str(target), "checkout", "--detach", project["commit"]], check=True)
    actual = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
    if actual != project["commit"]:
        raise SystemExit(f"Pin verification failed for {project['name']}: {actual}")
    print(f"installed {project['name']} at {actual}")
PY
