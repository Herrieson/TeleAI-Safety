import argparse
import csv
import json
import os
import re
import statistics
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DEFAULT_SUMMARY_LONG = os.path.join(PROJECT_ROOT, "evaluation_report", "asr", "summary_long.csv")
DEFAULT_SUMMARY_OVERVIEW = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_overview.md")
DEFAULT_MDS_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "mds")
DEFAULT_KAPPA_CSV = os.path.join(PROJECT_ROOT, "evaluation_report", "kappa", "kappa_report_kappa.csv")
DEFAULT_BIAS_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "bias")
DEFAULT_WSL_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "wsl")
DEFAULT_CM_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "cm")
DEFAULT_FRR_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "frr")
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "evaluation_report", "facts.json")
DEFAULT_FACTS_MD = os.path.join(PROJECT_ROOT, "evaluation_report", "facts.md")

DEFAULT_PLOTS_ROOT = os.path.join(PROJECT_ROOT, "evaluation_report", "plots")
DEFAULT_PLOTS = {
    "heatmap": os.path.join(DEFAULT_PLOTS_ROOT, "heatmap", "asr_strict_model_attack.png"),
    "model_bar": os.path.join(DEFAULT_PLOTS_ROOT, "bar", "asr_strict_model_avg.png"),
    "attack_bar": os.path.join(DEFAULT_PLOTS_ROOT, "bar", "asr_strict_attack_avg.png"),
    "legacy_heatmap": os.path.join(DEFAULT_PLOTS_ROOT, "heatmap", "asr_legacy_model_attack.png"),
    "legacy_model_bar": os.path.join(DEFAULT_PLOTS_ROOT, "bar", "asr_legacy_model_avg.png"),
    "legacy_attack_bar": os.path.join(DEFAULT_PLOTS_ROOT, "bar", "asr_legacy_attack_avg.png"),
    "metric_bar": os.path.join(DEFAULT_PLOTS_ROOT, "bar", "summary_bar_metrics.png"),
    "frr_bar": os.path.join(DEFAULT_PLOTS_ROOT, "bar", "frr_strict_model_avg.png"),
}
LEGACY_PLOTS = {
    "heatmap": os.path.join(PROJECT_ROOT, "evaluation_report", "summary_heatmap.png"),
    "model_bar": os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_models.png"),
    "attack_bar": os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_attacks.png"),
    "metric_bar": os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_metrics.png"),
    "frr_bar": os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_models_frr.png"),
}

KNOWN_ATTACKS = [
    "cipher",
    "deepinception",
    "deep_inception",
    "jailbroken",
    "pair",
    "rene",
    "artprompt",
    "dra",
    "dan",
]

RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
ALT_RESULTS_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, os.pardir, "data", "attack_results"))
ASR_LABEL_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "asr_labels")
FRR_LABEL_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "frr_labels")
EXCLUDED_MODEL_DIRS = {"manifests", "runs"}


def load_authoritative_models(results_dir: str = ALT_RESULTS_DIR) -> List[str]:
    if not os.path.isdir(results_dir):
        return []
    models: List[str] = []
    for name in sorted(os.listdir(results_dir)):
        path = os.path.join(results_dir, name)
        if not os.path.isdir(path) or name in EXCLUDED_MODEL_DIRS:
            continue
        models.append(name)
    return models


def filter_matrix_by_models(
    matrix: Dict[str, Dict[str, float]],
    allowed_models: Optional[Iterable[str]],
) -> Dict[str, Dict[str, float]]:
    if not allowed_models:
        return matrix
    allowed = set(allowed_models)
    return {model: attacks for model, attacks in matrix.items() if model in allowed}


def filter_row_list_by_models(
    rows: List[Dict[str, object]],
    allowed_models: Optional[Iterable[str]],
) -> List[Dict[str, object]]:
    if not allowed_models:
        return rows
    allowed = set(allowed_models)
    return [row for row in rows if str(row.get("model") or "") in allowed]


def filter_metric_map_by_models(
    values: Dict[str, List[float]],
    allowed_models: Optional[Iterable[str]],
) -> Dict[str, List[float]]:
    if not allowed_models:
        return values
    allowed = set(allowed_models)
    return {model: vals for model, vals in values.items() if model in allowed}


def normalize_attack_name(name: str) -> str:
    return name.replace("_", "")


def is_legacy_scorer_name(scorer: str) -> bool:
    return "legacy" in (scorer or "").lower()


def split_attack_and_model(text: str) -> Tuple[Optional[str], Optional[str]]:
    text_lower = text.lower()
    for attack in KNOWN_ATTACKS:
        if text_lower.startswith(attack):
            model_raw = text[len(attack):].lstrip("_-")
            return normalize_attack_name(attack), model_raw
    if "_" in text:
        attack_part, model_part = text.split("_", 1)
        if attack_part.lower() in KNOWN_ATTACKS:
            return normalize_attack_name(attack_part), model_part
    return None, None


def parse_attack_run(attack_run: str) -> Optional[Tuple[str, str]]:
    parts = attack_run.split(os.sep)
    if len(parts) >= 2:
        model = parts[0]
        attack_part = parts[1]
        attack_raw, _ = split_attack_and_model(attack_part)
        if attack_raw:
            return model, attack_raw
        for attack in KNOWN_ATTACKS:
            if attack_part.lower().startswith(attack):
                return model, normalize_attack_name(attack)
        for part in parts[1:]:
            if part.lower() in KNOWN_ATTACKS:
                return model, normalize_attack_name(part)
        return model, attack_part

    attack_raw, model_raw = split_attack_and_model(attack_run)
    if attack_raw and model_raw:
        return model_raw, attack_raw
    return None


def _find_relpath_after_marker(input_path: str, marker_parts: Iterable[str]) -> Optional[str]:
    normalized_parts = os.path.normpath(input_path).split(os.sep)
    marker = list(marker_parts)
    if not marker:
        return None
    max_idx = len(normalized_parts) - len(marker)
    for idx in range(max_idx + 1):
        if normalized_parts[idx : idx + len(marker)] != marker:
            continue
        suffix = normalized_parts[idx + len(marker) :]
        if not suffix:
            return ""
        return os.path.join(*suffix)
    return None


def derive_attack_run(input_file: str) -> Tuple[str, str]:
    abs_input = os.path.abspath(input_file)
    candidate_roots = [os.path.abspath(RESULTS_DIR), ALT_RESULTS_DIR]
    rel = None
    for root in candidate_roots:
        if abs_input.startswith(root + os.sep):
            rel = os.path.relpath(abs_input, root)
            break
    # ASR/FRR report inputs are typically label files, prefer restoring model/attack.
    if rel is None:
        for label_root in (os.path.abspath(ASR_LABEL_DIR), os.path.abspath(FRR_LABEL_DIR)):
            if abs_input.startswith(label_root + os.sep):
                rel_labels = os.path.relpath(abs_input, label_root)
                label_parts = rel_labels.split(os.sep)
                if len(label_parts) >= 2:
                    model = label_parts[0]
                    attack = label_parts[1]
                    return f"{model}/{attack}", model
                rel = rel_labels
                break
    if rel is None:
        rel = _find_relpath_after_marker(abs_input, ["data", "attack_results"])
    if rel is None:
        for marker in (["evaluation_report", "asr_labels"], ["evaluation_report", "frr_labels"]):
            rel_labels = _find_relpath_after_marker(abs_input, marker)
            if rel_labels is None:
                continue
            label_parts = rel_labels.split(os.sep)
            if len(label_parts) >= 2:
                model = label_parts[0]
                attack = label_parts[1]
                return f"{model}/{attack}", model
            rel = rel_labels
            break
    if rel is None:
        rel = _find_relpath_after_marker(abs_input, ["results"])
    if rel is None:
        rel = os.path.basename(abs_input)
    if rel.endswith(".jsonl"):
        rel_no_ext = rel[:-6]
    else:
        rel_no_ext = os.path.splitext(rel)[0]
    parts = rel_no_ext.split(os.sep)
    attack_group = parts[0] if parts else rel_no_ext
    return rel_no_ext, attack_group


def read_summary_long(path: str) -> Tuple[List[Dict[str, str]], List[str]]:
    rows: List[Dict[str, str]] = []
    unparsed: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            scorer = (row.get("scorer") or "").strip()
            if is_legacy_scorer_name(scorer):
                continue
            input_file = (row.get("input_file") or "").strip()
            parsed = None
            attack_run = (row.get("attack_run") or "").strip()
            if input_file:
                derived_attack_run, _ = derive_attack_run(input_file)
                parsed = parse_attack_run(derived_attack_run)
            if not parsed:
                parsed = parse_attack_run(attack_run)
            if not parsed:
                if attack_run:
                    unparsed.append(attack_run)
                continue
            model, attack = parsed
            row_out = dict(row)
            row_out["model"] = model
            row_out["attack"] = attack
            rows.append(row_out)
    return rows, unparsed


def read_frr_reports(report_dir: str) -> Dict[str, Dict[str, float]]:
    if not os.path.isdir(report_dir):
        return {}
    frr_matrix: Dict[str, Dict[str, float]] = {}
    for root, _, files in os.walk(report_dir):
        for fname in files:
            if not fname.endswith(".txt"):
                continue
            path = os.path.join(root, fname)
            input_file = None
            frr_val = None
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("Input file:"):
                        input_file = line.split(":", 1)[1].strip()
                    elif line.startswith("False Refusal Rate (FRR):"):
                        try:
                            frr_val = float(line.split(":", 1)[1].strip())
                        except ValueError:
                            frr_val = None
            if not input_file or frr_val is None:
                continue
            attack_run, _ = derive_attack_run(input_file)
            parsed = parse_attack_run(attack_run)
            if not parsed:
                continue
            model, attack = parsed
            frr_matrix.setdefault(model, {})[attack] = frr_val
    return frr_matrix


def average(values: Iterable[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def compute_model_attack_matrix(
    rows: List[Dict[str, str]],
    value_field: str = "asr",
) -> Dict[str, Dict[str, float]]:
    buckets: Dict[Tuple[str, str], List[float]] = {}
    for row in rows:
        raw = row.get(value_field)
        if raw in (None, ""):
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        key = (row["model"], row["attack"])
        buckets.setdefault(key, []).append(value)

    matrix: Dict[str, Dict[str, float]] = {}
    for (model, attack), vals in buckets.items():
        matrix.setdefault(model, {})[attack] = sum(vals) / len(vals)
    return matrix


def compute_model_summary(
    matrix: Dict[str, Dict[str, float]],
    frr_matrix: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[Dict[str, object]]:
    summary: List[Dict[str, object]] = []
    for model, attacks in matrix.items():
        vals = list(attacks.values())
        if not vals:
            continue
        avg_asr = sum(vals) / len(vals)
        avg_frr = None
        if frr_matrix:
            frr_vals = list(frr_matrix.get(model, {}).values())
            if frr_vals:
                avg_frr = sum(frr_vals) / len(frr_vals)
        summary.append(
            {
                "model": model,
                "avg_asr": avg_asr,
                "avg_frr": avg_frr,
                "attacks_covered": len(vals),
            }
        )
    return sorted(summary, key=lambda r: r["model"])


def compute_attack_summary(
    matrix: Dict[str, Dict[str, float]],
    frr_matrix: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[Dict[str, object]]:
    buckets: Dict[str, List[float]] = {}
    for attacks in matrix.values():
        for attack, val in attacks.items():
            buckets.setdefault(attack, []).append(val)
    frr_buckets: Dict[str, List[float]] = {}
    if frr_matrix:
        for attacks in frr_matrix.values():
            for attack, val in attacks.items():
                frr_buckets.setdefault(attack, []).append(val)
    summary: List[Dict[str, object]] = []
    for attack, vals in buckets.items():
        if not vals:
            continue
        frr_vals = frr_buckets.get(attack, [])
        avg_frr = sum(frr_vals) / len(frr_vals) if frr_vals else None
        summary.append(
            {
                "attack": attack,
                "avg_asr": sum(vals) / len(vals),
                "avg_frr": avg_frr,
            }
        )
    return sorted(summary, key=lambda r: r["attack"])


def compute_model_stats(matrix: Dict[str, Dict[str, float]]) -> List[Dict[str, object]]:
    stats: List[Dict[str, object]] = []
    for model, attacks in matrix.items():
        vals = list(attacks.values())
        if not vals:
            continue
        mu = sum(vals) / len(vals)
        sigma = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        stats.append(
            {
                "model": model,
                "mu_asr": mu,
                "sigma_asr": sigma,
                "min_asr": min(vals),
                "max_asr": max(vals),
                "range_asr": max(vals) - min(vals),
                "attacks_covered": len(vals),
            }
        )
    return sorted(stats, key=lambda r: r["model"])


def read_mds_reports(mds_dir: str) -> List[Dict[str, object]]:
    if not os.path.isdir(mds_dir):
        return []
    rows: List[Dict[str, object]] = []
    for fname in sorted(os.listdir(mds_dir)):
        if not fname.endswith(".txt"):
            continue
        path = os.path.join(mds_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f]

        current = None
        for line in lines:
            if line.startswith("## "):
                if current and current.get("mds") is not None:
                    rows.append(current)
                model = line[3:].strip()
                current = {
                    "model": model,
                    "attack_types": None,
                    "mu_asr": None,
                    "sigma_asr": None,
                    "mds": None,
                    "report": os.path.relpath(path, PROJECT_ROOT),
                }
                continue
            if not current:
                continue
            if line.lower().startswith("attack types:"):
                value = line.split(":", 1)[1].strip()
                current["attack_types"] = int(value) if value.isdigit() else None
            elif line.lower().startswith("mu_asr:"):
                try:
                    current["mu_asr"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    current["mu_asr"] = None
            elif line.lower().startswith("sigma_asr:"):
                try:
                    current["sigma_asr"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    current["sigma_asr"] = None
            elif line.lower().startswith("mds:"):
                try:
                    current["mds"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    current["mds"] = None
        if current and current.get("mds") is not None:
            rows.append(current)
    return sorted(rows, key=lambda r: r["model"])


def read_metric_reports(report_dir: str, value_pattern: str) -> Dict[str, List[float]]:
    if not os.path.isdir(report_dir):
        return {}
    value_re = re.compile(value_pattern, re.IGNORECASE)
    values: Dict[str, List[float]] = {}
    for root, _, files in os.walk(report_dir):
        for fname in files:
            if not fname.endswith(".txt"):
                continue
            path = os.path.join(root, fname)
            rel = os.path.relpath(path, report_dir)
            parts = rel.split(os.sep)
            if not parts:
                continue
            model = parts[0]
            val = None
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    m = value_re.match(line)
                    if m:
                        try:
                            val = float(m.group(1))
                        except ValueError:
                            val = None
                        break
            if val is None:
                continue
            values.setdefault(model, []).append(val)
    return values


def mean_by_model(values: Dict[str, List[float]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for model, vals in values.items():
        if not vals:
            continue
        out[model] = sum(vals) / len(vals)
    return out


def read_kappa_summary(path: str) -> Optional[Dict[str, object]]:
    if not os.path.isfile(path):
        alt_path = ""
        if path.endswith("_kappa.csv"):
            alt_path = path[:-10] + ".csv"
        elif path.endswith(".csv"):
            alt_path = path[:-4] + "_kappa.csv"
        if alt_path and os.path.isfile(alt_path):
            path = alt_path
        else:
            return None
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("attack_run") or "").strip() == "__summary__":
                return {
                    "avg_kappa": row.get("avg_kappa") or row.get("kappa"),
                    "median_kappa": row.get("median_kappa"),
                    "min_kappa": row.get("min_kappa"),
                    "max_kappa": row.get("max_kappa"),
                    "total_rows": row.get("total_rows"),
                    "skipped_rows": row.get("skipped_rows"),
                }
    return None


def collect_plots(paths: Dict[str, str]) -> Dict[str, str]:
    plots: Dict[str, str] = {}
    for key, path in paths.items():
        if os.path.isfile(path):
            plots[key] = os.path.relpath(path, PROJECT_ROOT)
            continue
        legacy_path = LEGACY_PLOTS.get(key)
        if legacy_path and os.path.isfile(legacy_path):
            plots[key] = os.path.relpath(legacy_path, PROJECT_ROOT)
    return plots


def build_facts_md(facts: Dict[str, object], output_path: str) -> None:
    lines: List[str] = ["# Evaluation Facts", ""]
    lines.append(f"Generated at: {facts.get('generated_at')}")
    lines.append("")

    model_summary = facts.get("model_summary") or []
    if model_summary:
        lines.extend(
            [
                "## Model Summary",
                "",
                "| Model | Avg ASR | Avg FRR | Attacks Covered |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in model_summary:
            avg_frr = row.get("avg_frr")
            avg_frr_str = f"{avg_frr:.4f}" if isinstance(avg_frr, (int, float)) else ""
            lines.append(
                "| {model} | {avg_asr:.4f} | {avg_frr} | {attacks_covered} |".format(
                    model=row["model"],
                    avg_asr=row["avg_asr"],
                    avg_frr=avg_frr_str,
                    attacks_covered=row["attacks_covered"],
                )
            )
        lines.append("")

    mds_summary = facts.get("mds_summary") or []
    if mds_summary:
        lines.extend(["## MDS Summary", "", "| Model | MDS | mu_ASR | sigma_ASR | Attack types | Report |", "| --- | --- | --- | --- | --- | --- |"])
        for row in mds_summary:
            lines.append(
                "| {model} | {mds:.6f} | {mu_asr:.6f} | {sigma_asr:.6f} | {attack_types} | {report} |".format(
                    **row
                )
            )
        lines.append("")

    kappa = facts.get("kappa_summary")
    if kappa:
        lines.extend(["## Kappa Summary", ""])
        lines.append(
            "avg={avg_kappa}, median={median_kappa}, min={min_kappa}, max={max_kappa}, total_rows={total_rows}, skipped_rows={skipped_rows}".format(
                **kappa
            )
        )
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build evaluation facts from summary outputs.")
    parser.add_argument("--summary-long", default=DEFAULT_SUMMARY_LONG, help="Path to summary_long.csv")
    parser.add_argument("--summary-overview", default=DEFAULT_SUMMARY_OVERVIEW, help="Path to summary_overview.md")
    parser.add_argument("--mds-dir", default=DEFAULT_MDS_DIR, help="Directory with MDS reports")
    parser.add_argument("--kappa-csv", default=DEFAULT_KAPPA_CSV, help="Kappa report CSV path")
    parser.add_argument("--bias-dir", default=DEFAULT_BIAS_DIR, help="Directory with Bias reports")
    parser.add_argument("--wsl-dir", default=DEFAULT_WSL_DIR, help="Directory with WSL reports")
    parser.add_argument("--cm-dir", default=DEFAULT_CM_DIR, help="Directory with CM reports")
    parser.add_argument("--frr-dir", default=DEFAULT_FRR_DIR, help="Directory with FRR reports")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output facts.json path")
    parser.add_argument("--facts-md", default=DEFAULT_FACTS_MD, help="Output facts.md path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not os.path.isfile(args.summary_long):
        raise SystemExit(f"summary_long.csv not found: {args.summary_long}")

    authoritative_models = load_authoritative_models()
    rows, unparsed = read_summary_long(args.summary_long)
    rows = filter_row_list_by_models(rows, authoritative_models)
    matrix = compute_model_attack_matrix(rows)
    frr_matrix = read_frr_reports(args.frr_dir)
    matrix = filter_matrix_by_models(matrix, authoritative_models)
    frr_matrix = filter_matrix_by_models(frr_matrix, authoritative_models)
    model_summary = compute_model_summary(matrix, frr_matrix)
    attack_summary = compute_attack_summary(matrix, frr_matrix)
    model_stats = compute_model_stats(matrix)

    mds_summary = read_mds_reports(args.mds_dir)
    bias_vals = read_metric_reports(
        args.bias_dir,
        r"^Mean\(response_label - (?:question_label|response_strategy_label)\):\s*([0-9.\-]+)",
    )
    wsl_vals = read_metric_reports(args.wsl_dir, r"^Mean weighted loss:\s*([0-9.\-]+)")
    cm_vals = read_metric_reports(args.cm_dir, r"^Mean cost:\s*([0-9.\-]+)")

    mds_summary = filter_row_list_by_models(mds_summary, authoritative_models)
    bias_vals = filter_metric_map_by_models(bias_vals, authoritative_models)
    wsl_vals = filter_metric_map_by_models(wsl_vals, authoritative_models)
    cm_vals = filter_metric_map_by_models(cm_vals, authoritative_models)

    bias_mean = mean_by_model(bias_vals)
    wsl_mean = mean_by_model(wsl_vals)
    cm_mean = mean_by_model(cm_vals)

    metric_summary = []
    for model in sorted(set(bias_mean) | set(wsl_mean) | set(cm_mean)):
        metric_summary.append(
            {
                "model": model,
                "bias": bias_mean.get(model),
                "wsl": wsl_mean.get(model),
                "cm": cm_mean.get(model),
            }
        )

    kappa_summary = read_kappa_summary(args.kappa_csv)
    plots = collect_plots(DEFAULT_PLOTS)

    facts = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "sources": {
            "summary_long": os.path.relpath(args.summary_long, PROJECT_ROOT),
            "summary_overview": os.path.relpath(args.summary_overview, PROJECT_ROOT)
            if os.path.isfile(args.summary_overview)
            else None,
            "mds_dir": os.path.relpath(args.mds_dir, PROJECT_ROOT),
            "kappa_csv": os.path.relpath(args.kappa_csv, PROJECT_ROOT)
            if os.path.isfile(args.kappa_csv)
            else None,
            "bias_dir": os.path.relpath(args.bias_dir, PROJECT_ROOT),
            "wsl_dir": os.path.relpath(args.wsl_dir, PROJECT_ROOT),
            "cm_dir": os.path.relpath(args.cm_dir, PROJECT_ROOT),
        },
        "models": sorted(matrix.keys()),
        "attacks": sorted({attack for attacks in matrix.values() for attack in attacks.keys()}),
        "model_attack_matrix": matrix,
        "model_summary": model_summary,
        "attack_summary": attack_summary,
        "model_stats": model_stats,
        "mds_summary": mds_summary,
        "metric_summary": metric_summary,
        "kappa_summary": kappa_summary,
        "plots": plots,
        "unparsed_attack_runs": sorted(set(unparsed)),
    }

    output_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(output_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2, ensure_ascii=False)

    if args.facts_md:
        build_facts_md(facts, args.facts_md)

    print(f"Wrote {args.output}")
    if args.facts_md:
        print(f"Wrote {args.facts_md}")


if __name__ == "__main__":
    main()
