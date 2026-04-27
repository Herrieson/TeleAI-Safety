#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORCH_PORT="${ORCH_PORT:-9001}"
BFF_PORT="${BFF_PORT:-9000}"
WEB_PORT="${WEB_PORT:-3000}"
MODE="${DEV_RESTART_MODE:-external}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/dev_restart.sh
  bash scripts/dev_restart.sh --internal
  bash scripts/dev_restart.sh --external

What it does:
  1. Stops existing TeleAI-Safety dev services
  2. Cleans leftover listeners on the standard ports
  3. Starts orchestrator + bff + web again
  4. Uses external-access mode by default

Modes:
  --external  default; orchestrator/bff/web all bind to 0.0.0.0 and frontend uses same-origin /api
  --internal  localhost-only mode for local development

Optional env overrides:
  ORCH_PORT / BFF_PORT / WEB_PORT
  ORCH_BIND_HOST / BFF_BIND_HOST / WEB_BIND_HOST
  NEXT_PUBLIC_BFF_BASE_URL
  BFF_CORS_ALLOW_ORIGINS
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --external)
      MODE="external"
      shift
      ;;
    --internal)
      MODE="internal"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[dev_restart] unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

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

stop_port_listener() {
  local port="$1"
  local label="$2"
  local killed=0

  if command -v lsof >/dev/null 2>&1; then
    while IFS= read -r pid; do
      [[ -z "$pid" ]] && continue
      kill "$pid" >/dev/null 2>&1 || true
      killed=1
    done < <(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  elif command -v fuser >/dev/null 2>&1; then
    if fuser -k -TERM -n tcp "$port" >/dev/null 2>&1; then
      killed=1
    fi
  fi

  if [[ "$killed" -eq 1 ]]; then
    echo "[dev_restart] stopped leftover listener on port $port ($label)"
  fi
}

wait_port_free() {
  local port="$1"
  local label="$2"
  local i
  for ((i=1; i<=15; i++)); do
    if ! port_in_use "$port"; then
      return 0
    fi
    sleep 1
  done
  echo "[dev_restart] port $port is still in use after cleanup ($label)" >&2
  return 1
}

echo "[dev_restart] stopping existing services"
bash "$ROOT_DIR/scripts/dev_down.sh"

stop_port_listener "$WEB_PORT" "web"
stop_port_listener "$BFF_PORT" "bff"
stop_port_listener "$ORCH_PORT" "orchestrator"

wait_port_free "$WEB_PORT" "web"
wait_port_free "$BFF_PORT" "bff"
wait_port_free "$ORCH_PORT" "orchestrator"

if [[ "$MODE" == "external" ]]; then
  echo "[dev_restart] starting in external-access mode"
  export ORCH_BIND_HOST="${ORCH_BIND_HOST:-0.0.0.0}"
  export BFF_BIND_HOST="${BFF_BIND_HOST:-0.0.0.0}"
  export WEB_BIND_HOST="${WEB_BIND_HOST:-0.0.0.0}"
  export NEXT_PUBLIC_BFF_BASE_URL="${NEXT_PUBLIC_BFF_BASE_URL:-}"
else
  echo "[dev_restart] starting in internal localhost-only mode"
fi

bash "$ROOT_DIR/scripts/dev_up.sh"
