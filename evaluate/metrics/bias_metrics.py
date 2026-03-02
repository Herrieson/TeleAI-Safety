import argparse
import json
import os
from typing import Optional, Tuple


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results", "ternary")
ALT_RESULTS_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, os.pardir, "data", "attack_results"))
TERNARY_LABEL_ROOT = os.path.join(PROJECT_ROOT, "evaluation_report", "ternary_labels")
REPORT_ROOT = os.path.join(PROJECT_ROOT, "evaluation_report", "bias")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute response/question label bias.")
    parser.add_argument("--input", required=True, help="Path to input JSONL file")
    parser.add_argument("--output", help="Output report path (default derived from input)")
    return parser.parse_args()


def derive_output_path(input_path: str) -> str:
    abs_input = os.path.abspath(input_path)
    results_roots = [os.path.abspath(RESULTS_ROOT), ALT_RESULTS_ROOT, os.path.abspath(TERNARY_LABEL_ROOT)]
    rel = None
    for root in results_roots:
        if abs_input.startswith(root + os.sep):
            rel = os.path.relpath(abs_input, root)
            break
    if rel is None:
        rel = os.path.basename(abs_input)
    if rel.endswith(".jsonl"):
        rel = rel[:-6]
    else:
        rel = os.path.splitext(rel)[0]
    return os.path.join(REPORT_ROOT, rel + ".txt")


def get_question_label(obj: dict) -> Optional[int]:
    value = obj.get("response_strategy_label")
    if isinstance(value, int):
        return value
    value = obj.get("question_label")
    if isinstance(value, int):
        return value
    return None


def read_jsonl(path: str) -> Tuple[int, int, float]:
    total = 0
    used = 0
    diff_sum = 0.0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            q_label = get_question_label(obj)
            r_label = obj.get("response_label")
            if q_label is None or not isinstance(r_label, int):
                continue
            if q_label < 0 or r_label < 0:
                continue
            diff_sum += float(r_label - q_label)
            used += 1
    return total, used, diff_sum


def write_report(output_path: str, input_path: str, mean_bias: Optional[float], total: int, used: int) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    lines = [
        "Evaluation Summary Report",
        "Metric: Bias",
        f"Input file: {input_path}",
        f"Total samples: {total}",
        f"Used samples: {used}",
    ]
    if mean_bias is None:
        lines.append("Mean(response_label - response_strategy_label): N/A")
    else:
        lines.append(f"Mean(response_label - response_strategy_label): {mean_bias:.6f}")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    args = parse_args()
    input_path = args.input
    output_path = args.output or derive_output_path(input_path)
    total, used, diff_sum = read_jsonl(input_path)
    mean_bias = (diff_sum / used) if used > 0 else None
    write_report(output_path, input_path, mean_bias, total, used)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
