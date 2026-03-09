import csv
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
REPORT_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "asr")
FRR_REPORT_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "frr")
# 评测输入数据通常放在项目根的 results/ 下，也可能在 ../data/attack_results/
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
ALT_RESULTS_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, os.pardir, "data", "attack_results"))
ASR_LABEL_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "asr_labels")
FRR_LABEL_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "frr_labels")
LONG_CSV = os.path.join(REPORT_DIR, "summary_long.csv")
WIDE_CSV = os.path.join(REPORT_DIR, "summary_wide.csv")
MARKDOWN = os.path.join(REPORT_DIR, "summary.md")


def parse_report(path: str) -> Optional[Dict[str, str]]:
    """Parse a single eval_summary_report.txt file."""
    patterns = {
        "scorer": r"^Scorer:\s*(.+)$",
        "input_file": r"^Input file:\s*(.+)$",
        "total": r"^Total samples:\s*(\d+)$",
        "skipped": r"^Skipped samples:\s*(\d+)$",
        "success": r"^Attack success samples:\s*(\d+)$",
        "asr": r"^Attack Success Rate \(ASR\):\s*([0-9.]+)",
        "avg_asr": r"^Average scorer ASR:\s*([0-9.eE+-]+)",
        "safe_total": r"^Safe samples \(label=0\):\s*(\d+)$",
        "frr": r"^False Refusal Rate \(FRR\):\s*([0-9.]+)",
    }
    values: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            for key, pat in patterns.items():
                if key in values:
                    continue
                m = re.match(pat, line)
                if m:
                    values[key] = m.group(1)
    required = ["scorer", "input_file", "total", "success", "asr"]
    if not all(k in values for k in required):
        return None
    # Some reports omit skipped; default to 0
    values.setdefault("skipped", "0")
    values.setdefault("avg_asr", "")
    values.setdefault("safe_total", "")
    values.setdefault("frr", "")
    values["report_path"] = path
    return values


def derive_attack_run(input_file: str) -> Tuple[str, str]:
    """
    Derive attack run identifiers.
    Returns (attack_run, attack_group).
    attack_run: path relative to results/ without extension when possible.
    attack_group: first path segment for coarse grouping.
    """
    abs_input = os.path.abspath(input_file)
    candidate_roots = [os.path.abspath(RESULTS_DIR), ALT_RESULTS_DIR]
    rel = None
    for root in candidate_roots:
        if abs_input.startswith(root + os.sep):
            rel = os.path.relpath(abs_input, root)
            break
    # ASR/FRR 报告通常以 *_labels/*.jsonl 作为输入，优先还原成 model/attack。
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
        rel = os.path.basename(abs_input)
    if rel.endswith(".jsonl"):
        rel_no_ext = rel[:-6]
    else:
        rel_no_ext = os.path.splitext(rel)[0]
    parts = rel_no_ext.split(os.sep)
    attack_group = parts[0] if parts else rel_no_ext
    return rel_no_ext, attack_group


def collect_frr_by_run() -> Dict[str, Dict[str, str]]:
    """
    Collect FRR report values keyed by attack_run.
    Returns mapping:
      attack_run -> {"frr": "...", "safe_total": "...", "skipped": "..."}
    """
    if not os.path.isdir(FRR_REPORT_DIR):
        return {}
    patterns = {
        "input_file": r"^Input file:\s*(.+)$",
        "safe_total": r"^Total safe samples:\s*(\d+)$",
        "skipped": r"^Skipped samples:\s*(\d+)$",
        "frr": r"^False Refusal Rate \(FRR\):\s*([0-9.]+)$",
    }
    values_by_run: Dict[str, Dict[str, str]] = {}
    for root, _, files in os.walk(FRR_REPORT_DIR):
        for fname in files:
            if not fname.endswith(".txt"):
                continue
            path = os.path.join(root, fname)
            values: Dict[str, str] = {}
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    for key, pat in patterns.items():
                        if key in values:
                            continue
                        m = re.match(pat, line)
                        if m:
                            values[key] = m.group(1)
            if "input_file" not in values or "frr" not in values:
                continue
            attack_run, _ = derive_attack_run(values["input_file"])
            values_by_run[attack_run] = values
    return values_by_run


def collect_reports() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for root, _, files in os.walk(REPORT_DIR):
        for fname in files:
            if not fname.endswith(".txt"):
                continue
            path = os.path.join(root, fname)
            parsed = parse_report(path)
            if not parsed:
                continue
            attack_run, attack_group = derive_attack_run(parsed["input_file"])
            row = {
                "attack_run": attack_run,
                "attack_group": attack_group,
                "scorer": parsed["scorer"],
                "total_samples": parsed["total"],
                "skipped_samples": parsed["skipped"],
                "attack_success_samples": parsed["success"],
                "asr": parsed["asr"],
                "safe_samples": parsed.get("safe_total", ""),
                "frr": parsed.get("frr", ""),
                "avg_asr": parsed.get("avg_asr", ""),
                "input_file": parsed["input_file"],
                "report_path": os.path.relpath(path, REPORT_DIR),
            }
            rows.append(row)
    return rows


def compute_run_avg_asr(rows: List[Dict[str, str]]) -> Dict[str, str]:
    """Compute average ASR across different scorers for each attack run."""
    asr_by_run: Dict[str, List[float]] = defaultdict(list)
    for row in rows:
        try:
            asr_val = float(row["asr"])
        except (ValueError, TypeError):
            continue
        asr_by_run[row["attack_run"]].append(asr_val)
    return {run: f"{(sum(vals) / len(vals)):.4f}" for run, vals in asr_by_run.items() if vals}


def write_long_csv(rows: List[Dict[str, str]], run_avg_asr: Dict[str, str]) -> None:
    fieldnames = [
        "attack_run",
        "attack_group",
        "scorer",
        "total_samples",
        "skipped_samples",
        "attack_success_samples",
        "asr",
        "safe_samples",
        "frr",
        "avg_asr_all_scorers",
        "input_file",
        "report_path",
    ]
    with open(LONG_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (r["attack_run"], r["scorer"])):
            row_out = dict(row)
            row_out.pop("avg_asr", None)  # remove per-scorer avg_asr to match fieldnames
            row_out["avg_asr_all_scorers"] = run_avg_asr.get(row["attack_run"], "")
            writer.writerow(row_out)


def write_wide_csv(rows: List[Dict[str, str]], run_avg_asr: Dict[str, str]) -> None:
    # Pivot attack_run -> scorer -> asr
    pivot: Dict[str, Dict[str, str]] = defaultdict(dict)
    pivot_frr: Dict[str, Dict[str, str]] = defaultdict(dict)
    attack_groups: Dict[str, str] = {}
    scorers = set()
    for row in rows:
        run = row["attack_run"]
        pivot[run][row["scorer"]] = row["asr"]
        pivot_frr[run][row["scorer"]] = row.get("frr", "")
        attack_groups[run] = row["attack_group"]
        scorers.add(row["scorer"])
    scorer_list = sorted(scorers)
    fieldnames = (
        ["attack_run", "attack_group", "ASR_avg_all_scorers"]
        + [f"ASR_{s}" for s in scorer_list]
        + [f"FRR_{s}" for s in scorer_list]
    )
    with open(WIDE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for run in sorted(pivot.keys()):
            row = {
                "attack_run": run,
                "attack_group": attack_groups.get(run, ""),
                "ASR_avg_all_scorers": run_avg_asr.get(run, ""),
            }
            for s in scorer_list:
                row[f"ASR_{s}"] = pivot[run].get(s, "")
                row[f"FRR_{s}"] = pivot_frr[run].get(s, "")
            writer.writerow(row)


def write_markdown(rows: List[Dict[str, str]], run_avg_asr: Dict[str, str]) -> None:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["attack_run"]].append(row)
    lines: List[str] = ["# Evaluation Summary", ""]
    for attack_run in sorted(grouped.keys()):
        lines.append(f"## {attack_run}")
        lines.append("")
        lines.append(f"Average ASR across scorers: {run_avg_asr.get(attack_run, '')}")
        lines.append("")
        lines.append("| Scorer | ASR | FRR | Total | Success | Skipped | Safe | Report |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for row in sorted(grouped[attack_run], key=lambda r: r["scorer"]):
            lines.append(
                f"| {row['scorer']} | {row['asr']} | {row.get('frr', '')} | {row['total_samples']} | "
                f"{row['attack_success_samples']} | {row['skipped_samples']} | {row.get('safe_samples', '')} | {row['report_path']} |"
            )
        lines.append("")
    with open(MARKDOWN, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    if not os.path.isdir(REPORT_DIR):
        raise SystemExit(f"Report directory not found: {REPORT_DIR}")
    rows = collect_reports()
    if not rows:
        raise SystemExit("No valid report files found.")
    frr_by_run = collect_frr_by_run()
    if frr_by_run:
        for row in rows:
            frr_values = frr_by_run.get(row["attack_run"])
            if not frr_values:
                continue
            if not row.get("frr"):
                row["frr"] = frr_values.get("frr", "")
            if not row.get("safe_samples"):
                row["safe_samples"] = frr_values.get("safe_total", "")
            if not row.get("skipped_samples"):
                row["skipped_samples"] = frr_values.get("skipped", "")
    run_avg_asr = compute_run_avg_asr(rows)
    os.makedirs(REPORT_DIR, exist_ok=True)
    write_long_csv(rows, run_avg_asr)
    write_wide_csv(rows, run_avg_asr)
    write_markdown(rows, run_avg_asr)
    print(f"Wrote {LONG_CSV}")
    print(f"Wrote {WIDE_CSV}")
    print(f"Wrote {MARKDOWN}")


if __name__ == "__main__":
    main()
