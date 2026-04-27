#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.dev-runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PID_FILE="$RUNTIME_DIR/pids.env"
LOCAL_ENV_FILE="$ROOT_DIR/.env.local"
ROOT_ENV_FILE="$ROOT_DIR/.env"

ORCH_BIND_HOST="${ORCH_BIND_HOST:-0.0.0.0}"
ORCH_PORT="${ORCH_PORT:-9001}"
BFF_BIND_HOST="${BFF_BIND_HOST:-0.0.0.0}"
BFF_PORT="${BFF_PORT:-9000}"
WEB_BIND_HOST="${WEB_BIND_HOST:-0.0.0.0}"
WEB_PORT="${WEB_PORT:-3000}"

default_local_url() {
  local port="$1"
  echo "http://127.0.0.1:$port"
}

ORCH_LOCAL_URL="${ORCH_LOCAL_URL:-$(default_local_url "$ORCH_PORT")}"
BFF_LOCAL_URL="${BFF_LOCAL_URL:-$(default_local_url "$BFF_PORT")}"
WEB_LOCAL_URL="${WEB_LOCAL_URL:-$(default_local_url "$WEB_PORT")}"
ORCH_URL="${ORCHESTRATOR_BASE_URL:-$ORCH_LOCAL_URL}"

WEB_SERVER_BFF_BASE_URL="${BFF_BASE_URL:-$BFF_LOCAL_URL}"

if [[ "${NEXT_PUBLIC_BFF_BASE_URL+x}" == x ]]; then
  WEB_PUBLIC_BFF_BASE_URL="$NEXT_PUBLIC_BFF_BASE_URL"
else
  WEB_PUBLIC_BFF_BASE_URL=""
fi

BFF_CORS_ORIGINS="${BFF_CORS_ALLOW_ORIGINS:-http://127.0.0.1:${WEB_PORT},http://localhost:${WEB_PORT}}"
ORCH_PID=""
BFF_PID=""
WEB_PID=""

load_env_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$file"
    set +a
  fi
}

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

extract_port_from_url() {
  local url="$1"
  local hostport
  hostport="${url#*://}"
  hostport="${hostport%%/*}"
  if [[ "$hostport" == *:* ]]; then
    echo "${hostport##*:}"
    return
  fi
  if [[ "$url" == https://* ]]; then
    echo "443"
    return
  fi
  echo "80"
}

port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "$port" >/dev/null 2>&1
    return $?
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :$port )" 2>/dev/null | tail -n +2 | grep -q .
    return $?
  fi
  return 1
}

describe_port_owner() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN | sed -n '2p'
    return
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser -v -n tcp "$port" 2>/dev/null | tail -n +2 | head -n 1
    return
  fi
  echo "owner unknown (install lsof/fuser for details)"
}

ensure_port_free() {
  local port="$1"
  local name="$2"
  if port_in_use "$port"; then
    echo "[dev_up] port $port already in use ($name)" >&2
    echo "[dev_up] listener: $(describe_port_owner "$port")" >&2
    echo "[dev_up] run scripts/dev_down.sh or stop the process above, then retry." >&2
    exit 1
  fi
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
require_cmd node
require_cmd curl
require_cmd setsid

load_env_file "$ROOT_ENV_FILE"
load_env_file "$LOCAL_ENV_FILE"

start_detached() {
  local log_file="$1"
  shift

  setsid "$@" </dev/null >"$log_file" 2>&1 &
  echo $!
}

mkdir -p "$LOG_DIR"

if [[ -f "$PID_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$PID_FILE"
  if is_alive "${ORCH_PID:-}" || is_alive "${BFF_PID:-}" || is_alive "${WEB_PID:-}"; then
    echo "[dev_up] existing dev services detected. Run scripts/dev_down.sh first." >&2
    exit 1
  fi
fi

ensure_port_free "$ORCH_PORT" "orchestrator"
ensure_port_free "$BFF_PORT" "bff"
ensure_port_free "$WEB_PORT" "web"

cd "$ROOT_DIR"
ORCH_PID=$(start_detached "$LOG_DIR/orchestrator.log" \
  uv run python -m uvicorn services.orchestrator.app.main:app --host "$ORCH_BIND_HOST" --port "$ORCH_PORT")
echo "[dev_up] started orchestrator pid=$ORCH_PID"
wait_http_ok "$ORCH_LOCAL_URL/health" "orchestrator"

cd "$ROOT_DIR"
BFF_PID=$(start_detached "$LOG_DIR/bff.log" \
  env ORCHESTRATOR_BASE_URL="$ORCH_URL" BFF_CORS_ALLOW_ORIGINS="$BFF_CORS_ORIGINS" \
  uv run python -m uvicorn services.bff.app.main:app --host "$BFF_BIND_HOST" --port "$BFF_PORT")
echo "[dev_up] started bff pid=$BFF_PID"
wait_http_ok "$BFF_LOCAL_URL/api/health" "bff"

cd "$ROOT_DIR/web"
# Use Next.js CLI directly so the recorded PID maps to the long-lived dev process.
WEB_PID=$(start_detached "$LOG_DIR/web.log" \
  env BFF_BASE_URL="$WEB_SERVER_BFF_BASE_URL" NEXT_PUBLIC_BFF_BASE_URL="$WEB_PUBLIC_BFF_BASE_URL" \
  node ./node_modules/next/dist/bin/next dev --hostname "$WEB_BIND_HOST" --port "$WEB_PORT")
echo "[dev_up] started web pid=$WEB_PID"
wait_http_ok "$WEB_LOCAL_URL/runs" "web"

cat >"$PID_FILE" <<PIDS
ORCH_PID=$ORCH_PID
BFF_PID=$BFF_PID
WEB_PID=$WEB_PID
PIDS

trap - EXIT

echo "[dev_up] all services started"
echo "[dev_up] web:  $WEB_LOCAL_URL/runs"
echo "[dev_up] bff:  $BFF_LOCAL_URL/api/health"
echo "[dev_up] orch: $ORCH_LOCAL_URL/health"
if [[ -n "$WEB_PUBLIC_BFF_BASE_URL" ]]; then
  echo "[dev_up] web api base: $WEB_PUBLIC_BFF_BASE_URL"
else
  echo "[dev_up] web api base: same-origin (/api via reverse proxy)"
fi
echo "[dev_up] web server bff base: $WEB_SERVER_BFF_BASE_URL"
echo "[dev_up] logs: $LOG_DIR"
