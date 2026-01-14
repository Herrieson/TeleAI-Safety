#!/usr/bin/env bash

# Batch runner for attacks -> evaluation -> summary.
# - Runs all configs under attack/configs concurrently.
# - Copies attack/results into evaluate/results, keeping the tree.
# - Runs evaluate/eval_demo.sh then summarize_reports.py.

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATTACK_DIR="${ROOT_DIR}/attack"
EVAL_DIR="${ROOT_DIR}/evaluate"
ATTACK_RESULTS="${ATTACK_DIR}/results"
EVAL_RESULTS="${EVAL_DIR}/results"

# Override with ATTACK_WORKERS=N to control concurrency.
MAX_PARALLEL=${ATTACK_WORKERS:-4}

# Preferred Python runner (defaults to uv run python -> python3 -> python).
if command -v uv >/dev/null 2>&1; then
  PYTHON_CMD=(uv run python)
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=(python3)
else
  PYTHON_CMD=(python)
fi

log() {
  printf '[%s] %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*"
}

run_attack_configs() {
  log "Starting attack runs with max ${MAX_PARALLEL} parallel jobs"
  cd "${ATTACK_DIR}"

  mapfile -t configs < <(find "./configs" -type f -name "*.yaml" | sort)
  if [[ ${#configs[@]} -eq 0 ]]; then
    log "No configs found under ${ATTACK_DIR}/configs"
    return 1
  fi

  declare -A PID_TO_CONFIG=()
  pids=()

  for cfg in "${configs[@]}"; do
    rel_cfg="${cfg#./}"
    method_name="$(basename "${cfg}" .yaml)"
    method_path="${ATTACK_DIR}/methods/${method_name}.py"
    if [[ ! -f "${method_path}" ]]; then
      log "Skip ${rel_cfg}: missing method script ${method_path}"
      continue
    fi

    # Throttle parallelism
    while (( $(jobs -r -p | wc -l) >= MAX_PARALLEL )); do
      sleep 0.5
    done

    (
      log "Run ${method_name} with ${rel_cfg}"
      if ! "${PYTHON_CMD[@]}" "${method_path}" --config_path "./${rel_cfg}"; then
        log "ERROR running ${method_name} (${rel_cfg})"
        exit 1
      fi
    ) &

    pid=$!
    PID_TO_CONFIG[$pid]="${rel_cfg}"
    pids+=("${pid}")
  done

  failed=()
  for pid in "${pids[@]}"; do
    if ! wait "${pid}"; then
      failed+=("${PID_TO_CONFIG[$pid]}")
    fi
  done

  if (( ${#failed[@]} > 0 )); then
    log "Attack runs finished with failures: ${failed[*]}"
    return 1
  fi

  log "All attack runs finished successfully"
  return 0
}

sync_results() {
  log "Sync attack results to evaluate/results"
  mkdir -p "${EVAL_RESULTS}"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a "${ATTACK_RESULTS}/" "${EVAL_RESULTS}/"
  else
    cp -R "${ATTACK_RESULTS}/." "${EVAL_RESULTS}/"
  fi
}

run_evaluation() {
  if [[ ! -f "${EVAL_DIR}/eval_demo.sh" ]]; then
    log "eval_demo.sh not found in ${EVAL_DIR}, skip"
    return 1
  fi

  log "Running evaluation demo"
  (cd "${EVAL_DIR}" && bash ./eval_demo.sh)
}

summarize_reports() {
  log "Summarizing reports"
  if command -v uv >/dev/null 2>&1; then
    (cd "${EVAL_DIR}" && uv run python summarize_reports.py)
  else
    (cd "${EVAL_DIR}" && python summarize_reports.py)
  fi
}

main() {
  run_attack_configs || log "Some attack jobs failed; continuing"
  cd "${ROOT_DIR}"

  sync_results || log "Result sync encountered issues"

  run_evaluation || log "Evaluation step failed"

  summarize_reports || log "Report summary failed"
}

main "$@"
