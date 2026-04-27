#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  Option 1: provide full public URLs
    WEB_PUBLIC_ORIGIN=http://<host>:<web-nodeport> \
    BFF_PUBLIC_BASE_URL=http://<host>:<bff-nodeport> \
    bash scripts/dev_up_nodeport.sh

  Option 2: provide host + ports separately
    PUBLIC_HOST=<host> \
    WEB_PUBLIC_PORT=<web-nodeport> \
    BFF_PUBLIC_PORT=<bff-nodeport> \
    [PUBLIC_SCHEME=http] \
    bash scripts/dev_up_nodeport.sh

What this script does:
  - orchestrator binds to 0.0.0.0:9001
  - bff binds to 0.0.0.0:<BFF_PORT>
  - web binds to 0.0.0.0:<WEB_PORT>
  - frontend points to the externally reachable BFF URL
  - BFF CORS allows the externally reachable web origin

Optional overrides:
  ORCH_BIND_HOST   default: 0.0.0.0
  BFF_BIND_HOST    default: 0.0.0.0
  WEB_BIND_HOST    default: 0.0.0.0
  ORCH_PORT        default: 9001
  BFF_PORT         default: 9000
  WEB_PORT         default: 3000
EOF
}

SCHEME="${PUBLIC_SCHEME:-http}"
WEB_PUBLIC_ORIGIN="${WEB_PUBLIC_ORIGIN:-}"
BFF_PUBLIC_BASE_URL="${BFF_PUBLIC_BASE_URL:-}"
PUBLIC_HOST="${PUBLIC_HOST:-}"
WEB_PUBLIC_PORT="${WEB_PUBLIC_PORT:-}"
BFF_PUBLIC_PORT="${BFF_PUBLIC_PORT:-}"

if [[ -z "$WEB_PUBLIC_ORIGIN" ]]; then
  if [[ -n "$PUBLIC_HOST" && -n "$WEB_PUBLIC_PORT" ]]; then
    WEB_PUBLIC_ORIGIN="${SCHEME}://${PUBLIC_HOST}:${WEB_PUBLIC_PORT}"
  fi
fi

if [[ -z "$BFF_PUBLIC_BASE_URL" ]]; then
  if [[ -n "$PUBLIC_HOST" && -n "$BFF_PUBLIC_PORT" ]]; then
    BFF_PUBLIC_BASE_URL="${SCHEME}://${PUBLIC_HOST}:${BFF_PUBLIC_PORT}"
  fi
fi

if [[ -z "$WEB_PUBLIC_ORIGIN" || -z "$BFF_PUBLIC_BASE_URL" ]]; then
  usage >&2
  echo >&2
  echo "[dev_up_nodeport] missing public URL information." >&2
  exit 1
fi

export ORCH_BIND_HOST="${ORCH_BIND_HOST:-0.0.0.0}"
export BFF_BIND_HOST="${BFF_BIND_HOST:-0.0.0.0}"
export WEB_BIND_HOST="${WEB_BIND_HOST:-0.0.0.0}"
export BFF_CORS_ALLOW_ORIGINS="$WEB_PUBLIC_ORIGIN"
export NEXT_PUBLIC_BFF_BASE_URL="$BFF_PUBLIC_BASE_URL"

cat <<EOF
[dev_up_nodeport] starting TeleAI-Safety in NodePort/direct-access mode
[dev_up_nodeport] web public origin: $WEB_PUBLIC_ORIGIN
[dev_up_nodeport] bff public base:  $BFF_PUBLIC_BASE_URL
[dev_up_nodeport] orch bind host:   $ORCH_BIND_HOST
[dev_up_nodeport] bff bind host:    $BFF_BIND_HOST
[dev_up_nodeport] web bind host:    $WEB_BIND_HOST
EOF

exec bash "$ROOT_DIR/scripts/dev_up.sh"
