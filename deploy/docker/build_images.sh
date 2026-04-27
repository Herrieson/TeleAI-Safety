#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <registry-prefix> [tag]" >&2
  echo "example: $0 registry.example.com/team latest" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REGISTRY_PREFIX="$1"
TAG="${2:-latest}"
PUSH="${PUSH:-0}"

PY_IMAGE="$REGISTRY_PREFIX/teleai-python-services:$TAG"
WEB_IMAGE="$REGISTRY_PREFIX/teleai-web:$TAG"

echo "[build] python services image: $PY_IMAGE"
docker build -f "$ROOT_DIR/deploy/docker/Dockerfile.python-services" -t "$PY_IMAGE" "$ROOT_DIR"

echo "[build] web image: $WEB_IMAGE"
docker build -f "$ROOT_DIR/deploy/docker/Dockerfile.web" -t "$WEB_IMAGE" "$ROOT_DIR"

if [[ "$PUSH" == "1" ]]; then
  echo "[push] $PY_IMAGE"
  docker push "$PY_IMAGE"
  echo "[push] $WEB_IMAGE"
  docker push "$WEB_IMAGE"
fi

echo
echo "Done."
echo "PYTHON_SERVICES_IMAGE=$PY_IMAGE"
echo "WEB_IMAGE=$WEB_IMAGE"
