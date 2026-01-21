import argparse
import csv
import os
from typing import Dict, List, Optional, Set, Tuple


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DEFAULT_INPUT = os.path.join(PROJECT_ROOT, "evaluation_report", "asr", "summary_long.csv")
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_overview.md")
DEFAULT_MDS_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "mds")
DEFAULT_HEATMAP = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_heatmap.png")
DEFAULT_MODEL_BAR = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_models.png")
DEFAULT_ATTACK_BAR = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_attacks.png")


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


def normalize_attack_name(name: str) -> str:
    return name.replace("_", "")


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


def read_summary_long(path: str) -> Tuple[Dict[Tuple[str, str], Dict[str, object]], List[str]]:
    groups: Dict[Tuple[str, str], Dict[str, object]] = {}
    unparsed: List[str] = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            attack_run = row.get("attack_run", "").strip()
            parsed = parse_attack_run(attack_run)
            if not parsed:
                if attack_run:
                    unparsed.append(attack_run)
                continue
            model, attack = parsed
            key = (model, attack)
            group = groups.setdefault(
                key,
                {
                    "asr_vals": [],
                    "scorers": set(),
                    "total_samples": set(),
                    "skipped_samples": set(),
                },
            )

            asr_raw = row.get("asr", "")
            try:
                asr_val = float(asr_raw)
            except (TypeError, ValueError):
                continue
            group["asr_vals"].append(asr_val)

            scorer = row.get("scorer")
            if scorer:
                group["scorers"].add(scorer)

            total = row.get("total_samples")
            if total and total.isdigit():
                group["total_samples"].add(int(total))

            skipped = row.get("skipped_samples")
            if skipped and skipped.isdigit():
                group["skipped_samples"].add(int(skipped))

    return groups, unparsed


def format_group_rows(groups: Dict[Tuple[str, str], Dict[str, object]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for (model, attack), data in groups.items():
        asr_vals: List[float] = data["asr_vals"]
        if not asr_vals:
            continue
        avg_asr = sum(asr_vals) / len(asr_vals)
        scorers: Set[str] = data["scorers"]
        total_samples: Set[int] = data["total_samples"]

        if len(total_samples) == 1:
            total_str = str(next(iter(total_samples)))
        elif len(total_samples) > 1:
            total_str = "mixed"
        else:
            total_str = ""

        rows.append(
            {
                "model": model,
                "attack": attack,
                "avg_asr": f"{avg_asr:.4f}",
                "num_scorers": str(len(scorers)) if scorers else "",
                "total_samples": total_str,
            }
        )
    return sorted(rows, key=lambda r: (r["model"], r["attack"]))


def format_model_summary(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    model_vals: Dict[str, List[float]] = {}
    for row in rows:
        try:
            asr_val = float(row["avg_asr"])
        except (TypeError, ValueError):
            continue
        model_vals.setdefault(row["model"], []).append(asr_val)

    summary = []
    for model, vals in sorted(model_vals.items()):
        avg_asr = sum(vals) / len(vals)
        summary.append(
            {
                "model": model,
                "avg_asr": f"{avg_asr:.4f}",
                "attacks": str(len(vals)),
            }
        )
    return summary


def format_model_attack_matrix(rows: List[Dict[str, str]]) -> Tuple[List[str], List[Dict[str, str]]]:
    attacks = sorted({row["attack"] for row in rows})
    models = sorted({row["model"] for row in rows})
    matrix_map: Dict[Tuple[str, str], str] = {
        (row["model"], row["attack"]): row["avg_asr"] for row in rows
    }
    matrix_rows: List[Dict[str, str]] = []
    for model in models:
        row = {"model": model}
        for attack in attacks:
            row[attack] = matrix_map.get((model, attack), "")
        matrix_rows.append(row)
    return attacks, matrix_rows


def build_matrix(rows: List[Dict[str, str]]) -> Tuple[List[str], List[str], List[List[float]]]:
    models = sorted({row["model"] for row in rows})
    attacks = sorted({row["attack"] for row in rows})
    model_index = {model: idx for idx, model in enumerate(models)}
    attack_index = {attack: idx for idx, attack in enumerate(attacks)}
    matrix = [[float("nan") for _ in attacks] for _ in models]
    for row in rows:
        try:
            val = float(row["avg_asr"])
        except (TypeError, ValueError):
            continue
        i = model_index[row["model"]]
        j = attack_index[row["attack"]]
        matrix[i][j] = val
    return models, attacks, matrix


def compute_attack_summary(rows: List[Dict[str, str]]) -> List[Tuple[str, float]]:
    attack_vals: Dict[str, List[float]] = {}
    for row in rows:
        try:
            asr_val = float(row["avg_asr"])
        except (TypeError, ValueError):
            continue
        attack_vals.setdefault(row["attack"], []).append(asr_val)
    summary = []
    for attack, vals in attack_vals.items():
        if vals:
            summary.append((attack, sum(vals) / len(vals)))
    return summary


def generate_plots(
    rows: List[Dict[str, str]],
    heatmap_path: str,
    model_bar_path: str,
    attack_bar_path: str,
) -> List[str]:
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = [
            "Arial",
            "DejaVu Sans",
            "Liberation Sans",
            "sans-serif",
        ]
    except ImportError:
        print("matplotlib not available; skipping plots.")
        return []

    created: List[str] = []
    models, attacks, matrix = build_matrix(rows)

    def setup_axis(ax, title: str, ylabel: str) -> None:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=20, loc="left")
        ax.set_ylabel(ylabel, fontsize=11, labelpad=10)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")
        ax.yaxis.grid(True, linestyle="--", which="major", color="grey", alpha=0.2)
        ax.set_axisbelow(True)

    if models and attacks:
        data = np.array(matrix, dtype=float)
        fig_w = max(8.0, len(attacks) * 1.2)
        fig_h = max(6.0, len(models) * 0.8)
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        vmin = 0.0
        vmax = float(np.nanmax(data)) if np.isfinite(np.nanmax(data)) else 1.0
        im = ax.imshow(data, aspect="auto", cmap="RdYlBu_r", vmin=vmin, vmax=vmax)
        ax.set_xticks(np.arange(len(attacks) + 1) - 0.5, minor=True)
        ax.set_yticks(np.arange(len(models) + 1) - 0.5, minor=True)
        ax.grid(which="minor", color="w", linestyle="-", linewidth=3)
        ax.tick_params(which="minor", bottom=False, left=False)
        ax.set_xticks(range(len(attacks)))
        ax.set_xticklabels(attacks, rotation=45, ha="right", fontsize=10)
        ax.set_yticks(range(len(models)))
        ax.set_yticklabels(models, fontsize=10)
        for spine in ax.spines.values():
            spine.set_visible(False)
        for i in range(len(models)):
            for j in range(len(attacks)):
                val = data[i, j]
                if np.isnan(val):
                    continue
                text_color = "white" if (val < 0.3 or val > 0.7) else "black"
                ax.text(
                    j,
                    i,
                    f"{val:.2f}",
                    ha="center",
                    va="center",
                    fontsize=9,
                    color=text_color,
                    fontweight="bold",
                )
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.set_ylabel("Avg ASR", rotation=-90, va="bottom", fontsize=10)
        cbar.outline.set_visible(False)
        ax.set_title("Model ASR by Attack Matrix", fontsize=14, fontweight="bold", pad=20)
        fig.tight_layout()
        os.makedirs(os.path.dirname(heatmap_path), exist_ok=True)
        fig.savefig(heatmap_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        created.append(heatmap_path)

    model_summary = format_model_summary(rows)
    model_vals = []
    for row in model_summary:
        try:
            model_vals.append((row["model"], float(row["avg_asr"])))
        except (TypeError, ValueError):
            continue
    model_vals.sort(key=lambda item: item[1])
    if model_vals:
        labels = [item[0] for item in model_vals]
        values = [item[1] for item in model_vals]
        fig_w = max(8.0, len(labels) * 1.0)
        fig, ax = plt.subplots(figsize=(fig_w, 5.0))
        setup_axis(ax, "Model Average ASR (Ascending)", "Avg ASR")
        colors = plt.cm.viridis(np.linspace(0.3, 0.8, len(values)))
        bars = ax.bar(labels, values, color=colors, alpha=0.9, width=0.6)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=10)
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + 0.01,
                f"{height:.2f}",
                ha="center",
                va="bottom",
                fontsize=9,
                color="#555555",
            )
        fig.tight_layout()
        os.makedirs(os.path.dirname(model_bar_path), exist_ok=True)
        fig.savefig(model_bar_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        created.append(model_bar_path)

    attack_summary = compute_attack_summary(rows)
    attack_summary.sort(key=lambda item: item[1], reverse=True)
    if attack_summary:
        labels = [item[0] for item in attack_summary]
        values = [item[1] for item in attack_summary]
        fig_w = max(8.0, len(labels) * 1.0)
        fig, ax = plt.subplots(figsize=(fig_w, 5.0))
        setup_axis(ax, "Attack Effectiveness (Avg ASR Descending)", "Avg ASR")
        colors = plt.cm.magma(np.linspace(0.3, 0.8, len(values)))
        bars = ax.bar(labels, values, color=colors, alpha=0.9, width=0.6)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=10)
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + 0.01,
                f"{height:.2f}",
                ha="center",
                va="bottom",
                fontsize=9,
                color="#555555",
            )
        fig.tight_layout()
        os.makedirs(os.path.dirname(attack_bar_path), exist_ok=True)
        fig.savefig(attack_bar_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        created.append(attack_bar_path)

    return created


def write_markdown(
    output_path: str,
    model_summary: List[Dict[str, str]],
    attack_list: List[str],
    matrix_rows: List[Dict[str, str]],
    mds_rows: List[Dict[str, str]],
    plot_paths: List[str],
    unparsed: List[str],
    input_path: str,
    mds_dir: str,
) -> None:
    lines = [
        "# Evaluation Overview",
        "",
        f"Source: {os.path.relpath(input_path, PROJECT_ROOT)}",
        "",
    ]

    if attack_list and matrix_rows:
        lines.extend(
            [
                "",
                "## Model ASR by Attack",
                "",
                "| Model | " + " | ".join(attack_list) + " |",
                "| --- | " + " | ".join(["---"] * len(attack_list)) + " |",
            ]
        )
        for row in matrix_rows:
            values = [row.get(attack, "") for attack in attack_list]
            lines.append("| {model} | ".format(model=row["model"]) + " | ".join(values) + " |")

        heatmap_path = next(
            (p for p in plot_paths if os.path.basename(p) == os.path.basename(DEFAULT_HEATMAP)),
            None,
        )
        if heatmap_path:
            rel_heatmap = os.path.relpath(heatmap_path, os.path.dirname(output_path))
            lines.extend(["", f"![Model ASR by Attack Heatmap]({rel_heatmap})"])

    if model_summary:
        lines.extend(
            [
                "",
                "## Model Summary (Average ASR across attacks)",
                "",
                "| Model | Avg ASR | Attacks Covered |",
                "| --- | --- | --- |",
            ]
        )
        for row in model_summary:
            lines.append(
                "| {model} | {avg_asr} | {attacks} |".format(
                    **row
                )
            )

        model_bar_path = next(
            (p for p in plot_paths if os.path.basename(p) == os.path.basename(DEFAULT_MODEL_BAR)),
            None,
        )
        if model_bar_path:
            rel_model_bar = os.path.relpath(model_bar_path, os.path.dirname(output_path))
            lines.extend(["", f"![Model Average ASR Bar]({rel_model_bar})"])

        attack_bar_path = next(
            (p for p in plot_paths if os.path.basename(p) == os.path.basename(DEFAULT_ATTACK_BAR)),
            None,
        )
        if attack_bar_path:
            rel_attack_bar = os.path.relpath(attack_bar_path, os.path.dirname(output_path))
            lines.extend(["", f"![Attack Average ASR Bar]({rel_attack_bar})"])

    if mds_rows:
        lines.extend(
            [
                "",
                "## Model MDS",
                "",
                f"Source: {os.path.relpath(mds_dir, PROJECT_ROOT)}",
                "",
                "| Model | MDS | mu_ASR | sigma_ASR | Attack types | Report |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in mds_rows:
            lines.append(
                "| {model} | {mds} | {mu_asr} | {sigma_asr} | {attack_types} | {report} |".format(
                    **row
                )
            )

    if unparsed:
        lines.extend(["", "## Unparsed attack runs", ""])
        for attack_run in sorted(set(unparsed)):
            lines.append(f"- {attack_run}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def read_mds_reports(mds_dir: str) -> List[Dict[str, str]]:
    if not os.path.isdir(mds_dir):
        return []
    rows: List[Dict[str, str]] = []
    for fname in sorted(os.listdir(mds_dir)):
        if not fname.endswith(".txt"):
            continue
        path = os.path.join(mds_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f]

        current = None
        for line in lines:
            if line.startswith("## "):
                if current and current.get("mds"):
                    rows.append(current)
                model = line[3:].strip()
                current = {
                    "model": model,
                    "attack_types": "",
                    "mu_asr": "",
                    "sigma_asr": "",
                    "mds": "",
                    "report": os.path.relpath(path, PROJECT_ROOT),
                }
                continue
            if not current:
                continue
            if line.lower().startswith("attack types:"):
                current["attack_types"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("mu_asr:"):
                current["mu_asr"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("sigma_asr:"):
                current["sigma_asr"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("mds:"):
                current["mds"] = line.split(":", 1)[1].strip()

        if current and current.get("mds"):
            rows.append(current)

    return sorted(rows, key=lambda r: r["model"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize evaluation_report/asr/summary_long.csv into a Markdown overview."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to summary_long.csv")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output Markdown path")
    parser.add_argument("--mds-dir", default=DEFAULT_MDS_DIR, help="Directory with MDS reports")
    parser.add_argument("--heatmap", default=DEFAULT_HEATMAP, help="Heatmap image path")
    parser.add_argument("--model-bar", default=DEFAULT_MODEL_BAR, help="Model bar chart path")
    parser.add_argument("--attack-bar", default=DEFAULT_ATTACK_BAR, help="Attack bar chart path")
    parser.add_argument("--no-plots", action="store_true", help="Disable plot generation")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        raise SystemExit(f"summary_long.csv not found: {input_path}")

    groups, unparsed = read_summary_long(input_path)
    rows = format_group_rows(groups)
    if not rows:
        raise SystemExit("No valid rows found in summary_long.csv")

    model_summary = format_model_summary(rows)
    attack_list, matrix_rows = format_model_attack_matrix(rows)
    mds_dir = os.path.abspath(args.mds_dir)
    mds_rows = read_mds_reports(mds_dir)
    plot_paths: List[str] = []
    if not args.no_plots:
        plot_paths = generate_plots(
            rows,
            os.path.abspath(args.heatmap),
            os.path.abspath(args.model_bar),
            os.path.abspath(args.attack_bar),
        )
    write_markdown(
        args.output,
        model_summary,
        attack_list,
        matrix_rows,
        mds_rows,
        plot_paths,
        unparsed,
        input_path,
        mds_dir,
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
