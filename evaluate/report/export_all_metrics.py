import argparse
import csv
import json
import os
from typing import Any, Dict, List, Optional


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DEFAULT_FACTS = os.path.join(PROJECT_ROOT, "evaluation_report", "facts.json")
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "evaluation_report", "all_metrics_summary.csv")
DEFAULT_SUMMARY_WIDE = os.path.join(PROJECT_ROOT, "evaluation_report", "asr", "summary_wide.csv")
DEFAULT_DETAILED_OUTPUT = os.path.join(PROJECT_ROOT, "evaluation_report", "all_metrics_full.csv")


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def load_facts(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid facts file: {path}")
    return data


def load_csv_rows(path: str) -> List[Dict[str, str]]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"CSV file not found: {path}")
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float_text(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value:.6f}"


def _as_int_text(value: Optional[int]) -> str:
    if value is None:
        return ""
    return str(value)


def build_model_rows(facts: Dict[str, Any], kappa: Dict[str, Any]) -> List[Dict[str, Any]]:
    model_summary = facts.get("model_summary") or []
    mds_summary = facts.get("mds_summary") or []
    metric_summary = facts.get("metric_summary") or []

    mds_map = {}
    for row in mds_summary:
        if not isinstance(row, dict):
            continue
        model = row.get("model")
        if isinstance(model, str) and model:
            mds_map[model] = row

    metric_map = {}
    for row in metric_summary:
        if not isinstance(row, dict):
            continue
        model = row.get("model")
        if isinstance(model, str) and model:
            metric_map[model] = row

    rows: List[Dict[str, Any]] = []
    for row in model_summary:
        if not isinstance(row, dict):
            continue
        model = row.get("model")
        if not isinstance(model, str) or not model:
            continue
        mds_row = mds_map.get(model, {})
        ext_row = metric_map.get(model, {})
        rows.append(
            {
                "record_type": "model",
                "model": model,
                "attack": "",
                "avg_asr": _safe_float(row.get("avg_asr")),
                "avg_frr": _safe_float(row.get("avg_frr")),
                "mu_asr": _safe_float(mds_row.get("mu_asr")),
                "sigma_asr": _safe_float(mds_row.get("sigma_asr")),
                "mds": _safe_float(mds_row.get("mds")),
                "bias": _safe_float(ext_row.get("bias")),
                "wsl": _safe_float(ext_row.get("wsl")),
                "cm": _safe_float(ext_row.get("cm")),
                "avg_kappa": _safe_float(kappa.get("avg_kappa")),
                "median_kappa": _safe_float(kappa.get("median_kappa")),
                "min_kappa": _safe_float(kappa.get("min_kappa")),
                "max_kappa": _safe_float(kappa.get("max_kappa")),
                "kappa_total_rows": _safe_float(kappa.get("total_rows")),
                "kappa_skipped_rows": _safe_float(kappa.get("skipped_rows")),
            }
        )
    return rows


def build_attack_rows(facts: Dict[str, Any], kappa: Dict[str, Any]) -> List[Dict[str, Any]]:
    attack_summary = facts.get("attack_summary") or []
    rows: List[Dict[str, Any]] = []
    for row in attack_summary:
        if not isinstance(row, dict):
            continue
        attack = row.get("attack")
        if not isinstance(attack, str) or not attack:
            continue
        rows.append(
            {
                "record_type": "attack",
                "model": "",
                "attack": attack,
                "avg_asr": _safe_float(row.get("avg_asr")),
                "avg_frr": _safe_float(row.get("avg_frr")),
                "mu_asr": "",
                "sigma_asr": "",
                "mds": "",
                "bias": "",
                "wsl": "",
                "cm": "",
                "avg_kappa": _safe_float(kappa.get("avg_kappa")),
                "median_kappa": _safe_float(kappa.get("median_kappa")),
                "min_kappa": _safe_float(kappa.get("min_kappa")),
                "max_kappa": _safe_float(kappa.get("max_kappa")),
                "kappa_total_rows": _safe_float(kappa.get("total_rows")),
                "kappa_skipped_rows": _safe_float(kappa.get("skipped_rows")),
            }
        )
    return rows


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "record_type",
        "model",
        "attack",
        "avg_asr",
        "avg_frr",
        "mu_asr",
        "sigma_asr",
        "mds",
        "bias",
        "wsl",
        "cm",
        "avg_kappa",
        "median_kappa",
        "min_kappa",
        "max_kappa",
        "kappa_total_rows",
        "kappa_skipped_rows",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _build_model_metric_map(
    facts: Dict[str, Any], kappa: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    model_summary = facts.get("model_summary") or []
    mds_summary = facts.get("mds_summary") or []
    metric_summary = facts.get("metric_summary") or []

    model_map: Dict[str, Dict[str, Any]] = {}
    for row in model_summary:
        if not isinstance(row, dict):
            continue
        model = row.get("model")
        if not isinstance(model, str) or not model:
            continue
        model_map[model] = {
            "model_avg_asr": _safe_float(row.get("avg_asr")),
            "model_avg_frr": _safe_float(row.get("avg_frr")),
            "attacks_covered": _safe_int(row.get("attacks_covered")),
        }

    for row in mds_summary:
        if not isinstance(row, dict):
            continue
        model = row.get("model")
        if not isinstance(model, str) or not model:
            continue
        base = model_map.setdefault(model, {})
        base["mu_asr"] = _safe_float(row.get("mu_asr"))
        base["sigma_asr"] = _safe_float(row.get("sigma_asr"))
        base["mds"] = _safe_float(row.get("mds"))
        base["attack_types"] = _safe_int(row.get("attack_types"))

    for row in metric_summary:
        if not isinstance(row, dict):
            continue
        model = row.get("model")
        if not isinstance(model, str) or not model:
            continue
        base = model_map.setdefault(model, {})
        base["bias"] = _safe_float(row.get("bias"))
        base["wsl"] = _safe_float(row.get("wsl"))
        base["cm"] = _safe_float(row.get("cm"))

    kappa_payload = {
        "avg_kappa": _safe_float(kappa.get("avg_kappa")),
        "median_kappa": _safe_float(kappa.get("median_kappa")),
        "min_kappa": _safe_float(kappa.get("min_kappa")),
        "max_kappa": _safe_float(kappa.get("max_kappa")),
        "kappa_total_rows": _safe_int(kappa.get("total_rows")),
        "kappa_skipped_rows": _safe_int(kappa.get("skipped_rows")),
    }
    for model_metrics in model_map.values():
        model_metrics.update(kappa_payload)
    return model_map


def build_detailed_rows(
    summary_wide_rows: List[Dict[str, str]],
    model_metric_map: Dict[str, Dict[str, Any]],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for row in summary_wide_rows:
        attack_run = row.get("attack_run", "")
        model = row.get("attack_group", "")
        attack = ""
        if isinstance(attack_run, str) and "/" in attack_run:
            _, attack = attack_run.split("/", 1)
        metrics = model_metric_map.get(model, {})
        out = dict(row)
        out["model"] = model
        out["attack"] = attack
        out["model_avg_asr"] = _as_float_text(_safe_float(metrics.get("model_avg_asr")))
        out["model_avg_frr"] = _as_float_text(_safe_float(metrics.get("model_avg_frr")))
        out["mu_asr"] = _as_float_text(_safe_float(metrics.get("mu_asr")))
        out["sigma_asr"] = _as_float_text(_safe_float(metrics.get("sigma_asr")))
        out["mds"] = _as_float_text(_safe_float(metrics.get("mds")))
        out["bias"] = _as_float_text(_safe_float(metrics.get("bias")))
        out["wsl"] = _as_float_text(_safe_float(metrics.get("wsl")))
        out["cm"] = _as_float_text(_safe_float(metrics.get("cm")))
        out["avg_kappa"] = _as_float_text(_safe_float(metrics.get("avg_kappa")))
        out["median_kappa"] = _as_float_text(_safe_float(metrics.get("median_kappa")))
        out["min_kappa"] = _as_float_text(_safe_float(metrics.get("min_kappa")))
        out["max_kappa"] = _as_float_text(_safe_float(metrics.get("max_kappa")))
        out["kappa_total_rows"] = _as_int_text(_safe_int(metrics.get("kappa_total_rows")))
        out["kappa_skipped_rows"] = _as_int_text(_safe_int(metrics.get("kappa_skipped_rows")))
        out["attacks_covered"] = _as_int_text(_safe_int(metrics.get("attacks_covered")))
        out["attack_types"] = _as_int_text(_safe_int(metrics.get("attack_types")))
        rows.append(out)
    return rows


def write_dynamic_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("")
        return
    fieldnames = list(rows[0].keys())
    for row in rows[1:]:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export all evaluation metrics into one CSV file.")
    parser.add_argument("--facts", default=DEFAULT_FACTS, help="Path to facts.json")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output CSV path")
    parser.add_argument(
        "--summary-wide",
        default=DEFAULT_SUMMARY_WIDE,
        help="Path to summary_wide.csv used for per-attack-run full metric export",
    )
    parser.add_argument(
        "--detailed-output",
        default=DEFAULT_DETAILED_OUTPUT,
        help="Output CSV path for per-attack-run full metrics",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.path.isfile(args.facts):
        raise SystemExit(f"facts file not found: {args.facts}")
    if not os.path.isfile(args.summary_wide):
        raise SystemExit(f"summary_wide file not found: {args.summary_wide}")

    facts = load_facts(args.facts)
    summary_wide_rows = load_csv_rows(args.summary_wide)
    kappa = facts.get("kappa_summary") if isinstance(facts.get("kappa_summary"), dict) else {}
    model_rows = build_model_rows(facts, kappa)
    attack_rows = build_attack_rows(facts, kappa)
    all_rows = model_rows + attack_rows
    write_csv(args.output, all_rows)
    model_metric_map = _build_model_metric_map(facts, kappa)
    detailed_rows = build_detailed_rows(summary_wide_rows, model_metric_map)
    write_dynamic_csv(args.detailed_output, detailed_rows)
    print(f"Wrote {args.output}")
    print(f"Wrote {args.detailed_output}")


if __name__ == "__main__":
    main()
