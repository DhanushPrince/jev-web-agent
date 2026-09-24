#!/usr/bin/env bash
#
# run.sh — run the Jev inspector on localhost (no dependency install).
#
# Assumes dependencies are already installed (run ./start.sh once, or `uv sync`).
# What it does:
#   1. Kills whatever is bound to the demo port (default 8766) + stray demo processes.
#   2. Ensures browser-harness has a live Chrome tab (clears stale targets).
#   3. Starts the inspector server and waits until it responds.
#
# Usage:
#   ./run.sh                # foreground (Ctrl-C to stop)
#   ./run.sh --background   # run detached, logs to /tmp/jev_run.log
#   PORT=9000 ./run.sh      # use a different port

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PORT="${PORT:-8766}"
LOG="${LOG:-/tmp/jev_run.log}"
BACKGROUND=0
[[ "${1:-}" == "--background" || "${1:-}" == "-b" ]] && BACKGROUND=1

echo "==> Jev inspector (port ${PORT})"

if ! command -v uv >/dev/null 2>&1; then
  echo "!!  'uv' is not installed. Install it: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

# 1. Kill anything on the port and any stray demo processes.
echo "--> Stopping any existing server..."
if PIDS="$(lsof -ti "tcp:${PORT}" 2>/dev/null)"; then
  [[ -n "$PIDS" ]] && echo "    killing pids on :${PORT}: $PIDS" && kill -9 $PIDS 2>/dev/null || true
fi
pkill -f "jev_ultrafast.demo" 2>/dev/null || true
sleep 2

# 2. Ensure a live browser tab so the harness has a fresh target to attach to.
echo "--> Ensuring a live browser tab..."
uv run browser-harness <<'PY' 2>/dev/null || echo "    (warning: could not ensure a tab; open Chrome and allow remote debugging)"
ensure_real_tab()
print("    tab ready")
PY

# 3. Start the server.
if [[ "$BACKGROUND" -eq 1 ]]; then
  echo "--> Starting server in background (logs: ${LOG})..."
  TYPESAFE_DEMO_PORT="$PORT" nohup uv run jev > "$LOG" 2>&1 &
  echo "    pid $!"
  for i in $(seq 1 20); do
    if curl -s -o /dev/null "http://127.0.0.1:${PORT}/"; then
      echo "==> Ready: http://127.0.0.1:${PORT}/"
      exit 0
    fi
    sleep 0.5
  done
  echo "!!  Server did not respond in time; check ${LOG}"
  tail -20 "$LOG" || true
  exit 1
else
  echo "--> Starting server (foreground; Ctrl-C to stop)..."
  echo "==> Open: http://127.0.0.1:${PORT}/"
  exec env TYPESAFE_DEMO_PORT="$PORT" uv run jev
fi
