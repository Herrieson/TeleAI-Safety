import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

from metrics import ASRMetric, ASRMetricConfig, get_metric
from metrics.base_metric import MetricUpdate


def parse_sample(line: str) -> Dict[str, Any]:
    try:
        item = json.loads(line.strip())
    except Exception as e:
        print(f"[Scoring] JSON parse failed: {e}", flush=True)
        return {}
    if not isinstance(item, dict):
        return {}
    query = None
    response = None
    query_field_candidates = ["goals", "query", "final_query", "input"]
    response_field_candidates = ["response", "target", "targets"]
    for field in query_field_candidates:
        if field in item:
            query = item[field]
            break
    for field in response_field_candidates:
        if field in item:
            response = item[field]
            break
    safety_label = item.get("safety_label")
    return {
        **item,
        "query": query,
        "response": response,
        "safety_label": safety_label,
        "__raw__": item,
    }


def build_metrics(metric_names: List[str], metric_args: Dict[str, Dict]) -> List:
    metrics = []
    for name in metric_names:
        lower_name = name.lower()
        cfg = metric_args.get(name) or metric_args.get(lower_name) or {}
        if lower_name == "asr":
            # 默认参数仅在缺省时使用，避免脚本与 ASR 绑定
            default_cfg = {
                "scorer_name": "PatternScorer",
                "config_path": "./metrics/asr/config/pattern_scorer.yaml",
            }
            merged = {**default_cfg, **cfg}
            metrics.append(ASRMetric(ASRMetricConfig(**merged)))
        else:
            metrics.append(get_metric(name, **cfg))
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metrics",
        type=str,
        default="ASR",
        help="Comma separated metric names (default: ASR)",
    )
    parser.add_argument(
        "--metric_args",
        type=str,
        default="{}",
        help='JSON string of metric-specific args, e.g. \'{"ASR": {"scorer_name":"PatternScorer","config_path":"./metrics/asr/config/pattern_scorer.yaml"}}\'',
    )
    parser.add_argument("--json_path", type=str, required=True, help="Path to json file for evaluation")
    parser.add_argument("--output_path", type=str, default="./eval_summary.txt", help="Path to output summary txt")
    parser.add_argument("--workers", type=int, default=32, help="Number of threads for scoring")
    parser.add_argument(
        "--prediction_output_path",
        type=str,
        default="",
        help="Optional output JSONL path for per-sample predictions",
    )
    parser.add_argument(
        "--annotate_only",
        action="store_true",
        help="Only save per-sample predictions and skip summary report generation",
    )
    args = parser.parse_args()

    metric_names = [m.strip() for m in args.metrics.split(",") if m.strip()]
    try:
        metric_args = json.loads(args.metric_args)
        if not isinstance(metric_args, dict):
            raise ValueError
    except Exception:
        raise SystemExit("--metric_args must be a JSON object mapping metric name to kwargs")
    metrics = build_metrics(metric_names, metric_args)
    json_path = args.json_path
    output_path = args.output_path
    workers = max(1, args.workers)
    prediction_output_path = args.prediction_output_path.strip()

    # Prepare output
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    base_filename = os.path.basename(output_path)
    base_stub = base_filename.split(".")[0]
    base_ext = base_filename.split(".")[-1]

    # Read input json
    with open(json_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_lines = len(lines)
    progress_step = max(1, total_lines // 10) if total_lines else 1

    parsed_samples = [parse_sample(line) for line in lines]
    metric_states = {metric.name: metric.create_state() for metric in metrics}
    metric_predictions: Dict[str, List[Dict[str, Any]]] = {
        metric.name: [{} for _ in range(total_lines)] for metric in metrics
    }

    def process_line(index_and_sample: Tuple[int, Dict[str, Any]]):
        index, sample = index_and_sample
        updates: Dict[str, MetricUpdate] = {}
        predictions: Dict[str, Dict[str, Any]] = {}
        for metric in metrics:
            update = metric.process_sample(sample)
            updates[metric.name] = update
            if update.extra and isinstance(update.extra.get("prediction"), dict):
                predictions[metric.name] = update.extra.get("prediction") or {}
        return index, updates, predictions

    processed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(process_line, pair) for pair in enumerate(parsed_samples)]
        for future in as_completed(futures):
            index, updates, predictions = future.result()
            for metric in metrics:
                update = updates.get(metric.name) or MetricUpdate()
                metric.merge(metric_states[metric.name], update)
                metric_predictions[metric.name][index] = predictions.get(metric.name, {})
            processed += 1
            if total_lines and (processed % progress_step == 0 or processed == total_lines):
                print(f"[Progress] {processed}/{total_lines} processed", flush=True)

    if prediction_output_path:
        prediction_dir = os.path.dirname(prediction_output_path)
        if prediction_dir:
            os.makedirs(prediction_dir, exist_ok=True)
        for metric in metrics:
            if len(metrics) == 1:
                metric_prediction_path = prediction_output_path
            else:
                pred_stub, pred_ext = os.path.splitext(prediction_output_path)
                metric_prediction_path = f"{pred_stub}_{metric.name}{pred_ext or '.jsonl'}"
            with open(metric_prediction_path, "w", encoding="utf-8") as f:
                for sample, prediction in zip(parsed_samples, metric_predictions[metric.name]):
                    raw = sample.get("__raw__")
                    if not isinstance(raw, dict):
                        continue
                    out_item = dict(raw)
                    out_item.update(prediction or {})
                    f.write(json.dumps(out_item, ensure_ascii=False) + "\n")
            print(f"[Predictions] wrote {metric_prediction_path}", flush=True)

    if args.annotate_only:
        return

    # 输出每个指标的报告
    for metric in metrics:
        state = metric_states[metric.name]
        summary_text = metric.render_report(state=state, input_file=json_path)
        if len(metrics) == 1:
            out_name = f"{base_stub}_{metric.output_tag}.{base_ext}"
        else:
            out_name = f"{base_stub}_{metric.name}_{metric.output_tag}.{base_ext}"
        metric_output_path = os.path.join(output_dir, out_name) if output_dir else out_name
        print(summary_text)
        with open(metric_output_path, "w", encoding="utf-8") as f:
            f.write(summary_text)


if __name__ == "__main__":
    main()
