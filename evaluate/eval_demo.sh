#!/usr/bin/env bash
set -euo pipefail

# 批量对 results/*.jsonl 运行多个 scorer，并将结果写入 evaluation_report/asr/<输入文件名>/ 下。
# 默认只跑轻量方法（Pattern / Prefix）。如需更多 scorer，可通过环境变量 EVAL_SCORERS 覆盖，例如：
#   EVAL_SCORERS="PatternScorer PrefixMatchScorer ClassficationScorer" ./eval_demo.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

ASR_ROOT="${ROOT_DIR}/metrics/asr"
RESULTS_DIR="${ROOT_DIR}/../data/attack_results"
OUTPUT_ROOT="${ROOT_DIR}/evaluation_report/asr"
FRR_OUTPUT_ROOT="${ROOT_DIR}/evaluation_report/frr"

# 默认 scorer 列表（按需扩展）
DEFAULT_SCORERS=("PatternScorer" "PrefixMatchScorer" "ClassficationScorer" "GPTScorer" "GPT5Scorer" "DSV3Scorer" "DSR1Scorer" "MultiAPIScorer")
if [[ -n "${EVAL_SCORERS:-}" ]]; then
  # shellcheck disable=SC2206
  SCORERS=(${EVAL_SCORERS})
else
  SCORERS=("${DEFAULT_SCORERS[@]}")
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
  ["MultiAPIScorer"]="${ASR_ROOT}/config/multi_api_scorer.yaml"
)

mapfile -t result_files < <(find "${RESULTS_DIR}" -type f -name "*.jsonl" | sort)
if [[ ${#result_files[@]} -eq 0 ]]; then
  echo "No jsonl files found in ${RESULTS_DIR}" >&2
  exit 1
fi

filtered_result_files=()
for json_path in "${result_files[@]}"; do
  if [[ "$(basename "${json_path}")" == "any.jsonl" ]]; then
    continue
  fi
  filtered_result_files+=("${json_path}")
done
if [[ ${#filtered_result_files[@]} -eq 0 ]]; then
  echo "No jsonl files found in ${RESULTS_DIR} after excluding placeholder any.jsonl" >&2
  exit 1
fi

mkdir -p "${OUTPUT_ROOT}"
mkdir -p "${FRR_OUTPUT_ROOT}"

FRR_MODE="${EVAL_FRR_MODE:-llm}"

for json_path in "${filtered_result_files[@]}"; do
  # 相对 results 的子路径（去掉扩展）
  rel_path="${json_path#${RESULTS_DIR}/}"
  rel_no_ext="${rel_path%.jsonl}"
  output_dir="${OUTPUT_ROOT}/${rel_no_ext}"
  base_name="$(basename "${rel_no_ext}")"
  mkdir -p "${output_dir}"

  for scorer in "${SCORERS[@]}"; do
    cfg="${CONFIG_MAP[${scorer}]:-}"
    if [[ -z "${cfg}" ]]; then
      echo "Skip ${scorer}: no config mapping" >&2
      continue
    fi
    if [[ ! -f "${cfg}" ]]; then
      echo "Skip ${scorer}: config not found ${cfg}" >&2
      continue
    fi
    out_path="${output_dir}/${base_name}.txt"
    # Skip if any existing report for this scorer in the output dir (tolerate legacy file names)
    existing_glob=("${output_dir}"/*_"${scorer}".txt)
    if compgen -G "${output_dir}/*_${scorer}.txt" > /dev/null; then
      echo "Skip ${scorer} on ${rel_path}: output already exists"
      continue
    fi
    echo "Running ${scorer} on ${rel_path}"
    metric_args_json=$(printf '{"ASR":{"scorer_name":"%s","config_path":"%s"}}' "${scorer}" "${cfg}")
    uv run python evaluate_metrics.py \
      --metrics="ASR" \
      --metric_args="${metric_args_json}" \
      --json_path="${json_path}" \
      --output_path="${out_path}"
  done

  frr_out_dir="${FRR_OUTPUT_ROOT}/${rel_no_ext}"
  mkdir -p "${frr_out_dir}"
  frr_out_path="${frr_out_dir}/${base_name}.txt"
  frr_args_json=$(printf '{"FRR":{"mode":"%s"}}' "${FRR_MODE}")
  uv run python evaluate_metrics.py \
    --metrics="FRR" \
    --metric_args="${frr_args_json}" \
    --json_path="${json_path}" \
    --output_path="${frr_out_path}"
done

# 生成所有模型的 MDS 汇总报告（基于 ASR evaluation_report 目录）
MDS_OUTPUT_DIR="${ROOT_DIR}/evaluation_report/mds"
mkdir -p "${MDS_OUTPUT_DIR}"
MDS_OUTPUT_PATH="${MDS_OUTPUT_DIR}/mds_report.txt"
MDS_ARGS=$(printf '{"MDS":{"report_root":"%s","lambda_penalty":1.0}}' "${OUTPUT_ROOT}")
uv run python evaluate_metrics.py \
  --metrics="MDS" \
  --metric_args="${MDS_ARGS}" \
  --json_path="${filtered_result_files[0]}" \
  --output_path="${MDS_OUTPUT_PATH}"

# 计算平均各个 scorer 的平均 ASR 并总结到 csv，markdown 文件中
echo "Summarizing reports in ${OUTPUT_ROOT}"
uv run python report/summarize_reports.py

# 生成 Kappa 一致性报告（基于 summary_wide.csv）
KAPPA_OUTPUT_DIR="${ROOT_DIR}/evaluation_report/kappa"
mkdir -p "${KAPPA_OUTPUT_DIR}"
KAPPA_OUTPUT_PATH="${KAPPA_OUTPUT_DIR}/kappa_report.csv"
KAPPA_ARGS=$(printf '{"Kappa":{"input_csv":"%s","threshold":0.5,"min_raters":2,"include_rows":true}}' "${OUTPUT_ROOT}/summary_wide.csv")
uv run python evaluate_metrics.py \
  --metrics="Kappa" \
  --metric_args="${KAPPA_ARGS}" \
  --json_path="${filtered_result_files[0]}" \
  --output_path="${KAPPA_OUTPUT_PATH}"

# 标注三分类标签
TERNARY_DIR="${RESULTS_DIR}"
if [[ -d "${TERNARY_DIR}" ]]; then
  if [[ -z "${AZURE_OPENAI_DEPLOYMENT:-}" ]]; then
    echo "AZURE_OPENAI_DEPLOYMENT is required for ternary labeling." >&2
    exit 1
  fi
  mapfile -t ternary_files < <(find "${TERNARY_DIR}" -type f -name "*.jsonl" | sort)
  if [[ ${#ternary_files[@]} -eq 0 ]]; then
    echo "No ternary jsonl files found in ${TERNARY_DIR}" >&2
  else
    echo "Running ternary labeling in ${TERNARY_DIR}"
    for json_path in "${ternary_files[@]}"; do
      uv run python metrics/ternary_metrics.py \
        --input "${json_path}" \
        --judge-deployment "${AZURE_OPENAI_DEPLOYMENT}"
    done
    echo "Running bias metrics in ${TERNARY_DIR}" # 计算 bias
    for json_path in "${ternary_files[@]}"; do
      uv run python metrics/bias_metrics.py --input "${json_path}"
    done
    echo "Running WSL metrics in ${TERNARY_DIR}" # 计算加权安全损失
    for json_path in "${ternary_files[@]}"; do
      uv run python metrics/wsl_metrics.py --input "${json_path}"
    done
    echo "Running cost matrix metrics in ${TERNARY_DIR}" # 计算代价矩阵
    for json_path in "${ternary_files[@]}"; do
      uv run python metrics/cm_metrics.py --input "${json_path}"
    done
  fi
fi

# 生成最终的 evaluation dashboard 报告，包括可视化内容，但只包含数据，不包括 LLM 对数据的分析
echo "Generating evaluation dashboard in ${ROOT_DIR}/evaluation_report"
uv run python report/summary_dashboard.py

# 生成结构化事实与深度评测报告（默认不调用 LLM）
echo "Generating facts and deep report in ${ROOT_DIR}/evaluation_report"
uv run python report/facts_builder.py
uv run python report/final_report.py --provider azure --model "${AZURE_OPENAI_DEPLOYMENT}"
