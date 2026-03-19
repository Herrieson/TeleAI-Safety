#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.dev-runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PID_FILE="$RUNTIME_DIR/pids.env"

ORCH_URL="${ORCHESTRATOR_BASE_URL:-http://127.0.0.1:9001}"
BFF_URL="${BFF_BASE_URL:-http://127.0.0.1:9000}"
WEB_URL="${WEB_BASE_URL:-http://127.0.0.1:3000}"
BFF_CORS_ORIGINS="${BFF_CORS_ALLOW_ORIGINS:-http://127.0.0.1:3000,http://localhost:3000}"
ORCH_PID=""
BFF_PID=""
WEB_PID=""

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[dev_up] missing command: $1" >&2
    exit 1
  fi
}

is_alive() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

wait_http_ok() {
  local url="$1"
  local label="$2"
  local retries="${3:-30}"
  local i

  for ((i=1; i<=retries; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "[dev_up] $label is ready: $url"
      return 0
    fi
    sleep 1
  done

  echo "[dev_up] $label did not become ready: $url" >&2
  return 1
}

cleanup_on_error() {
  local exit_code="$1"
  if [[ "$exit_code" -eq 0 ]]; then
    return
  fi

  for pid in "$WEB_PID" "$BFF_PID" "$ORCH_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}
trap 'cleanup_on_error $?' EXIT

require_cmd uv
require_cmd npm
require_cmd curl

mkdir -p "$LOG_DIR"

if [[ -f "$PID_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$PID_FILE"
  if is_alive "${ORCH_PID:-}" || is_alive "${BFF_PID:-}" || is_alive "${WEB_PID:-}"; then
    echo "[dev_up] existing dev services detected. Run scripts/dev_down.sh first." >&2
    exit 1
  fi
fi

cd "$ROOT_DIR"
nohup uv run python -m uvicorn services.orchestrator.app.main:app --host 127.0.0.1 --port 9001 --reload \
  >"$LOG_DIR/orchestrator.log" 2>&1 &
ORCH_PID=$!
echo "[dev_up] started orchestrator pid=$ORCH_PID"
wait_http_ok "$ORCH_URL/health" "orchestrator"

cd "$ROOT_DIR"
nohup env ORCHESTRATOR_BASE_URL="$ORCH_URL" BFF_CORS_ALLOW_ORIGINS="$BFF_CORS_ORIGINS" \
  uv run python -m uvicorn services.bff.app.main:app --host 127.0.0.1 --port 9000 --reload \
  >"$LOG_DIR/bff.log" 2>&1 &
BFF_PID=$!
echo "[dev_up] started bff pid=$BFF_PID"
wait_http_ok "$BFF_URL/api/health" "bff"

cd "$ROOT_DIR/web"
nohup npm run dev >"$LOG_DIR/web.log" 2>&1 &
WEB_PID=$!
echo "[dev_up] started web pid=$WEB_PID"
wait_http_ok "$WEB_URL/runs" "web"

cat >"$PID_FILE" <<PIDS
ORCH_PID=$ORCH_PID
BFF_PID=$BFF_PID
WEB_PID=$WEB_PID
PIDS

trap - EXIT

echo "[dev_up] all services started"
echo "[dev_up] web:  $WEB_URL/runs"
echo "[dev_up] bff:  $BFF_URL/api/health"
echo "[dev_up] orch: $ORCH_URL/health"
echo "[dev_up] logs: $LOG_DIR"
