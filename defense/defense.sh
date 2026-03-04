#!/usr/bin/env bash
set -euo pipefail

DEFENDER_CONFIG="${1:-telesafety_defense/configs/dro.yaml}"
FILTER_CONFIG="${2:-telesafety_defense/configs/filter.yaml}"

python3 telesafety_defense/run_defense.py \
  --defender_config "${DEFENDER_CONFIG}" \
  --filter_config "${FILTER_CONFIG}"
