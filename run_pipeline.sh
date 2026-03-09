#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATTACK_SCRIPT="${ROOT_DIR}/attack/run_attack_parallel.sh"
EVAL_SCRIPT="${ROOT_DIR}/evaluate/eval_demo.sh"

MODE="both"
RESUME=0
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
ATTACK_CONFIG_DIR="${ATTACK_CONFIG_DIR:-configs/gpt-5.4}"
RESULTS_ROOT="${RESULTS_ROOT:-${ROOT_DIR}/data/attack_results}"
MANIFEST_PATH="${MANIFEST_PATH:-}"
EVAL_FILE_PARALLEL="${EVAL_FILE_PARALLEL:-4}"

usage() {
  cat <<'EOF'
Usage: ./run_pipeline.sh [options]

Options:
  --attack-only            Only run attack stage.
  --eval-only              Only run evaluation stage.
  --resume                 For eval-only mode, auto-use latest manifest when manifest is not provided.
  --run-id <id>            Run id used in manifest file name.
  --config-dir <dir>       Attack config directory (default: configs/gpt-5.4, relative to attack/).
  --results-root <dir>     Unified results root (default: ./data/attack_results).
  --manifest <path>        Manifest path to read/write.
  -h, --help               Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --attack-only)
      MODE="attack"
      shift
      ;;
    --eval-only)
      MODE="eval"
      shift
      ;;
    --resume)
      RESUME=1
      shift
      ;;
    --run-id)
      RUN_ID="${2:-}"
      shift 2
      ;;
    --config-dir)
      ATTACK_CONFIG_DIR="${2:-}"
      shift 2
      ;;
    --results-root)
      RESULTS_ROOT="${2:-}"
      shift 2
      ;;
    --manifest)
      MANIFEST_PATH="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${RUN_ID}" ]]; then
  echo "--run-id cannot be empty" >&2
  exit 1
fi
if [[ -z "${ATTACK_CONFIG_DIR}" ]]; then
  echo "--config-dir cannot be empty" >&2
  exit 1
fi
if [[ -z "${RESULTS_ROOT}" ]]; then
  echo "--results-root cannot be empty" >&2
  exit 1
fi

if [[ "${RESULTS_ROOT}" != /* ]]; then
  RESULTS_ROOT="${ROOT_DIR}/${RESULTS_ROOT}"
fi
CONFIG_TAG="$(basename "${ATTACK_CONFIG_DIR}")"
if [[ -z "${MANIFEST_PATH}" ]]; then
  MANIFEST_PATH="${RESULTS_ROOT}/manifests/${CONFIG_TAG}_${RUN_ID}.txt"
fi
if [[ "${MANIFEST_PATH}" != /* ]]; then
  MANIFEST_PATH="${ROOT_DIR}/${MANIFEST_PATH}"
fi

if [[ "${MODE}" == "attack" || "${MODE}" == "both" ]]; then
  echo "[pipeline] attack stage: config=${ATTACK_CONFIG_DIR} results_root=${RESULTS_ROOT}"
  RUN_ID="${RUN_ID}" \
  CONFIG_DIR="${ATTACK_CONFIG_DIR}" \
  RESULTS_ROOT="${RESULTS_ROOT}" \
  MANIFEST_PATH="${MANIFEST_PATH}" \
  bash "${ATTACK_SCRIPT}"
fi

if [[ "${MODE}" == "eval" || "${MODE}" == "both" ]]; then
  result_manifest=""
  if [[ -f "${MANIFEST_PATH}" ]]; then
    result_manifest="${MANIFEST_PATH}"
  elif [[ "${RESUME}" == "1" ]]; then
    latest_manifest="$(find "${RESULTS_ROOT}/manifests" -maxdepth 1 -type f -name "${CONFIG_TAG}_*.txt" 2>/dev/null | sort | tail -n 1 || true)"
    if [[ -n "${latest_manifest}" ]]; then
      result_manifest="${latest_manifest}"
      echo "[pipeline] resume mode using latest manifest: ${result_manifest}"
    fi
  fi

  echo "[pipeline] eval stage: results_root=${RESULTS_ROOT}"
  if [[ -n "${result_manifest}" ]]; then
    echo "[pipeline] eval manifest=${result_manifest}"
    RESULTS_DIR="${RESULTS_ROOT}" \
    RESULT_MANIFEST="${result_manifest}" \
    EVAL_FILE_PARALLEL="${EVAL_FILE_PARALLEL}" \
    bash "${EVAL_SCRIPT}"
  else
    echo "[pipeline] manifest not found, evaluate all files under ${RESULTS_ROOT}"
    RESULTS_DIR="${RESULTS_ROOT}" \
    EVAL_FILE_PARALLEL="${EVAL_FILE_PARALLEL}" \
    bash "${EVAL_SCRIPT}"
  fi
fi

echo "[pipeline] done."
