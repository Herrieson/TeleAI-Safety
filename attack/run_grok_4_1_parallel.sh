#!/usr/bin/env bash
set -euo pipefail

# 在 TeleAI-Safety/attack 根目录执行
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

CONFIG_DIR="configs/grok-4.1"
PARALLEL_SCRIPT="parallel_attack.py"

# 可通过环境变量覆盖
SHARDS="${SHARDS:-4}"
MAX_WORKERS="${MAX_WORKERS:-4}"
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-15}"
SAVE_INTERVAL="${SAVE_INTERVAL:-60}"
METHOD_PARALLEL="${METHOD_PARALLEL:-2}"
RESULT_MIN_LINES="${RESULT_MIN_LINES:-500}"
failed_methods=()
declare -a running_pids=()
declare -a running_methods=()

if command -v uv >/dev/null 2>&1; then
  PY_CMD=(uv run python)
elif command -v python3 >/dev/null 2>&1; then
  PY_CMD=(python3)
elif command -v python >/dev/null 2>&1; then
  PY_CMD=(python)
else
  echo "[error] no python runtime found (expected uv/python3/python)." >&2
  exit 1
fi

get_res_save_path() {
  local cfg_path="$1"
  CFG_PATH="$cfg_path" ROOT_DIR="$ROOT_DIR" "${PY_CMD[@]}" - <<'PY'
import os
import yaml
from pathlib import Path

cfg_path = Path(os.environ["CFG_PATH"])
root = Path(os.environ["ROOT_DIR"])
with cfg_path.open("r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}
res = data.get("res_save_path")
if not res:
    print("")
else:
    res = os.path.expandvars(str(res))
    p = Path(res)
    if not p.is_absolute():
        p = root / p
    print(str(p))
PY
}

count_result_records() {
  local res_path="$1"
  RES_PATH="$res_path" "${PY_CMD[@]}" - <<'PY'
import json
import os
from pathlib import Path

p = Path(os.environ["RES_PATH"])
if not p.exists():
    print(0)
    raise SystemExit(0)

if p.suffix == ".jsonl":
    cnt = 0
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                cnt += 1
    print(cnt)
    raise SystemExit(0)

if p.suffix == ".json":
    try:
        with p.open("r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, list):
            print(len(obj))
        elif isinstance(obj, dict):
            print(1)
        else:
            print(0)
    except Exception:
        print(0)
    raise SystemExit(0)

print(0)
PY
}

wait_one_slot() {
  local pid="${running_pids[0]}"
  local method="${running_methods[0]}"
  local rc=0
  if ! wait "$pid"; then
    rc=$?
  fi

  running_pids=("${running_pids[@]:1}")
  running_methods=("${running_methods[@]:1}")

  if ((rc == 0)); then
    echo "[ok] $method"
  else
    echo "[fail] $method" >&2
    failed_methods+=("$method")
  fi
}

for cfg in "$CONFIG_DIR"/*.yaml; do
  method_name="$(basename "$cfg" .yaml)"
  method_path="methods/${method_name}.py"

  if [[ ! -f "$method_path" ]]; then
    echo "[skip] method not found: $method_path (config: $cfg)"
    continue
  fi

  res_path="$(get_res_save_path "$cfg")"
  if [[ -n "$res_path" ]]; then
    existing_count="$(count_result_records "$res_path")"
    if ((existing_count >= RESULT_MIN_LINES)); then
      echo "[skip] method=$method_name result already has ${existing_count} records (>=${RESULT_MIN_LINES}): $res_path"
      continue
    fi
  fi

  echo "[run] method=$method_name config=$cfg shards=$SHARDS workers=$MAX_WORKERS save_interval=$SAVE_INTERVAL"
  "${PY_CMD[@]}" "$PARALLEL_SCRIPT" \
    --method "$method_path" \
    --config "$cfg" \
    --shards "$SHARDS" \
    --max-workers "$MAX_WORKERS" \
    --progress-interval "$PROGRESS_INTERVAL" \
    --save-interval "$SAVE_INTERVAL" &

  running_pids+=("$!")
  running_methods+=("$method_name")

  while ((${#running_pids[@]} >= METHOD_PARALLEL)); do
    wait_one_slot
  done
done

while ((${#running_pids[@]} > 0)); do
  wait_one_slot
done

if ((${#failed_methods[@]} > 0)); then
  echo "[done] finished with failures: ${failed_methods[*]}" >&2
  exit 1
fi

echo "[done] all configs in $CONFIG_DIR finished successfully."
