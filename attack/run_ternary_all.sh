#!/usr/bin/env bash
set -u
set -o pipefail

ROOT="/home/hyx/workplace/TeleAI-Safety/attack"
CFG_DIR="${1:-$ROOT/configs/ternary}"
LOG_DIR="$ROOT/logs/ternary_runs"
TIME_DIR="$ROOT/results/ternary"
TIME_FILE="$TIME_DIR/timings.txt"
MAX_JOBS="${MAX_JOBS:-4}"

mkdir -p "$LOG_DIR"
mkdir -p "$TIME_DIR"

run_one() {
  local cfg="$1"
  local name
  name="$(basename "$cfg" .yaml)"
  local method="$ROOT/methods/${name}.py"

  if [[ ! -f "$method" ]]; then
    echo "[SKIP] No method for $cfg (missing $method)" | tee -a "$LOG_DIR/_missing.log"
    return 0
  fi

  local log="$LOG_DIR/${name}.log"
  local model_name
  model_name="$(rg -n "^target_model_name:" "$cfg" | head -n 1 | sed -E 's/.*target_model_name:[[:space:]]*//')"
  model_name="${model_name:-unknown_model}"
  local start_ts
  start_ts="$(date +%s)"
  echo "[START] $name" | tee -a "$log"
  uv run python "$method" --config_path="$cfg" >>"$log" 2>&1
  local rc=$?
  local end_ts
  local elapsed
  end_ts="$(date +%s)"
  elapsed=$((end_ts - start_ts))
  printf "%s %s %s\n" "$name" "$model_name" "$elapsed" >>"$TIME_FILE"
  if [[ $rc -ne 0 ]]; then
    echo "[FAIL] $name (exit=$rc)" | tee -a "$LOG_DIR/_failed.log" >>"$log"
    return 0
  fi
  echo "[DONE] $name" | tee -a "$log"
  return 0
}

export -f run_one
export ROOT CFG_DIR LOG_DIR

find "$CFG_DIR" -type f -name "*.yaml" -print0 \
  | xargs -0 -n 1 -P "$MAX_JOBS" bash -lc 'run_one "$1"' _

echo "All jobs dispatched. Logs in: $LOG_DIR"
echo "Configs dir: $CFG_DIR"
