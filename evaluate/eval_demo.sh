#!/usr/bin/env bash
set -euo pipefail

# 批量对 results/*.jsonl 运行多个 scorer，并将结果写入 evaluation_report/<输入文件名>/ 下。
# 默认只跑轻量方法（Pattern / Prefix）。如需更多 scorer，可通过环境变量 EVAL_SCORERS 覆盖，例如：
#   EVAL_SCORERS="PatternScorer PrefixMatchScorer ClassficationScorer" ./eval_demo.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

RESULTS_DIR="${ROOT_DIR}/results"
OUTPUT_ROOT="${ROOT_DIR}/evaluation_report"

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
  ["PatternScorer"]="${ROOT_DIR}/config/pattern_scorer.yaml"
  ["PrefixMatchScorer"]="${ROOT_DIR}/config/prefix_match_scorer.yaml"
  ["ClassficationScorer"]="${ROOT_DIR}/config/classfication_scorer.yaml"
  ["GPTScorer"]="${ROOT_DIR}/config/gpt_scorer.yaml"
  ["GPT5Scorer"]="${ROOT_DIR}/config/gpt5_scorer.yaml"
  ["DSV3Scorer"]="${ROOT_DIR}/config/dsv3_scorer.yaml"
  ["DSR1Scorer"]="${ROOT_DIR}/config/dsr1_scorer.yaml"
  ["MultiAPIScorer"]="${ROOT_DIR}/config/multi_api_scorer.yaml"
)

mapfile -t result_files < <(find "${RESULTS_DIR}" -type f -name "*.jsonl" | sort)
if [[ ${#result_files[@]} -eq 0 ]]; then
  echo "No jsonl files found in ${RESULTS_DIR}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_ROOT}"

for json_path in "${result_files[@]}"; do
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
    uv run python eval_summary_report.py \
      --scorer="${scorer}" \
      --config_path="${cfg}" \
      --json_path="${json_path}" \
      --output_path="${out_path}"
  done
done
