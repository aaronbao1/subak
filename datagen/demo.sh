#!/usr/bin/env bash
# One-command live demo: load the simulated company into the backend (first run only), start the backend
# on that database, and stream live usage into it until Ctrl-C.
#
#   datagen/demo.sh                         # backend on :8787, live feed every 2 s
#   datagen/demo.sh --interval 1 --speed 100 --people 20
#
# Point the frontend at it with NEXT_PUBLIC_API_URL=http://localhost:8787/compat in frontend/.env.local.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/backend/.venv/bin/python"
DB="${BACKEND_DB_PATH:-$ROOT/backend/data/uber.db}"
PORT="${BACKEND_PORT:-8787}"

[ -x "$PY" ] || { echo "backend/.venv missing: python3 -m venv backend/.venv && backend/.venv/bin/pip install -e 'backend[dev]'"; exit 1; }
[ -f "$ROOT/datagen/out/backend/reference.json" ] || python3 "$ROOT/datagen/generate.py" --quiet
"$PY" "$ROOT/datagen/load_backend.py" --db "$DB"

(cd "$ROOT/backend" && BACKEND_DB_PATH="$DB" BACKEND_PORT="$PORT" BACKEND_COMPANY_ID="${BACKEND_COMPANY_ID:-uber-sim}" BACKEND_COMPANY_NAME="${BACKEND_COMPANY_NAME:-Uber (simulated)}" exec "$PY" -m app.main) &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
"$PY" - "$PORT" <<'PY'
import sys, time, urllib.request
port = sys.argv[1]
for _ in range(100):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2); break
    except Exception:
        time.sleep(0.3)
else:
    sys.exit("backend did not start")
PY
echo "backend up on http://127.0.0.1:$PORT (compat API at /compat/api). Streaming live usage; Ctrl-C stops both."
python3 "$ROOT/datagen/live.py" --api "http://127.0.0.1:$PORT" "$@"
