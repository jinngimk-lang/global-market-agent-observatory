#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED="8b36d4fb2635b3c21998dcd8144439c9e5ba7302"
SUBMODULE="$ROOT/.agents/vendor/mattpocock-skills"

cd "$ROOT"
git submodule sync -- .agents/vendor/mattpocock-skills
git submodule update --init --recursive .agents/vendor/mattpocock-skills

ACTUAL="$(git -C "$SUBMODULE" rev-parse HEAD)"
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
  echo "Skill commit mismatch: expected $EXPECTED, got $ACTUAL" >&2
  exit 1
fi

if [[ ! -f "$ROOT/.agents/skills/engineering/setup-matt-pocock-skills/SKILL.md" ]]; then
  echo "Skill discovery path is incomplete" >&2
  exit 1
fi

echo "Matt Pocock skills ready at $ACTUAL"
