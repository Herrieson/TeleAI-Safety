#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

DEFENDER_CONFIG="${1:-telesafety_defense/configs/dro.yaml}"
FILTER_CONFIG="${2:-telesafety_defense/configs/filter.yaml}"

python3 -m telesafety_defense.run_defense \
  --defender_config "${DEFENDER_CONFIG}" \
  --filter_config "${FILTER_CONFIG}"
