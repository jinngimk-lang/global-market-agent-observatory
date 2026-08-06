#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export DATABASE_PATH="${DATABASE_PATH:-$ROOT/data/verify.db}"
export MARKET_SOURCE="replay"
export REPLAY_DELAY_SECONDS="0.05"
export LIVE_TRADING_ENABLED="false"

rm -f "$DATABASE_PATH" "$DATABASE_PATH-shm" "$DATABASE_PATH-wal"
bash -n scripts/loop_verify.sh scripts/bootstrap_upstreams.sh scripts/bootstrap_agent_skills.sh
python - <<'PY'
import json
from pathlib import Path

catalog = json.loads(Path("upstreams/catalog.json").read_text(encoding="utf-8"))
assert len(catalog["projects"]) == 5
assert all(project["enabled_by_default"] is False for project in catalog["projects"])
PY

rm -rf site
python scripts/build_static_site.py --output site
test -f site/index.html
test -f site/config.js
test ! -e site/backend-actions.js
grep -q "mode: 'static'" site/config.js
grep -q "PUBLIC DATA / OBSERVE ONLY" site/demo-data.js
if grep -R -E "BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|ALPACA_API_SECRET|IBKR_ACCOUNT_ID" site; then
  echo "static site contains a secret-like token" >&2
  exit 1
fi
if grep -R -E "/api/orders|/api/research/refresh|method: ['\"]POST['\"]" site/*.js; then
  echo "static site contains a write-capable endpoint" >&2
  exit 1
fi

python -m compileall -q app scripts
if command -v ruff >/dev/null 2>&1; then
  ruff check .
elif python -c "import ruff" >/dev/null 2>&1; then
  python -m ruff check .
else
  python scripts/static_check.py
fi
python -m pytest -q
python - <<'PY'
from pydantic import ValidationError
from app.settings import Settings

try:
    Settings(live_trading_enabled=True)
except ValidationError:
    pass
else:
    raise SystemExit("live trading safety validation did not fail")
PY

PORT="${VERIFY_PORT:-18765}"
STATIC_PORT="$((PORT + 1))"
python -m http.server "$STATIC_PORT" --bind 127.0.0.1 --directory site >/tmp/observatory-static-verify.log 2>&1 &
STATIC_PID=$!
python -m uvicorn app.api.main:app --host 127.0.0.1 --port "$PORT" >/tmp/observatory-verify.log 2>&1 &
SERVER_PID=$!
cleanup() {
  kill "$STATIC_PID" "$SERVER_PID" 2>/dev/null || true
  wait "$STATIC_PID" "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 50); do
  if python - "$PORT" "$STATIC_PORT" <<'PY'
import json
import sys
import urllib.request

port = sys.argv[1]
static_port = sys.argv[2]
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
        payload = json.load(response)
    with urllib.request.urlopen(f"http://127.0.0.1:{static_port}/", timeout=1) as response:
        static_html = response.read().decode("utf-8")
    if (
        payload.get("status") == "ok"
        and payload.get("live_trading_enabled") is False
        and "./config.js" in static_html
    ):
        raise SystemExit(0)
except Exception:
    pass
raise SystemExit(1)
PY
  then
    break
  fi
  sleep 0.1
done

python - "$PORT" "$STATIC_PORT" <<'PY'
import json
import sys
import urllib.request

port = sys.argv[1]
static_port = sys.argv[2]
with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3) as response:
    payload = json.load(response)
assert payload["status"] == "ok"
assert payload["trading_mode"] == "paper"
assert payload["live_trading_enabled"] is False
with urllib.request.urlopen(f"http://127.0.0.1:{static_port}/config.js", timeout=3) as response:
    static_config = response.read().decode("utf-8")
assert "mode: 'static'" in static_config
print(json.dumps(payload, ensure_ascii=False))
PY

cleanup
trap - EXIT

if [[ "${LOOP_VERIFY_DOCKER:-0}" == "1" ]] && command -v docker >/dev/null 2>&1; then
  docker build -t global-market-agent-observatory:verify .
fi

echo "verification-pass"
