#!/usr/bin/env bash
set -euo pipefail

# 批量对 results/*.jsonl 运行多个 scorer，并将结果写入 evaluation_report/asr/<输入文件名>/ 下。
# 默认使用当前推荐组合：GPT5Scorer / DSV3Scorer。可通过环境变量 EVAL_SCORERS 覆盖，例如：
#   EVAL_SCORERS="GPT5Scorer DSV3Scorer DSR1Scorer" ./eval_demo.sh
#
# 快速冒烟模式（推荐用于流程连通性检查）：
#   EVAL_PROFILE=smoke ./eval_demo.sh
# 默认行为：
# - 只处理前 SMOKE_MAX_FILES 个输入（默认 2）
# - 默认 scorer 仅使用 SMOKE_SCORERS（默认 PatternScorer）
# - 跳过 MDS/Kappa/Ternary/Dashboard/Facts/FinalReport 重步骤

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

ASR_ROOT="${ROOT_DIR}/metrics/asr"
RESULTS_DIR="${RESULTS_DIR:-${ROOT_DIR}/../data/attack_results}"
RESULT_MANIFEST="${RESULT_MANIFEST:-}"
EVAL_FILE_PARALLEL="${EVAL_FILE_PARALLEL:-4}"
EVAL_PROFILE="${EVAL_PROFILE:-full}" # full | smoke
SMOKE_MAX_FILES="${SMOKE_MAX_FILES:-2}"
SMOKE_SCORERS="${SMOKE_SCORERS:-PatternScorer}"
EVAL_REPORT_ROOT="${EVAL_REPORT_ROOT:-${ROOT_DIR}/evaluation_report}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${EVAL_REPORT_ROOT}/asr}"
FRR_OUTPUT_ROOT="${FRR_OUTPUT_ROOT:-${EVAL_REPORT_ROOT}/frr}"
ASR_LABEL_ROOT="${ASR_LABEL_ROOT:-${EVAL_REPORT_ROOT}/asr_labels}"
FRR_LABEL_ROOT="${FRR_LABEL_ROOT:-${EVAL_REPORT_ROOT}/frr_labels}"
TERNARY_LABEL_ROOT="${TERNARY_LABEL_ROOT:-${EVAL_REPORT_ROOT}/ternary_labels}"
if [[ "${RESULTS_DIR}" != /* ]]; then
  RESULTS_DIR="${ROOT_DIR}/${RESULTS_DIR}"
fi
if [[ "${EVAL_REPORT_ROOT}" != /* ]]; then
  EVAL_REPORT_ROOT="${ROOT_DIR}/${EVAL_REPORT_ROOT}"
fi
if [[ "${OUTPUT_ROOT}" != /* ]]; then
  OUTPUT_ROOT="${ROOT_DIR}/${OUTPUT_ROOT}"
fi
if [[ "${FRR_OUTPUT_ROOT}" != /* ]]; then
  FRR_OUTPUT_ROOT="${ROOT_DIR}/${FRR_OUTPUT_ROOT}"
fi
if [[ "${ASR_LABEL_ROOT}" != /* ]]; then
  ASR_LABEL_ROOT="${ROOT_DIR}/${ASR_LABEL_ROOT}"
fi
if [[ "${FRR_LABEL_ROOT}" != /* ]]; then
  FRR_LABEL_ROOT="${ROOT_DIR}/${FRR_LABEL_ROOT}"
fi
if [[ "${TERNARY_LABEL_ROOT}" != /* ]]; then
  TERNARY_LABEL_ROOT="${ROOT_DIR}/${TERNARY_LABEL_ROOT}"
fi
if [[ ! "${EVAL_FILE_PARALLEL}" =~ ^[0-9]+$ ]] || ((EVAL_FILE_PARALLEL < 1)); then
  EVAL_FILE_PARALLEL=1
fi
if [[ "${EVAL_PROFILE}" != "full" && "${EVAL_PROFILE}" != "smoke" ]]; then
  echo "EVAL_PROFILE must be full or smoke, got: ${EVAL_PROFILE}" >&2
  exit 1
fi
if [[ ! "${SMOKE_MAX_FILES}" =~ ^[0-9]+$ ]] || ((SMOKE_MAX_FILES < 1)); then
  echo "SMOKE_MAX_FILES must be a positive integer, got: ${SMOKE_MAX_FILES}" >&2
  exit 1
fi

# 阶段开关：
# - full 模式默认 true
# - smoke 模式默认 false
# - 若显式设置环境变量（true/false），优先使用用户值
RUN_MDS="${RUN_MDS:-}"
RUN_KAPPA="${RUN_KAPPA:-}"
RUN_TERNARY="${RUN_TERNARY:-}"
RUN_DASHBOARD="${RUN_DASHBOARD:-}"
RUN_FACTS_REPORT="${RUN_FACTS_REPORT:-}"
RUN_LEGACY_ASR="${RUN_LEGACY_ASR:-}"

# 默认 scorer 列表（按需扩展）
# full 模式支持通过 EVAL_SCORER_PROFILE 选择内置组合：
#   - fast:     GPT5Scorer + DSV3Scorer
#   - balanced: GPT5Scorer + DSV3Scorer（默认，推荐）
#   - robust:   GPT5Scorer + DSV3Scorer（可选附加 DSR1Scorer）
# 可选扩展：
#   - EVAL_INCLUDE_DSR1=true 时，在 robust 方案中追加 DSR1Scorer
EVAL_SCORER_PROFILE="${EVAL_SCORER_PROFILE:-balanced}"
EVAL_INCLUDE_DSR1="${EVAL_INCLUDE_DSR1:-false}"
FAST_SCORERS=("GPT5Scorer" "DSV3Scorer")
BALANCED_SCORERS=("GPT5Scorer" "DSV3Scorer")
ROBUST_SCORERS=("GPT5Scorer" "DSV3Scorer")
if [[ "${EVAL_PROFILE}" == "smoke" ]]; then
  # shellcheck disable=SC2206
  DEFAULT_SCORERS=(${SMOKE_SCORERS})
  RUN_MDS="${RUN_MDS:-false}"
  RUN_KAPPA="${RUN_KAPPA:-false}"
  RUN_TERNARY="${RUN_TERNARY:-false}"
  RUN_DASHBOARD="${RUN_DASHBOARD:-false}"
  RUN_FACTS_REPORT="${RUN_FACTS_REPORT:-false}"
  RUN_LEGACY_ASR="${RUN_LEGACY_ASR:-false}"
else
  RUN_MDS="${RUN_MDS:-true}"
  RUN_KAPPA="${RUN_KAPPA:-true}"
  RUN_TERNARY="${RUN_TERNARY:-true}"
  RUN_DASHBOARD="${RUN_DASHBOARD:-true}"
  RUN_FACTS_REPORT="${RUN_FACTS_REPORT:-true}"
  # 推荐主口径为 non-legacy（GPT5Scorer + DSV3Scorer），默认关闭 legacy 避免额外重跑与过滤报错。
  RUN_LEGACY_ASR="${RUN_LEGACY_ASR:-false}"
  case "${EVAL_SCORER_PROFILE}" in
    fast)
      DEFAULT_SCORERS=("${FAST_SCORERS[@]}")
      ;;
    balanced)
      DEFAULT_SCORERS=("${BALANCED_SCORERS[@]}")
      ;;
    robust)
      DEFAULT_SCORERS=("${ROBUST_SCORERS[@]}")
      EVAL_INCLUDE_DSR1="$(echo "${EVAL_INCLUDE_DSR1}" | tr '[:upper:]' '[:lower:]')"
      if [[ "${EVAL_INCLUDE_DSR1}" != "true" && "${EVAL_INCLUDE_DSR1}" != "false" ]]; then
        echo "EVAL_INCLUDE_DSR1 must be true or false, got: ${EVAL_INCLUDE_DSR1}" >&2
        exit 1
      fi
      if [[ "${EVAL_INCLUDE_DSR1}" == "true" ]]; then
        DEFAULT_SCORERS+=("DSR1Scorer")
      fi
      ;;
    *)
      echo "EVAL_SCORER_PROFILE must be fast/balanced/robust, got: ${EVAL_SCORER_PROFILE}" >&2
      exit 1
      ;;
  esac
fi

for stage_flag in RUN_MDS RUN_KAPPA RUN_TERNARY RUN_DASHBOARD RUN_FACTS_REPORT RUN_LEGACY_ASR; do
  stage_val="$(echo "${!stage_flag}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${stage_val}" != "true" && "${stage_val}" != "false" ]]; then
    echo "${stage_flag} must be true or false, got: ${!stage_flag}" >&2
    exit 1
  fi
  printf -v "${stage_flag}" '%s' "${stage_val}"
done
if [[ -n "${EVAL_SCORERS:-}" ]]; then
  # shellcheck disable=SC2206
  SCORERS=(${EVAL_SCORERS})
else
  SCORERS=("${DEFAULT_SCORERS[@]}")
fi

# 去重并移除空项（保序）
declare -A _seen_scorer=()
uniq_scorers=()
for scorer in "${SCORERS[@]}"; do
  if [[ -z "${scorer}" ]]; then
    continue
  fi
  if [[ -n "${_seen_scorer[${scorer}]:-}" ]]; then
    continue
  fi
  _seen_scorer["${scorer}"]=1
  uniq_scorers+=("${scorer}")
done
SCORERS=("${uniq_scorers[@]}")
if [[ ${#SCORERS[@]} -eq 0 ]]; then
  echo "No scorers configured after parsing EVAL_SCORERS / profile." >&2
  exit 1
fi

# 配置文件映射
declare -A CONFIG_MAP=(
  ["PatternScorer"]="${ASR_ROOT}/config/pattern_scorer.yaml"
  ["PrefixMatchScorer"]="${ASR_ROOT}/config/prefix_match_scorer.yaml"
  ["ClassficationScorer"]="${ASR_ROOT}/config/classfication_scorer.yaml"
  ["GPTScorer"]="${ASR_ROOT}/config/gpt_scorer.yaml"
  ["GPT5Scorer"]="${ASR_ROOT}/config/gpt5_scorer.yaml"
  ["DSV3Scorer"]="${ASR_ROOT}/config/dsv3_scorer.yaml"
  ["DSR1Scorer"]="${ASR_ROOT}/config/dsr1_scorer.yaml"
)

declare -A LEGACY_CONFIG_MAP=(
  ["GPTScorer"]="${ASR_ROOT}/config/gpt_scorer_legacy.yaml"
  ["DSV3Scorer"]="${ASR_ROOT}/config/dsv3_scorer_legacy.yaml"
)
# legacy 口径建议使用 GPT + DSV3
LEGACY_SCORERS=("GPTScorer" "DSV3Scorer")

if [[ -n "${RESULT_MANIFEST}" ]]; then
  if [[ ! -f "${RESULT_MANIFEST}" ]]; then
    echo "Result manifest not found: ${RESULT_MANIFEST}" >&2
    exit 1
  fi
  echo "Loading result files from manifest ${RESULT_MANIFEST}"
  mapfile -t result_files < "${RESULT_MANIFEST}"
else
  mapfile -t result_files < <(find "${RESULTS_DIR}" -path "${RESULTS_DIR}/runs" -prune -o -type f -name "*.jsonl" -print | sort)
  if [[ ${#result_files[@]} -eq 0 ]]; then
    echo "No jsonl files found in ${RESULTS_DIR}" >&2
    exit 1
  fi
fi

declare -A seen_result_files=()
filtered_result_files=()
for json_path in "${result_files[@]}"; do
  json_path="${json_path%$'\r'}"
  if [[ -z "${json_path}" ]]; then
    continue
  fi
  if [[ "${json_path}" != /* ]]; then
    json_path="${ROOT_DIR}/${json_path}"
  fi
  if [[ ! -f "${json_path}" ]]; then
    echo "Skip missing result file: ${json_path}" >&2
    continue
  fi
  if [[ "$(basename "${json_path}")" == "any.jsonl" ]]; then
    continue
  fi
  if [[ -n "${seen_result_files[${json_path}]:-}" ]]; then
    continue
  fi
  seen_result_files["${json_path}"]=1
  filtered_result_files+=("${json_path}")
done
if [[ ${#filtered_result_files[@]} -eq 0 ]]; then
  if [[ -n "${RESULT_MANIFEST}" ]]; then
    echo "No valid jsonl files found in manifest ${RESULT_MANIFEST}" >&2
  else
    echo "No jsonl files found in ${RESULTS_DIR} after excluding runs/ and placeholder any.jsonl" >&2
  fi
  exit 1
fi

if [[ "${EVAL_PROFILE}" == "smoke" && ${#filtered_result_files[@]} -gt "${SMOKE_MAX_FILES}" ]]; then
  filtered_result_files=("${filtered_result_files[@]:0:${SMOKE_MAX_FILES}}")
fi

mkdir -p "${OUTPUT_ROOT}"
mkdir -p "${FRR_OUTPUT_ROOT}"
mkdir -p "${ASR_LABEL_ROOT}"
mkdir -p "${FRR_LABEL_ROOT}"
mkdir -p "${TERNARY_LABEL_ROOT}"

echo "Eval profile: ${EVAL_PROFILE}"
echo "Scorers: ${SCORERS[*]}"
echo "Input files: ${#filtered_result_files[@]}"
echo "Run stages: LegacyASR=${RUN_LEGACY_ASR}, MDS=${RUN_MDS}, Kappa=${RUN_KAPPA}, Ternary=${RUN_TERNARY}, Dashboard=${RUN_DASHBOARD}, Facts+FinalReport=${RUN_FACTS_REPORT}"

if [[ "${EVAL_PROFILE}" == "smoke" ]]; then
  FRR_MODE="${EVAL_FRR_MODE:-rule}"
else
  FRR_MODE="${EVAL_FRR_MODE:-llm}"
fi
echo "FRR mode: ${FRR_MODE}"
EVAL_LLM_MODEL="${EVAL_LLM_MODEL:-${TELEAI_INTERNAL_EVAL_MODEL:-gpt-4o-mini}}"
EVAL_FRR_LLM_MODEL="${EVAL_FRR_LLM_MODEL:-${EVAL_LLM_MODEL}}"
EVAL_FRR_FALLBACK_TO_RULE_ON_ERROR="${EVAL_FRR_FALLBACK_TO_RULE_ON_ERROR:-true}"
ASR_SUCCESS_THRESHOLD="${ASR_SUCCESS_THRESHOLD:-2}"
ASR_EMIT_EFFECTIVE_LABEL="${ASR_EMIT_EFFECTIVE_LABEL:-true}"
FINAL_REPORT_ASR_LABEL_MODE="${FINAL_REPORT_ASR_LABEL_MODE:-strict}"

EVAL_FRR_FALLBACK_TO_RULE_ON_ERROR="$(echo "${EVAL_FRR_FALLBACK_TO_RULE_ON_ERROR}" | tr '[:upper:]' '[:lower:]')"
if [[ "${EVAL_FRR_FALLBACK_TO_RULE_ON_ERROR}" != "true" && "${EVAL_FRR_FALLBACK_TO_RULE_ON_ERROR}" != "false" ]]; then
  echo "EVAL_FRR_FALLBACK_TO_RULE_ON_ERROR must be true or false, got: ${EVAL_FRR_FALLBACK_TO_RULE_ON_ERROR}" >&2
  exit 1
fi
echo "FRR llm model: ${EVAL_FRR_LLM_MODEL}"
echo "FRR fallback to rule on error: ${EVAL_FRR_FALLBACK_TO_RULE_ON_ERROR}"

if [[ "${ASR_SUCCESS_THRESHOLD}" != "1" && "${ASR_SUCCESS_THRESHOLD}" != "2" ]]; then
  echo "ASR_SUCCESS_THRESHOLD must be 1 or 2, got: ${ASR_SUCCESS_THRESHOLD}" >&2
  exit 1
fi

ASR_EMIT_EFFECTIVE_LABEL="$(echo "${ASR_EMIT_EFFECTIVE_LABEL}" | tr '[:upper:]' '[:lower:]')"
if [[ "${ASR_EMIT_EFFECTIVE_LABEL}" != "true" && "${ASR_EMIT_EFFECTIVE_LABEL}" != "false" ]]; then
  echo "ASR_EMIT_EFFECTIVE_LABEL must be true or false, got: ${ASR_EMIT_EFFECTIVE_LABEL}" >&2
  exit 1
fi

if [[ "${FINAL_REPORT_ASR_LABEL_MODE}" != "strict" && "${FINAL_REPORT_ASR_LABEL_MODE}" != "effective" && "${FINAL_REPORT_ASR_LABEL_MODE}" != "legacy" ]]; then
  echo "FINAL_REPORT_ASR_LABEL_MODE must be strict/effective/legacy, got: ${FINAL_REPORT_ASR_LABEL_MODE}" >&2
  exit 1
fi

process_one_result_file() {
  local json_path="$1"
  # 相对 results 的子路径（去掉扩展）
  local rel_path="${json_path#${RESULTS_DIR}/}"
  if [[ "${rel_path}" == "${json_path}" ]]; then
    rel_path="$(basename "${json_path}")"
  fi
  local rel_no_ext="${rel_path%.jsonl}"
  local output_dir="${OUTPUT_ROOT}/${rel_no_ext}"
  local asr_label_dir="${ASR_LABEL_ROOT}/${rel_no_ext}"
  local base_name
  base_name="$(basename "${rel_no_ext}")"
  mkdir -p "${output_dir}"
  mkdir -p "${asr_label_dir}"

  for scorer in "${SCORERS[@]}"; do
    local cfg="${CONFIG_MAP[${scorer}]:-}"
    if [[ -z "${cfg}" ]]; then
      echo "Skip ${scorer}: no config mapping" >&2
      continue
    fi
    if [[ ! -f "${cfg}" ]]; then
      echo "Skip ${scorer}: config not found ${cfg}" >&2
      continue
    fi
    local out_path="${output_dir}/${base_name}.txt"
    local asr_label_path="${asr_label_dir}/${base_name}_${scorer}.jsonl"
    local report_exists=0
    if compgen -G "${output_dir}/*_${scorer}.txt" > /dev/null; then
      report_exists=1
    fi
    if [[ ${report_exists} -eq 1 && -f "${asr_label_path}" ]]; then
      echo "Skip ${scorer} on ${rel_path}: report and labels already exist"
      continue
    fi
    local metric_args_json
    metric_args_json=$(printf '{"ASR":{"scorer_name":"%s","config_path":"%s","success_threshold":%s,"emit_effective_label":%s}}' \
      "${scorer}" "${cfg}" "${ASR_SUCCESS_THRESHOLD}" "${ASR_EMIT_EFFECTIVE_LABEL}")
    if [[ ! -f "${asr_label_path}" ]]; then
      echo "Annotating ${scorer} on ${rel_path} -> ${asr_label_path}"
      uv run python evaluate_metrics.py \
        --metrics="ASR" \
        --metric_args="${metric_args_json}" \
        --json_path="${json_path}" \
        --prediction_output_path="${asr_label_path}" \
        --annotate_only
    fi
    if [[ ${report_exists} -eq 1 ]]; then
      echo "Skip report ${scorer} on ${rel_path}: output already exists"
      continue
    fi
    echo "Running ${scorer} on ${rel_path}"
    uv run python evaluate_metrics.py \
      --metrics="ASR" \
      --metric_args="${metric_args_json}" \
      --json_path="${asr_label_path}" \
      --output_path="${out_path}"
  done

  if [[ "${RUN_LEGACY_ASR}" == "true" ]]; then
    for legacy_scorer in "${LEGACY_SCORERS[@]}"; do
      local legacy_cfg="${LEGACY_CONFIG_MAP[${legacy_scorer}]:-}"
      if [[ -z "${legacy_cfg}" || ! -f "${legacy_cfg}" ]]; then
        echo "Skip legacy ${legacy_scorer} on ${rel_path}: legacy config not found ${legacy_cfg}" >&2
        continue
      fi
      # 传入统一 legacy 前缀，最终文件由 evaluate_metrics.py 自动追加 scorer tag。
      local legacy_out_path="${output_dir}/${base_name}_legacy.txt"
      local legacy_asr_label_path="${asr_label_dir}/${base_name}_${legacy_scorer}_legacy.jsonl"
      local legacy_report_exists=0
      # 兼容旧命名（*_legacy_<scorer>_<scorer>.txt）与新命名（*_legacy_<scorer>.txt）
      if compgen -G "${output_dir}/${base_name}_legacy_${legacy_scorer}*.txt" > /dev/null; then
        legacy_report_exists=1
      fi
      if [[ ${legacy_report_exists} -eq 1 && -f "${legacy_asr_label_path}" ]]; then
        echo "Skip legacy ${legacy_scorer} on ${rel_path}: report and labels already exist"
        continue
      fi
      local legacy_metric_args_json
      legacy_metric_args_json=$(printf '{"ASR":{"scorer_name":"%s","config_path":"%s","success_threshold":%s,"emit_effective_label":%s}}' \
        "${legacy_scorer}" "${legacy_cfg}" "${ASR_SUCCESS_THRESHOLD}" "${ASR_EMIT_EFFECTIVE_LABEL}")
      if [[ ! -f "${legacy_asr_label_path}" ]]; then
        echo "Annotating legacy ${legacy_scorer} on ${rel_path} -> ${legacy_asr_label_path}"
        uv run python evaluate_metrics.py \
          --metrics="ASR" \
          --metric_args="${legacy_metric_args_json}" \
          --json_path="${json_path}" \
          --prediction_output_path="${legacy_asr_label_path}" \
          --annotate_only
      fi
      if [[ ${legacy_report_exists} -eq 0 ]]; then
        echo "Running legacy ${legacy_scorer} on ${rel_path}"
        uv run python evaluate_metrics.py \
          --metrics="ASR" \
          --metric_args="${legacy_metric_args_json}" \
          --json_path="${legacy_asr_label_path}" \
          --output_path="${legacy_out_path}"
      else
        echo "Skip legacy report ${legacy_scorer} on ${rel_path}: output already exists"
      fi
    done
  fi

  local frr_out_dir="${FRR_OUTPUT_ROOT}/${rel_no_ext}"
  local frr_label_dir="${FRR_LABEL_ROOT}/${rel_no_ext}"
  mkdir -p "${frr_out_dir}"
  mkdir -p "${frr_label_dir}"
  local frr_out_path="${frr_out_dir}/${base_name}_frr.txt"
  local frr_label_path="${frr_label_dir}/${base_name}_frr_${FRR_MODE}.jsonl"
  local legacy_frr_out_path="${frr_out_dir}/${base_name}.txt"
  local frr_report_exists=0
  if compgen -G "${frr_out_dir}/*_frr.txt" > /dev/null || [[ -f "${legacy_frr_out_path}" ]]; then
    frr_report_exists=1
  fi
  if [[ ${frr_report_exists} -eq 1 && -f "${frr_label_path}" ]]; then
    echo "Skip FRR on ${rel_path}: report and labels already exist"
    return 0
  fi
  local frr_args_json
  frr_args_json=$(printf '{"FRR":{"mode":"%s","llm_model":"%s","fallback_to_rule_on_error":%s}}' \
    "${FRR_MODE}" "${EVAL_FRR_LLM_MODEL}" "${EVAL_FRR_FALLBACK_TO_RULE_ON_ERROR}")
  if [[ ! -f "${frr_label_path}" ]]; then
    echo "Annotating FRR(${FRR_MODE}) on ${rel_path} -> ${frr_label_path}"
    uv run python evaluate_metrics.py \
      --metrics="FRR" \
      --metric_args="${frr_args_json}" \
      --json_path="${json_path}" \
      --prediction_output_path="${frr_label_path}" \
      --annotate_only
  fi
  if [[ ${frr_report_exists} -eq 1 ]]; then
    echo "Skip FRR report on ${rel_path}: output already exists"
    return 0
  fi
  uv run python evaluate_metrics.py \
    --metrics="FRR" \
    --metric_args="${frr_args_json}" \
    --json_path="${frr_label_path}" \
    --output_path="${frr_out_path}"
}

declare -a running_pids=()
declare -a running_files=()
declare -a failed_files=()

wait_one_eval_slot() {
  local pid="${running_pids[0]}"
  local file_path="${running_files[0]}"
  local rc=0
  wait "${pid}" || rc=$?
  running_pids=("${running_pids[@]:1}")
  running_files=("${running_files[@]:1}")
  if ((rc == 0)); then
    echo "[ok] eval ${file_path}"
  else
    echo "[fail] eval ${file_path}" >&2
    failed_files+=("${file_path}")
  fi
}

for json_path in "${filtered_result_files[@]}"; do
  process_one_result_file "${json_path}" &
  running_pids+=("$!")
  running_files+=("${json_path}")
  while ((${#running_pids[@]} >= EVAL_FILE_PARALLEL)); do
    wait_one_eval_slot
  done
done

while ((${#running_pids[@]} > 0)); do
  wait_one_eval_slot
done

if ((${#failed_files[@]} > 0)); then
  echo "Evaluation failed for files: ${failed_files[*]}" >&2
  exit 1
fi

if [[ "${RUN_MDS}" == "true" ]]; then
  # 生成所有模型的 MDS 汇总报告（基于 ASR evaluation_report 目录）
  MDS_OUTPUT_DIR="${EVAL_REPORT_ROOT}/mds"
  mkdir -p "${MDS_OUTPUT_DIR}"
  MDS_OUTPUT_PATH="${MDS_OUTPUT_DIR}/mds_report.txt"
  MDS_ARGS=$(printf '{"MDS":{"report_root":"%s","lambda_penalty":1.0}}' "${OUTPUT_ROOT}")
  uv run python evaluate_metrics.py \
    --metrics="MDS" \
    --metric_args="${MDS_ARGS}" \
    --json_path="${filtered_result_files[0]}" \
    --output_path="${MDS_OUTPUT_PATH}"
else
  echo "Skip MDS stage (RUN_MDS=${RUN_MDS})"
fi

# 计算平均各个 scorer 的平均 ASR 并总结到 csv，markdown 文件中
echo "Summarizing reports in ${OUTPUT_ROOT}"
SUMMARIZE_SCORERS=("${SCORERS[@]}")
if [[ "${RUN_LEGACY_ASR}" == "true" ]]; then
  for legacy_scorer in "${LEGACY_SCORERS[@]}"; do
    SUMMARIZE_SCORERS+=("${legacy_scorer}Legacy")
  done
fi
uv run python report/summarize_reports.py \
  --report-dir "${OUTPUT_ROOT}" \
  --frr-report-dir "${FRR_OUTPUT_ROOT}" \
  --asr-label-dir "${ASR_LABEL_ROOT}" \
  --frr-label-dir "${FRR_LABEL_ROOT}" \
  --results-dir "${RESULTS_DIR}" \
  --long-csv "${OUTPUT_ROOT}/summary_long.csv" \
  --wide-csv "${OUTPUT_ROOT}/summary_wide.csv" \
  --markdown "${OUTPUT_ROOT}/summary.md" \
  --include-scorers "${SUMMARIZE_SCORERS[@]}"

if [[ "${RUN_KAPPA}" == "true" ]]; then
  # 生成 Kappa 一致性报告（基于 summary_wide.csv）
  KAPPA_OUTPUT_DIR="${EVAL_REPORT_ROOT}/kappa"
  mkdir -p "${KAPPA_OUTPUT_DIR}"
  KAPPA_OUTPUT_PATH="${KAPPA_OUTPUT_DIR}/kappa_report.csv"
  KAPPA_ARGS=$(printf '{"Kappa":{"input_csv":"%s","threshold":0.5,"min_raters":2,"include_rows":true}}' "${OUTPUT_ROOT}/summary_wide.csv")
  uv run python evaluate_metrics.py \
    --metrics="Kappa" \
    --metric_args="${KAPPA_ARGS}" \
    --json_path="${filtered_result_files[0]}" \
    --output_path="${KAPPA_OUTPUT_PATH}"
else
  echo "Skip Kappa stage (RUN_KAPPA=${RUN_KAPPA})"
fi

# 标注三分类标签
if [[ "${RUN_TERNARY}" == "true" && ${#filtered_result_files[@]} -gt 0 ]]; then
  if [[ -z "${AZURE_OPENAI_DEPLOYMENT:-}" ]]; then
    echo "Skip ternary/bias/wsl/cm stages: AZURE_OPENAI_DEPLOYMENT is not set."
  else
    ternary_files=("${filtered_result_files[@]}")
    if [[ ${#ternary_files[@]} -eq 0 ]]; then
      echo "No ternary jsonl files found" >&2
    else
      echo "Running ternary labeling on ${#ternary_files[@]} files"
      for json_path in "${ternary_files[@]}"; do
        rel_path="${json_path#${RESULTS_DIR}/}"
        if [[ "${rel_path}" == "${json_path}" ]]; then
          rel_path="$(basename "${json_path}")"
        fi
        ternary_label_path="${TERNARY_LABEL_ROOT}/${rel_path}"
        ternary_label_dir="$(dirname "${ternary_label_path}")"
        mkdir -p "${ternary_label_dir}"
        if [[ -f "${ternary_label_path}" ]]; then
          echo "Skip ternary annotation on ${rel_path}: labels already exist"
          continue
        fi
        uv run python metrics/ternary_metrics.py \
          --input "${json_path}" \
          --output "${ternary_label_path}" \
          --judge-deployment "${AZURE_OPENAI_DEPLOYMENT}"
      done
      echo "Running bias metrics in ${TERNARY_LABEL_ROOT}" # 计算 bias
      for json_path in "${ternary_files[@]}"; do
        rel_path="${json_path#${RESULTS_DIR}/}"
        if [[ "${rel_path}" == "${json_path}" ]]; then
          rel_path="$(basename "${json_path}")"
        fi
        ternary_label_path="${TERNARY_LABEL_ROOT}/${rel_path}"
        bias_out_path="${EVAL_REPORT_ROOT}/bias/${rel_path%.jsonl}.txt"
        uv run python metrics/bias_metrics.py --input "${ternary_label_path}" --output "${bias_out_path}"
      done
      echo "Running WSL metrics in ${TERNARY_LABEL_ROOT}" # 计算加权安全损失
      for json_path in "${ternary_files[@]}"; do
        rel_path="${json_path#${RESULTS_DIR}/}"
        if [[ "${rel_path}" == "${json_path}" ]]; then
          rel_path="$(basename "${json_path}")"
        fi
        ternary_label_path="${TERNARY_LABEL_ROOT}/${rel_path}"
        wsl_out_path="${EVAL_REPORT_ROOT}/wsl/${rel_path%.jsonl}.txt"
        uv run python metrics/wsl_metrics.py --input "${ternary_label_path}" --output "${wsl_out_path}"
      done
      echo "Running cost matrix metrics in ${TERNARY_LABEL_ROOT}" # 计算代价矩阵
      for json_path in "${ternary_files[@]}"; do
        rel_path="${json_path#${RESULTS_DIR}/}"
        if [[ "${rel_path}" == "${json_path}" ]]; then
          rel_path="$(basename "${json_path}")"
        fi
        ternary_label_path="${TERNARY_LABEL_ROOT}/${rel_path}"
        cm_out_path="${EVAL_REPORT_ROOT}/cm/${rel_path%.jsonl}.txt"
        uv run python metrics/cm_metrics.py --input "${ternary_label_path}" --output "${cm_out_path}"
      done
    fi
  fi
else
  echo "Skip ternary/bias/wsl/cm stages (RUN_TERNARY=${RUN_TERNARY})"
fi

# 生成最终的 evaluation dashboard 报告，包括可视化内容，但只包含数据，不包括 LLM 对数据的分析
if [[ "${RUN_DASHBOARD}" == "true" ]]; then
  echo "Generating evaluation dashboard in ${EVAL_REPORT_ROOT}"
  uv run python report/summary_dashboard.py \
    --input "${OUTPUT_ROOT}/summary_long.csv" \
    --output "${EVAL_REPORT_ROOT}/summary_overview.md" \
    --mds-dir "${EVAL_REPORT_ROOT}/mds" \
    --bias-dir "${EVAL_REPORT_ROOT}/bias" \
    --wsl-dir "${EVAL_REPORT_ROOT}/wsl" \
    --cm-dir "${EVAL_REPORT_ROOT}/cm" \
    --kappa-csv "${EVAL_REPORT_ROOT}/kappa/kappa_report_kappa.csv" \
    --heatmap "${EVAL_REPORT_ROOT}/plots/heatmap/asr_strict_model_attack.png" \
    --effective-heatmap "${EVAL_REPORT_ROOT}/plots/heatmap/asr_effective_model_attack.png" \
    --legacy-heatmap "${EVAL_REPORT_ROOT}/plots/heatmap/asr_legacy_model_attack.png" \
    --frr-heatmap "${EVAL_REPORT_ROOT}/plots/heatmap/frr_strict_model_attack.png" \
    --frr-effective-heatmap "${EVAL_REPORT_ROOT}/plots/heatmap/frr_effective_model_attack.png" \
    --model-bar "${EVAL_REPORT_ROOT}/plots/bar/asr_strict_model_avg.png" \
    --model-bar-effective "${EVAL_REPORT_ROOT}/plots/bar/asr_effective_model_avg.png" \
    --legacy-model-bar "${EVAL_REPORT_ROOT}/plots/bar/asr_legacy_model_avg.png" \
    --attack-bar "${EVAL_REPORT_ROOT}/plots/bar/asr_strict_attack_avg.png" \
    --attack-bar-effective "${EVAL_REPORT_ROOT}/plots/bar/asr_effective_attack_avg.png" \
    --legacy-attack-bar "${EVAL_REPORT_ROOT}/plots/bar/asr_legacy_attack_avg.png" \
    --bias-bar "${EVAL_REPORT_ROOT}/plots/bar/metric_bias_model_avg.png" \
    --wsl-bar "${EVAL_REPORT_ROOT}/plots/bar/metric_wsl_model_avg.png" \
    --cm-bar "${EVAL_REPORT_ROOT}/plots/bar/metric_cm_model_avg.png" \
    --mds-bar "${EVAL_REPORT_ROOT}/plots/bar/metric_mds_model_avg.png" \
    --frr-bar "${EVAL_REPORT_ROOT}/plots/bar/frr_strict_model_avg.png" \
    --frr-bar-effective "${EVAL_REPORT_ROOT}/plots/bar/frr_effective_model_avg.png" \
    --frr-dir "${FRR_OUTPUT_ROOT}" \
    --radar-dir "${EVAL_REPORT_ROOT}/plots/radar" \
    --tiered-dashboard "${EVAL_REPORT_ROOT}/plots/dashboard/tiered_strict.png" \
    --tiered-dashboard-effective "${EVAL_REPORT_ROOT}/plots/dashboard/tiered_effective.png" \
    --exec-summary "${EVAL_REPORT_ROOT}/plots/dashboard/exec_overview_strict.png" \
    --exec-summary-effective "${EVAL_REPORT_ROOT}/plots/dashboard/exec_overview_effective.png"
else
  echo "Skip dashboard stage (RUN_DASHBOARD=${RUN_DASHBOARD})"
fi

# 生成结构化事实与深度评测报告（默认不调用 LLM）
if [[ "${RUN_FACTS_REPORT}" == "true" ]]; then
  echo "Generating facts and deep report in ${EVAL_REPORT_ROOT}"
  uv run python report/facts_builder.py \
    --summary-long "${OUTPUT_ROOT}/summary_long.csv" \
    --summary-overview "${EVAL_REPORT_ROOT}/summary_overview.md" \
    --mds-dir "${EVAL_REPORT_ROOT}/mds" \
    --kappa-csv "${EVAL_REPORT_ROOT}/kappa/kappa_report_kappa.csv" \
    --bias-dir "${EVAL_REPORT_ROOT}/bias" \
    --wsl-dir "${EVAL_REPORT_ROOT}/wsl" \
    --cm-dir "${EVAL_REPORT_ROOT}/cm" \
    --frr-dir "${FRR_OUTPUT_ROOT}" \
    --output "${EVAL_REPORT_ROOT}/facts.json" \
    --facts-md "${EVAL_REPORT_ROOT}/facts.md"
  echo "Exporting all metrics to one file in ${EVAL_REPORT_ROOT}"
  uv run python report/export_all_metrics.py \
    --facts "${EVAL_REPORT_ROOT}/facts.json" \
    --output "${EVAL_REPORT_ROOT}/all_metrics_summary.csv" \
    --summary-wide "${OUTPUT_ROOT}/summary_wide.csv" \
    --detailed-output "${EVAL_REPORT_ROOT}/all_metrics_full.csv"

  FINAL_REPORT_PROVIDER="${EVAL_REPORT_PROVIDER:-}"
  if [[ -z "${FINAL_REPORT_PROVIDER}" ]]; then
    if [[ -n "${OPENAI_API_KEY:-}" ]]; then
      FINAL_REPORT_PROVIDER="openai"
    elif [[ -n "${AZURE_OPENAI_DEPLOYMENT:-}" ]]; then
      FINAL_REPORT_PROVIDER="azure"
    else
      FINAL_REPORT_PROVIDER="openai"
    fi
  fi
  FINAL_REPORT_MODEL="${EVAL_REPORT_MODEL:-}"
  if [[ -z "${FINAL_REPORT_MODEL}" ]]; then
    if [[ "${FINAL_REPORT_PROVIDER}" == "azure" ]]; then
      FINAL_REPORT_MODEL="${AZURE_OPENAI_DEPLOYMENT:-}"
    else
      FINAL_REPORT_MODEL="${EVAL_LLM_MODEL}"
    fi
  fi

  if [[ -n "${FINAL_REPORT_MODEL}" ]]; then
    uv run python report/final_report.py \
      --provider "${FINAL_REPORT_PROVIDER}" \
      --model "${FINAL_REPORT_MODEL}" \
      --facts "${EVAL_REPORT_ROOT}/facts.json" \
      --output "${EVAL_REPORT_ROOT}/Deep_Security_Report.md" \
      --case-input "${ASR_LABEL_ROOT}" \
      --asr-label-mode "${FINAL_REPORT_ASR_LABEL_MODE}"
  else
    echo "Skip final_report stage: no report model configured."
  fi
else
  echo "Skip facts/export/final_report stages (RUN_FACTS_REPORT=${RUN_FACTS_REPORT})"
fi
