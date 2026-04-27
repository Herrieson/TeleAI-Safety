#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.dev-runtime"
PID_FILE="$RUNTIME_DIR/pids.env"
ORCH_PORT="${ORCH_PORT:-9001}"
BFF_PORT="${BFF_PORT:-9000}"
WEB_PORT="${WEB_PORT:-3000}"

stop_pid() {
  local pid="$1"
  local name="$2"

  if [[ -z "$pid" ]]; then
    return 0
  fi

  if ! kill -0 "$pid" >/dev/null 2>&1; then
    echo "[dev_down] $name already stopped (pid=$pid)"
    return 0
  fi

  kill "$pid" >/dev/null 2>&1 || true

  local i
  for ((i=1; i<=10; i++)); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "[dev_down] stopped $name (pid=$pid)"
      return 0
    fi
    sleep 1
  done

  kill -9 "$pid" >/dev/null 2>&1 || true
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    echo "[dev_down] force-stopped $name (pid=$pid)"
  else
    echo "[dev_down] failed to stop $name (pid=$pid)" >&2
  fi
}

stop_matching_pids() {
  local pattern="$1"
  local name="$2"

  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi

  local pid
  while IFS= read -r pid; do
    if [[ -z "$pid" ]]; then
      continue
    fi
    stop_pid "$pid" "$name"
  done < <(pgrep -f "$pattern" || true)
}

stop_stale_known_processes() {
  stop_matching_pids "services.orchestrator.app.main:app .* --port ${ORCH_PORT}( |$)" "orchestrator(stale)"
  stop_matching_pids "services.bff.app.main:app .* --port ${BFF_PORT}( |$)" "bff(stale)"
  stop_matching_pids "$ROOT_DIR/web/node_modules/next/dist/bin/next dev --hostname .* --port ${WEB_PORT}( |$)" "web(stale)"
  stop_matching_pids "$ROOT_DIR/web/node_modules/.bin/next dev --hostname .* --port ${WEB_PORT}( |$)" "web(stale-legacy)"
  stop_matching_pids "next-server \\(v[0-9.]+\\)" "web(next-server)"
}

if [[ -f "$PID_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$PID_FILE"

  stop_pid "${WEB_PID:-}" "web"
  stop_pid "${BFF_PID:-}" "bff"
  stop_pid "${ORCH_PID:-}" "orchestrator"

  rm -f "$PID_FILE"
else
  echo "[dev_down] no pid file found: $PID_FILE"
fi

# Best-effort cleanup for stale processes left by previous failed startups.
stop_stale_known_processes

echo "[dev_down] done"
