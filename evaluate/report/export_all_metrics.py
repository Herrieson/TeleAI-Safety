import argparse
import csv
import json
import os
from typing import Any, Dict, List, Optional


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DEFAULT_FACTS = os.path.join(PROJECT_ROOT, "evaluation_report", "facts.json")
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "evaluation_report", "all_metrics_summary.csv")


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export all evaluation metrics into one CSV file.")
    parser.add_argument("--facts", default=DEFAULT_FACTS, help="Path to facts.json")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output CSV path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.path.isfile(args.facts):
        raise SystemExit(f"facts file not found: {args.facts}")

    facts = load_facts(args.facts)
    kappa = facts.get("kappa_summary") if isinstance(facts.get("kappa_summary"), dict) else {}
    model_rows = build_model_rows(facts, kappa)
    attack_rows = build_attack_rows(facts, kappa)
    all_rows = model_rows + attack_rows
    write_csv(args.output, all_rows)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
