import argparse
import csv
import os
import re
from typing import Dict, List, Optional, Set, Tuple


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
ALT_RESULTS_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, os.pardir, "data", "attack_results"))
DEFAULT_INPUT = os.path.join(PROJECT_ROOT, "evaluation_report", "asr", "summary_long.csv")
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_overview.md")
DEFAULT_MDS_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "mds")
DEFAULT_HEATMAP = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_heatmap.png")
DEFAULT_FRR_HEATMAP = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_heatmap_frr.png")
DEFAULT_MODEL_BAR = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_models.png")
DEFAULT_ATTACK_BAR = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_attacks.png")
DEFAULT_BIAS_BAR = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_bias.png")
DEFAULT_WSL_BAR = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_wsl.png")
DEFAULT_CM_BAR = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_cm.png")
DEFAULT_MDS_BAR = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_mds.png")
DEFAULT_FRR_MODEL_BAR = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_bar_models_frr.png")
DEFAULT_FRR_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "frr")
DEFAULT_RADAR_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "summary_radar")
DEFAULT_RADAR_FILE = "summary_radar_all.png"
DEFAULT_TIERED_DASHBOARD = os.path.join(
    PROJECT_ROOT, "evaluation_report", "summary_tiered_dashboard.png"
)
DEFAULT_EXEC_SUMMARY = os.path.join(
    PROJECT_ROOT, "evaluation_report", "summary_exec_overview.png"
)
DEFAULT_BIAS_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "bias")
DEFAULT_WSL_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "wsl")
DEFAULT_CM_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "cm")
DEFAULT_KAPPA_CSV = os.path.join(PROJECT_ROOT, "evaluation_report", "kappa", "kappa_report_kappa.csv")


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


def derive_attack_run(input_file: str) -> Tuple[str, str]:
    abs_input = os.path.abspath(input_file)
    candidate_roots = [
        os.path.abspath(RESULTS_DIR),
        ALT_RESULTS_DIR,
        os.path.join(PROJECT_ROOT, "evaluation_report", "frr_labels"),
    ]
    rel = None
    for root in candidate_roots:
        if abs_input.startswith(root + os.sep):
            rel = os.path.relpath(abs_input, root)
            break
    if rel is None:
        rel = os.path.basename(abs_input)
    if rel.endswith(".jsonl"):
        rel_no_ext = rel[:-6]
    else:
        rel_no_ext = os.path.splitext(rel)[0]
    parts = rel_no_ext.split(os.sep)
    # Canonicalize to model/attack when possible so FRR report keys align with
    # summary_long.csv attack_run values.
    if len(parts) >= 2:
        canonical = os.path.join(parts[0], parts[1])
        return canonical, parts[0]
    attack_group = parts[0] if parts else rel_no_ext
    return rel_no_ext, attack_group


def read_summary_long(
    path: str,
    frr_by_run: Optional[Dict[str, float]] = None,
) -> Tuple[Dict[Tuple[str, str], Dict[str, object]], List[str]]:
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
                    "frr_vals": [],
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

            frr_val = None
            frr_raw = row.get("frr", "")
            if frr_raw:
                try:
                    frr_val = float(frr_raw)
                except (TypeError, ValueError):
                    frr_val = None
            elif frr_by_run:
                frr_val = frr_by_run.get(attack_run)
            if frr_val is not None:
                group["frr_vals"].append(frr_val)

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


def read_frr_reports(frr_dir: str) -> Dict[str, float]:
    if not os.path.isdir(frr_dir):
        return {}

    def parse_report(path: str) -> Optional[Tuple[str, float]]:
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
        if input_file and frr_val is not None:
            attack_run, _ = derive_attack_run(input_file)
            return attack_run, frr_val
        return None

    frr_by_run: Dict[str, float] = {}
    for root, _, files in os.walk(frr_dir):
        for fname in files:
            if not fname.endswith(".txt"):
                continue
            path = os.path.join(root, fname)
            parsed = parse_report(path)
            if not parsed:
                continue
            attack_run, frr_val = parsed
            frr_by_run[attack_run] = frr_val
    return frr_by_run


def format_group_rows(groups: Dict[Tuple[str, str], Dict[str, object]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for (model, attack), data in groups.items():
        asr_vals: List[float] = data["asr_vals"]
        frr_vals: List[float] = data["frr_vals"]
        if not asr_vals:
            continue
        avg_asr = sum(asr_vals) / len(asr_vals)
        avg_frr = sum(frr_vals) / len(frr_vals) if frr_vals else None
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
                "avg_frr": f"{avg_frr:.4f}" if avg_frr is not None else "",
                "num_scorers": str(len(scorers)) if scorers else "",
                "total_samples": total_str,
            }
        )
    return sorted(rows, key=lambda r: (r["model"], r["attack"]))


def format_model_summary(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    model_asr_vals: Dict[str, List[float]] = {}
    model_frr_vals: Dict[str, List[float]] = {}
    for row in rows:
        try:
            asr_val = float(row["avg_asr"])
        except (TypeError, ValueError):
            continue
        model_asr_vals.setdefault(row["model"], []).append(asr_val)
        try:
            frr_val = float(row.get("avg_frr", ""))
        except (TypeError, ValueError):
            frr_val = None
        if frr_val is not None:
            model_frr_vals.setdefault(row["model"], []).append(frr_val)

    summary = []
    for model, vals in sorted(model_asr_vals.items()):
        avg_asr = sum(vals) / len(vals)
        frr_vals = model_frr_vals.get(model, [])
        avg_frr = sum(frr_vals) / len(frr_vals) if frr_vals else None
        summary.append(
            {
                "model": model,
                "avg_asr": f"{avg_asr:.4f}",
                "avg_frr": f"{avg_frr:.4f}" if avg_frr is not None else "",
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


def build_matrix(
    rows: List[Dict[str, str]],
    metric_key: str = "avg_asr",
) -> Tuple[List[str], List[str], List[List[float]]]:
    models = sorted({row["model"] for row in rows})
    attacks = sorted({row["attack"] for row in rows})
    model_index = {model: idx for idx, model in enumerate(models)}
    attack_index = {attack: idx for idx, attack in enumerate(attacks)}
    matrix = [[float("nan") for _ in attacks] for _ in models]
    for row in rows:
        try:
            val = float(row[metric_key])
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
    frr_heatmap_path: str,
    model_bar_path: str,
    attack_bar_path: str,
    frr_model_bar_path: str,
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

    def setup_axis(ax, title: str, ylabel: str) -> None:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=20, loc="left")
        ax.set_ylabel(ylabel, fontsize=11, labelpad=10)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")
        ax.yaxis.grid(True, linestyle="--", which="major", color="grey", alpha=0.2)
        ax.set_axisbelow(True)

    def render_heatmap(
        models: List[str],
        attacks: List[str],
        matrix: List[List[float]],
        *,
        title: str,
        cbar_label: str,
        output_path: str,
    ) -> Optional[str]:
        if not models or not attacks:
            return None
        data = np.array(matrix, dtype=float)
        if not np.isfinite(data).any():
            return None
        fig_w = max(8.0, len(attacks) * 1.2)
        fig_h = max(6.0, len(models) * 0.8)
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        vmin = 0.0
        vmax = float(np.nanmax(data)) if np.isfinite(np.nanmax(data)) else 1.0
        if vmax <= 0.0:
            vmax = 1.0
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
        cbar.ax.set_ylabel(cbar_label, rotation=-90, va="bottom", fontsize=10)
        cbar.outline.set_visible(False)
        ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
        fig.tight_layout()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return output_path

    asr_models, asr_attacks, asr_matrix = build_matrix(rows, metric_key="avg_asr")
    asr_heatmap = render_heatmap(
        asr_models,
        asr_attacks,
        asr_matrix,
        title="Model ASR by Attack Matrix",
        cbar_label="Avg ASR",
        output_path=heatmap_path,
    )
    if asr_heatmap:
        created.append(asr_heatmap)

    frr_models, frr_attacks, frr_matrix = build_matrix(rows, metric_key="avg_frr")
    frr_heatmap = render_heatmap(
        frr_models,
        frr_attacks,
        frr_matrix,
        title="Model FRR by Attack Matrix",
        cbar_label="Avg FRR",
        output_path=frr_heatmap_path,
    )
    if frr_heatmap:
        created.append(frr_heatmap)

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

    frr_model_vals = []
    for row in model_summary:
        try:
            frr_model_vals.append((row["model"], float(row["avg_frr"])))
        except (TypeError, ValueError):
            continue
    frr_model_vals.sort(key=lambda item: item[1])
    if frr_model_vals:
        labels = [item[0] for item in frr_model_vals]
        values = [item[1] for item in frr_model_vals]
        fig_w = max(8.0, len(labels) * 1.0)
        fig, ax = plt.subplots(figsize=(fig_w, 5.0))
        setup_axis(ax, "Model Average FRR (Ascending)", "Avg FRR")
        colors = plt.cm.cividis(np.linspace(0.3, 0.8, len(values)))
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
        os.makedirs(os.path.dirname(frr_model_bar_path), exist_ok=True)
        fig.savefig(frr_model_bar_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        created.append(frr_model_bar_path)

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


def generate_single_metric_bar(
    labels: List[str],
    values: List[float],
    title: str,
    cmap_name: str,
    output_path: str,
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
        print("matplotlib not available; skipping metric chart.")
        return []

    if not labels or not values:
        return []

    # Sort each metric chart in ascending order so bars go left->right from small to large.
    ordered = sorted(zip(labels, values), key=lambda x: x[1])
    labels = [x[0] for x in ordered]
    values = [x[1] for x in ordered]

    fig_w = max(8.0, len(labels) * 1.0)
    fig, ax = plt.subplots(1, 1, figsize=(fig_w, 5.0))
    x = np.arange(len(labels))
    cmap = plt.get_cmap(cmap_name)
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        colors = [cmap(0.6) for _ in values]
    else:
        colors = [cmap(0.3 + 0.5 * ((v - min_v) / (max_v - min_v))) for v in values]
    bars = ax.bar(x, values, width=0.6, color=colors, alpha=0.95)
    ax.set_title(title, fontsize=14, fontweight="bold", loc="left", pad=14)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.yaxis.grid(True, linestyle="--", which="major", color="grey", alpha=0.2)
    ax.set_axisbelow(True)
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height + (0.01 if height >= 0 else -0.01),
            f"{height:.2f}",
            ha="center",
            va="bottom" if height >= 0 else "top",
            fontsize=8,
            color="#555555",
        )
    ax.set_ylabel("Metric Value", fontsize=10, labelpad=6)

    fig.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return [output_path]


def generate_metric_charts_from_summary(
    metric_summary: List[Dict[str, str]],
    bias_output_path: str,
    wsl_output_path: str,
    cm_output_path: str,
) -> List[str]:
    labels: List[str] = []
    bias_vals: List[float] = []
    wsl_vals: List[float] = []
    cm_vals: List[float] = []
    for row in metric_summary:
        try:
            bias_vals.append(float(row["bias"]))
            wsl_vals.append(float(row["wsl"]))
            cm_vals.append(float(row["cm"]))
        except (TypeError, ValueError):
            continue
        labels.append(row["model"])

    if not labels:
        return []

    created: List[str] = []
    created.extend(
        generate_single_metric_bar(
            labels=labels,
            values=bias_vals,
            title="Model Bias (Avg across attacks)",
            cmap_name="Blues",
            output_path=bias_output_path,
        )
    )
    created.extend(
        generate_single_metric_bar(
            labels=labels,
            values=wsl_vals,
            title="Model WSL (Avg across attacks)",
            cmap_name="Oranges",
            output_path=wsl_output_path,
        )
    )
    created.extend(
        generate_single_metric_bar(
            labels=labels,
            values=cm_vals,
            title="Model CM (Avg across attacks)",
            cmap_name="Greens",
            output_path=cm_output_path,
        )
    )
    return created


def generate_mds_bar(mds_rows: List[Dict[str, str]], output_path: str) -> List[str]:
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
        print("matplotlib not available; skipping MDS bar plot.")
        return []

    values = []
    for row in mds_rows:
        try:
            values.append((row["model"], float(row["mds"])))
        except (TypeError, ValueError):
            continue

    if not values:
        return []

    values.sort(key=lambda item: item[1])
    labels = [item[0] for item in values]
    mds_vals = [item[1] for item in values]
    fig_w = max(8.0, len(labels) * 1.0)
    fig, ax = plt.subplots(figsize=(fig_w, 5.0))
    ax.set_ylabel("MDS", fontsize=11, labelpad=10)
    ax.set_title("Model MDS (Ascending)", fontsize=14, fontweight="bold", pad=20, loc="left")
    colors = plt.cm.viridis(np.linspace(0.3, 0.8, len(mds_vals)))
    bars = ax.bar(labels, mds_vals, color=colors, alpha=0.9, width=0.6)
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
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.yaxis.grid(True, linestyle="--", which="major", color="grey", alpha=0.2)
    ax.set_axisbelow(True)
    fig.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return [output_path]


def read_kappa_by_model(path: str) -> Dict[str, List[float]]:
    if not os.path.isfile(path):
        return {}
    values: Dict[str, List[float]] = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            attack_run = (row.get("attack_run") or "").strip()
            if not attack_run or attack_run == "__summary__":
                continue
            parsed = parse_attack_run(attack_run)
            if not parsed:
                continue
            model, _ = parsed
            kappa_raw = (row.get("kappa") or "").strip()
            if not kappa_raw:
                continue
            try:
                kappa_val = float(kappa_raw)
            except ValueError:
                continue
            values.setdefault(model, []).append(kappa_val)
    return values


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return cleaned or "model"


def generate_radar_plots(
    model_asr: Dict[str, float],
    model_frr: Dict[str, float],
    model_mds: Dict[str, float],
    model_bias: Dict[str, float],
    model_wsl: Dict[str, float],
    model_cm: Dict[str, float],
    output_dir: str,
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
        print("matplotlib not available; skipping radar plots.")
        return []

    metrics = [
        ("ASR", model_asr, False),
        ("FRR", model_frr, False),
        ("MDS", model_mds, True),
        ("Bias", model_bias, False),
        ("WSL", model_wsl, True),
        ("CM", model_cm, True),
    ]

    models = sorted(set.intersection(*[set(values) for _, values, _ in metrics]))
    if not models:
        return []

    normalized_data: Dict[str, List[float]] = {model: [] for model in models}
    for _, values, higher_is_better in metrics:
        metric_vals = [values[model] for model in models]
        min_val = min(metric_vals)
        max_val = max(metric_vals)
        range_val = max_val - min_val
        if range_val == 0:
            norm_vals = [1.0] * len(metric_vals)
        else:
            norm_vals = [(val - min_val) / range_val for val in metric_vals]
        if not higher_is_better:
            norm_vals = [1.0 - val for val in norm_vals]
        for idx, model in enumerate(models):
            normalized_data[model].append(norm_vals[idx])

    labels = [label for label, _, _ in metrics]
    num_axes = len(labels)
    angles = np.linspace(0, 2 * np.pi, num_axes, endpoint=False).tolist()
    angles += angles[:1]

    os.makedirs(output_dir, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9.0, 8.0), subplot_kw={"polar": True})
    fig.patch.set_facecolor("#fafafa")
    ax.set_facecolor("#fafafa")
    ax.spines["polar"].set_color("#e0e0e0")
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0.0, 1.05)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11, fontweight="bold", color="#333333")
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["", "", "", ""], fontsize=8, color="#888888")
    ax.yaxis.grid(True, color="#cccccc", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.xaxis.grid(True, color="#cccccc", linestyle="-", linewidth=0.8, alpha=0.5)

    try:
        import seaborn as sns

        palette = sns.color_palette("deep", len(models))
    except ImportError:
        palette = plt.cm.tab10(np.linspace(0, 1, len(models)))

    scored_models = sorted(
        models,
        key=lambda model: sum(normalized_data[model]),
        reverse=True,
    )

    for idx, model in enumerate(scored_models):
        values = normalized_data[model] + normalized_data[model][:1]
        color = palette[idx]
        ax.plot(
            angles,
            values,
            color=color,
            linewidth=2,
            marker="o",
            markersize=4,
            linestyle="solid",
            alpha=0.9,
            label=model,
        )
        ax.fill(angles, values, color=color, alpha=0.15)

    ax.set_title(
        "Model Safety & Capability Radar (Normalized)\nOutward = Better Performance",
        fontsize=13,
        fontweight="bold",
        pad=18,
        color="#222222",
    )
    ax.legend(
        loc="upper right",
        bbox_to_anchor=(1.3, 1.1),
        frameon=True,
        edgecolor="#cccccc",
        fontsize=8,
        title="Models (Sorted by Score)",
        title_fontsize=9,
    )
    inverted_labels = [label for label, _, higher_is_better in metrics if not higher_is_better]
    if inverted_labels:
        fig.text(
            0.5,
            0.02,
            "Note: lower-is-better metrics are inverted: " + ", ".join(inverted_labels),
            ha="center",
            fontsize=8,
            color="#666666",
            style="italic",
        )
    fig.tight_layout()

    path = os.path.join(output_dir, DEFAULT_RADAR_FILE)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return [path]


def generate_tiered_dashboard(
    model_summary: List[Dict[str, str]],
    metric_summary: List[Dict[str, str]],
    mds_rows: List[Dict[str, str]],
    output_path: str,
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
        print("matplotlib not available; skipping tiered dashboard.")
        return []

    asr_by_model: Dict[str, float] = {}
    frr_by_model: Dict[str, float] = {}
    for row in model_summary:
        model = row.get("model")
        if not model:
            continue
        try:
            asr_by_model[model] = float(row["avg_asr"])
            frr_by_model[model] = float(row["avg_frr"])
        except (TypeError, ValueError, KeyError):
            continue

    bias_by_model: Dict[str, float] = {}
    wsl_by_model: Dict[str, float] = {}
    cm_by_model: Dict[str, float] = {}
    for row in metric_summary:
        model = row.get("model")
        if not model:
            continue
        try:
            bias_by_model[model] = float(row["bias"])
        except (TypeError, ValueError, KeyError):
            pass
        try:
            wsl_by_model[model] = float(row["wsl"])
        except (TypeError, ValueError, KeyError):
            pass
        try:
            cm_by_model[model] = float(row["cm"])
        except (TypeError, ValueError, KeyError):
            pass

    mu_by_model: Dict[str, float] = {}
    sigma_by_model: Dict[str, float] = {}
    mds_by_model: Dict[str, float] = {}
    for row in mds_rows:
        model = row.get("model")
        if not model:
            continue
        try:
            mu_by_model[model] = float(row["mu_asr"])
            sigma_by_model[model] = float(row["sigma_asr"])
        except (TypeError, ValueError, KeyError):
            pass
        try:
            mds_by_model[model] = float(row["mds"])
        except (TypeError, ValueError, KeyError):
            pass

    if not (asr_by_model or bias_by_model or wsl_by_model or cm_by_model or mu_by_model or mds_by_model):
        return []

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.0))
    fig.patch.set_facecolor("#fafafa")

    # Panel 1: Safety-Utility Quadrant (ASR vs FRR)
    ax = axes[0, 0]
    models = sorted(set(asr_by_model) & set(frr_by_model))
    if models:
        x_vals = [frr_by_model[m] for m in models]
        y_vals = [asr_by_model[m] for m in models]
        ax.scatter(x_vals, y_vals, s=50, color="#1f77b4", alpha=0.85)
        for x_val, y_val, model in zip(x_vals, y_vals, models):
            ax.text(x_val + 0.01, y_val + 0.01, model, fontsize=8, color="#333333")
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.axvline(np.median(x_vals), color="#888888", linestyle="--", linewidth=0.8)
        ax.axhline(np.median(y_vals), color="#888888", linestyle="--", linewidth=0.8)
        ax.set_xlabel("FRR (lower is better)")
        ax.set_ylabel("ASR (lower is better)")
    else:
        ax.text(0.5, 0.5, "No ASR/FRR data", ha="center", va="center", color="#777777")
    ax.set_title("Safety-Utility Quadrant", fontsize=11, fontweight="bold", loc="left")

    # Panel 2: Business Risk (WSL + CM)
    ax = axes[0, 1]
    models = sorted(set(wsl_by_model) & set(cm_by_model))
    if models:
        x = np.arange(len(models))
        width = 0.35
        ax.bar(x - width / 2, [wsl_by_model[m] for m in models], width, label="WSL", color="#f4a261")
        ax.bar(x + width / 2, [cm_by_model[m] for m in models], width, label="CM", color="#2a9d8f")
        ax.set_xticks(x)
        ax.set_xticklabels(models, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Mean loss / cost")
        ax.legend(frameon=False, fontsize=8)
    else:
        ax.text(0.5, 0.5, "No WSL/CM data", ha="center", va="center", color="#777777")
    ax.set_title("Business Risk View", fontsize=11, fontweight="bold", loc="left")

    # Panel 3: Bias Profile
    ax = axes[1, 0]
    models = sorted(bias_by_model, key=lambda m: bias_by_model[m])
    if models:
        values = [bias_by_model[m] for m in models]
        colors = ["#d62828" if v > 0 else "#457b9d" for v in values]
        ax.barh(models, values, color=colors, alpha=0.9)
        ax.axvline(0.0, color="#666666", linewidth=1.0)
        ax.set_xlabel("Bias (0 = balanced)")
        ax.tick_params(axis="y", labelsize=8)
    else:
        ax.text(0.5, 0.5, "No Bias data", ha="center", va="center", color="#777777")
    ax.set_title("Model Bias Profile", fontsize=11, fontweight="bold", loc="left")

    # Panel 4: Stability (mu/sigma or MDS fallback)
    ax = axes[1, 1]
    models = sorted(set(mu_by_model) & set(sigma_by_model))
    if models:
        x_vals = [mu_by_model[m] for m in models]
        y_vals = [sigma_by_model[m] for m in models]
        ax.scatter(x_vals, y_vals, s=50, color="#6c757d", alpha=0.85)
        for x_val, y_val, model in zip(x_vals, y_vals, models):
            ax.text(x_val + 0.01, y_val + 0.01, model, fontsize=8, color="#333333")
        ax.set_xlim(0.0, 1.0)
        max_sigma = max(y_vals) if y_vals else 1.0
        ax.set_ylim(0.0, max(0.1, max_sigma * 1.1))
        ax.set_xlabel("ASR mean (mu)")
        ax.set_ylabel("ASR std (sigma)")
    elif mds_by_model:
        models = sorted(mds_by_model, key=lambda m: mds_by_model[m], reverse=True)
        ax.bar(models, [mds_by_model[m] for m in models], color="#4c78a8", alpha=0.85)
        ax.set_xticklabels(models, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("MDS")
    else:
        ax.text(0.5, 0.5, "No stability data", ha="center", va="center", color="#777777")
    ax.set_title("Stability Snapshot", fontsize=11, fontweight="bold", loc="left")

    fig.suptitle("Tiered Safety Dashboard", fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.96])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return [output_path]


def generate_exec_summary(
    model_summary: List[Dict[str, str]],
    metric_summary: List[Dict[str, str]],
    mds_rows: List[Dict[str, str]],
    output_path: str,
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
        print("matplotlib not available; skipping exec summary.")
        return []

    asr_by_model: Dict[str, float] = {}
    frr_by_model: Dict[str, float] = {}
    for row in model_summary:
        model = row.get("model")
        if not model:
            continue
        try:
            asr_by_model[model] = float(row["avg_asr"])
            frr_by_model[model] = float(row["avg_frr"])
        except (TypeError, ValueError, KeyError):
            continue

    mds_by_model: Dict[str, float] = {}
    for row in mds_rows:
        model = row.get("model")
        if not model:
            continue
        try:
            mds_by_model[model] = float(row["mds"])
        except (TypeError, ValueError, KeyError):
            continue

    wsl_by_model: Dict[str, float] = {}
    cm_by_model: Dict[str, float] = {}
    for row in metric_summary:
        model = row.get("model")
        if not model:
            continue
        try:
            wsl_by_model[model] = float(row["wsl"])
        except (TypeError, ValueError, KeyError):
            pass
        try:
            cm_by_model[model] = float(row["cm"])
        except (TypeError, ValueError, KeyError):
            pass

    if not (asr_by_model and frr_by_model):
        return []

    simple_models = sorted(set(asr_by_model) & set(frr_by_model))
    simple_scores = {
        model: 1.0 - (asr_by_model[model] + frr_by_model[model]) / 2.0
        for model in simple_models
    }

    weighted_models = sorted(
        set(asr_by_model)
        & set(frr_by_model)
        & set(mds_by_model)
        & set(wsl_by_model)
        & set(cm_by_model)
    )

    def _minmax(vals: List[float]) -> List[float]:
        min_val = min(vals)
        max_val = max(vals)
        if max_val == min_val:
            return [1.0 for _ in vals]
        return [(val - min_val) / (max_val - min_val) for val in vals]

    weights = {
        "ASR": 0.40,
        "FRR": 0.25,
        "MDS": 0.20,
        "WSL": 0.10,
        "CM": 0.05,
    }

    weighted_scores: Dict[str, float] = {}
    if weighted_models:
        asr_vals = [asr_by_model[m] for m in weighted_models]
        frr_vals = [frr_by_model[m] for m in weighted_models]
        mds_vals = [mds_by_model[m] for m in weighted_models]
        wsl_vals = [wsl_by_model[m] for m in weighted_models]
        cm_vals = [cm_by_model[m] for m in weighted_models]

        asr_norm = [1.0 - v for v in _minmax(asr_vals)]
        frr_norm = [1.0 - v for v in _minmax(frr_vals)]
        mds_norm = _minmax(mds_vals)
        wsl_norm = [1.0 - v for v in _minmax(wsl_vals)]
        cm_norm = [1.0 - v for v in _minmax(cm_vals)]

        for idx, model in enumerate(weighted_models):
            weighted_scores[model] = (
                weights["ASR"] * asr_norm[idx]
                + weights["FRR"] * frr_norm[idx]
                + weights["MDS"] * mds_norm[idx]
                + weights["WSL"] * wsl_norm[idx]
                + weights["CM"] * cm_norm[idx]
            )

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8))
    fig.patch.set_facecolor("#fafafa")

    ax = axes[0]
    models = sorted(simple_scores, key=lambda m: simple_scores[m], reverse=True)
    ax.barh(models, [simple_scores[m] for m in models], color="#457b9d", alpha=0.9)
    ax.invert_yaxis()
    ax.set_xlim(0.0, 1.0)
    ax.set_xlabel("Score (1 = best)")
    ax.set_title("Simple Score (1 - (ASR+FRR)/2)", fontsize=11, fontweight="bold", loc="left")
    ax.tick_params(axis="y", labelsize=8)

    ax = axes[1]
    if weighted_scores:
        models = sorted(weighted_scores, key=lambda m: weighted_scores[m], reverse=True)
        ax.barh(models, [weighted_scores[m] for m in models], color="#2a9d8f", alpha=0.9)
        ax.invert_yaxis()
        ax.set_xlim(0.0, 1.0)
        ax.set_xlabel("Score (weighted)")
        ax.set_title("Weighted Score (ASR/FRR/MDS/WSL/CM)", fontsize=11, fontweight="bold", loc="left")
        ax.tick_params(axis="y", labelsize=8)
        ax.text(
            0.0,
            -0.12,
            "Weights: ASR 0.40, FRR 0.25, MDS 0.20, WSL 0.10, CM 0.05",
            transform=ax.transAxes,
            fontsize=8,
            color="#555555",
        )
    else:
        ax.text(0.5, 0.5, "No full-metric data", ha="center", va="center", color="#777777")
        ax.set_axis_off()

    fig.suptitle("Executive Summary Overview", fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.95])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return [output_path]


def write_markdown(
    output_path: str,
    model_summary: List[Dict[str, str]],
    attack_list: List[str],
    matrix_rows: List[Dict[str, str]],
    mds_rows: List[Dict[str, str]],
    metric_summary: List[Dict[str, str]],
    kappa_summary: Optional[Dict[str, str]],
    plot_paths: List[str],
    unparsed: List[str],
    input_path: str,
    mds_dir: str,
    radar_paths: List[str],
    tiered_paths: List[str],
    exec_summary_paths: List[str],
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
        frr_heatmap_path = next(
            (p for p in plot_paths if os.path.basename(p) == os.path.basename(DEFAULT_FRR_HEATMAP)),
            None,
        )
        if frr_heatmap_path:
            rel_frr_heatmap = os.path.relpath(frr_heatmap_path, os.path.dirname(output_path))
            lines.extend(["", f"![Model FRR by Attack Heatmap]({rel_frr_heatmap})"])

    if model_summary:
        lines.extend(
            [
                "",
                "## Model Summary (Average ASR/FRR across attacks)",
                "",
                "| Model | Avg ASR | Avg FRR | Attacks Covered |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in model_summary:
            lines.append(
                "| {model} | {avg_asr} | {avg_frr} | {attacks} |".format(
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

        frr_model_bar_path = next(
            (p for p in plot_paths if os.path.basename(p) == os.path.basename(DEFAULT_FRR_MODEL_BAR)),
            None,
        )
        if frr_model_bar_path:
            rel_frr_bar = os.path.relpath(frr_model_bar_path, os.path.dirname(output_path))
            lines.extend(["", f"![Model Average FRR Bar]({rel_frr_bar})"])

        attack_bar_path = next(
            (p for p in plot_paths if os.path.basename(p) == os.path.basename(DEFAULT_ATTACK_BAR)),
            None,
        )
        if attack_bar_path:
            rel_attack_bar = os.path.relpath(attack_bar_path, os.path.dirname(output_path))
            lines.extend(["", f"![Attack Average ASR Bar]({rel_attack_bar})"])

    if exec_summary_paths:
        lines.extend(
            [
                "",
                "## Executive Summary Overview",
                "",
                "Left: simple score (1 - (ASR+FRR)/2). Right: weighted score.",
                "",
            ]
        )
        rel_exec = os.path.relpath(exec_summary_paths[0], os.path.dirname(output_path))
        lines.append(f"![Executive Summary]({rel_exec})")

    if tiered_paths:
        lines.extend(
            [
                "",
                "## Tiered Safety Dashboard",
                "",
                "Dashboard separates safety-utility tradeoffs, business risk, and model bias/stability.",
                "",
            ]
        )
        rel_tiered = os.path.relpath(tiered_paths[0], os.path.dirname(output_path))
        lines.append(f"![Tiered Dashboard]({rel_tiered})")

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
        mds_bar_path = next(
            (p for p in plot_paths if os.path.basename(p) == os.path.basename(DEFAULT_MDS_BAR)),
            None,
        )
        if mds_bar_path:
            rel_mds_bar = os.path.relpath(mds_bar_path, os.path.dirname(output_path))
            lines.extend(["", f"![Model MDS Bar]({rel_mds_bar})"])

    if metric_summary:
        lines.extend(
            [
                "",
                "## Model Bias/WSL/CM Summary (Average across attacks)",
                "",
                "| Model | Bias | WSL | CM |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in metric_summary:
            lines.append(
                "| {model} | {bias} | {wsl} | {cm} |".format(
                    **row
                )
            )
        bias_bar_path = next(
            (p for p in plot_paths if os.path.basename(p) == os.path.basename(DEFAULT_BIAS_BAR)),
            None,
        )
        if bias_bar_path:
            rel_bias = os.path.relpath(bias_bar_path, os.path.dirname(output_path))
            lines.extend(["", f"![Model Bias Bar]({rel_bias})"])
        wsl_bar_path = next(
            (p for p in plot_paths if os.path.basename(p) == os.path.basename(DEFAULT_WSL_BAR)),
            None,
        )
        if wsl_bar_path:
            rel_wsl = os.path.relpath(wsl_bar_path, os.path.dirname(output_path))
            lines.extend(["", f"![Model WSL Bar]({rel_wsl})"])
        cm_bar_path = next(
            (p for p in plot_paths if os.path.basename(p) == os.path.basename(DEFAULT_CM_BAR)),
            None,
        )
        if cm_bar_path:
            rel_cm = os.path.relpath(cm_bar_path, os.path.dirname(output_path))
            lines.extend(["", f"![Model CM Bar]({rel_cm})"])

    if radar_paths:
        lines.extend(
            [
                "",
                "## Model Metrics Radar (Normalized)",
                "",
                (
                    "Radar chart is min-max normalized per metric. "
                    "Lower-is-better metrics are inverted (ASR/FRR/Bias), "
                    "so outward always means better performance."
                ),
                "",
            ]
        )
        rel_path = os.path.relpath(radar_paths[0], os.path.dirname(output_path))
        lines.append(f"![Model Radar]({rel_path})")

    if unparsed:
        lines.extend(["", "## Unparsed attack runs", ""])
        for attack_run in sorted(set(unparsed)):
            lines.append(f"- {attack_run}")

    if kappa_summary:
        lines.extend(["", "## Notes", ""])
        lines.append(
            "Kappa summary: avg={avg_kappa}, median={median_kappa}, min={min_kappa}, "
            "max={max_kappa}, total_rows={total_rows}, skipped_rows={skipped_rows}".format(
                **kappa_summary
            )
        )

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


def format_model_metric_summary(
    bias_vals: Dict[str, List[float]],
    wsl_vals: Dict[str, List[float]],
    cm_vals: Dict[str, List[float]],
) -> List[Dict[str, str]]:
    models = sorted(set(bias_vals) | set(wsl_vals) | set(cm_vals))
    rows: List[Dict[str, str]] = []
    for model in models:
        bias_list = bias_vals.get(model, [])
        wsl_list = wsl_vals.get(model, [])
        cm_list = cm_vals.get(model, [])
        bias_avg = f"{(sum(bias_list) / len(bias_list)):.6f}" if bias_list else ""
        wsl_avg = f"{(sum(wsl_list) / len(wsl_list)):.6f}" if wsl_list else ""
        cm_avg = f"{(sum(cm_list) / len(cm_list)):.6f}" if cm_list else ""
        rows.append(
            {
                "model": model,
                "bias": bias_avg,
                "wsl": wsl_avg,
                "cm": cm_avg,
            }
        )
    return rows


def read_kappa_summary(path: str) -> Optional[Dict[str, str]]:
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
                    "avg_kappa": (row.get("avg_kappa") or row.get("kappa") or "").strip(),
                    "median_kappa": (row.get("median_kappa") or "").strip(),
                    "min_kappa": (row.get("min_kappa") or "").strip(),
                    "max_kappa": (row.get("max_kappa") or "").strip(),
                    "total_rows": (row.get("total_rows") or "").strip(),
                    "skipped_rows": (row.get("skipped_rows") or "").strip(),
                }
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize evaluation_report/asr/summary_long.csv into a Markdown overview."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to summary_long.csv")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output Markdown path")
    parser.add_argument("--mds-dir", default=DEFAULT_MDS_DIR, help="Directory with MDS reports")
    parser.add_argument("--bias-dir", default=DEFAULT_BIAS_DIR, help="Directory with Bias reports")
    parser.add_argument("--wsl-dir", default=DEFAULT_WSL_DIR, help="Directory with WSL reports")
    parser.add_argument("--cm-dir", default=DEFAULT_CM_DIR, help="Directory with CM reports")
    parser.add_argument("--kappa-csv", default=DEFAULT_KAPPA_CSV, help="Kappa report CSV path")
    parser.add_argument("--heatmap", default=DEFAULT_HEATMAP, help="Heatmap image path")
    parser.add_argument("--frr-heatmap", default=DEFAULT_FRR_HEATMAP, help="FRR heatmap image path")
    parser.add_argument("--model-bar", default=DEFAULT_MODEL_BAR, help="Model bar chart path")
    parser.add_argument("--attack-bar", default=DEFAULT_ATTACK_BAR, help="Attack bar chart path")
    parser.add_argument("--bias-bar", default=DEFAULT_BIAS_BAR, help="Bias bar chart path")
    parser.add_argument("--wsl-bar", default=DEFAULT_WSL_BAR, help="WSL bar chart path")
    parser.add_argument("--cm-bar", default=DEFAULT_CM_BAR, help="CM bar chart path")
    parser.add_argument("--mds-bar", default=DEFAULT_MDS_BAR, help="MDS bar chart path")
    parser.add_argument("--frr-bar", default=DEFAULT_FRR_MODEL_BAR, help="FRR model bar chart path")
    parser.add_argument("--frr-dir", default=DEFAULT_FRR_DIR, help="Directory with FRR reports")
    parser.add_argument("--radar-dir", default=DEFAULT_RADAR_DIR, help="Radar chart output directory")
    parser.add_argument(
        "--tiered-dashboard",
        default=DEFAULT_TIERED_DASHBOARD,
        help="Tiered dashboard image path",
    )
    parser.add_argument(
        "--exec-summary",
        default=DEFAULT_EXEC_SUMMARY,
        help="Executive summary overview image path",
    )
    parser.add_argument("--no-plots", action="store_true", help="Disable plot generation")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        raise SystemExit(f"summary_long.csv not found: {input_path}")

    frr_by_run = read_frr_reports(os.path.abspath(args.frr_dir))
    groups, unparsed = read_summary_long(input_path, frr_by_run)
    rows = format_group_rows(groups)
    if not rows:
        raise SystemExit("No valid rows found in summary_long.csv")

    model_summary = format_model_summary(rows)
    attack_list, matrix_rows = format_model_attack_matrix(rows)
    mds_dir = os.path.abspath(args.mds_dir)
    mds_rows = read_mds_reports(mds_dir)
    bias_vals = read_metric_reports(
        os.path.abspath(args.bias_dir),
        r"^Mean\(response_label - (?:question_label|response_strategy_label)\):\s*([0-9.\-]+)",
    )
    wsl_vals = read_metric_reports(
        os.path.abspath(args.wsl_dir),
        r"^Mean weighted loss:\s*([0-9.\-]+)",
    )
    cm_vals = read_metric_reports(
        os.path.abspath(args.cm_dir),
        r"^Mean cost:\s*([0-9.\-]+)",
    )
    metric_summary = format_model_metric_summary(bias_vals, wsl_vals, cm_vals)
    kappa_summary = read_kappa_summary(os.path.abspath(args.kappa_csv))
    plot_paths: List[str] = []
    radar_paths: List[str] = []
    tiered_paths: List[str] = []
    exec_summary_paths: List[str] = []
    if not args.no_plots:
        plot_paths = generate_plots(
            rows,
            os.path.abspath(args.heatmap),
            os.path.abspath(args.frr_heatmap),
            os.path.abspath(args.model_bar),
            os.path.abspath(args.attack_bar),
            os.path.abspath(args.frr_bar),
        )
        plot_paths.extend(
            generate_metric_charts_from_summary(
                metric_summary,
                os.path.abspath(args.bias_bar),
                os.path.abspath(args.wsl_bar),
                os.path.abspath(args.cm_bar),
            )
        )
        plot_paths.extend(
            generate_mds_bar(
                mds_rows,
                os.path.abspath(args.mds_bar),
            )
        )
        tiered_paths = generate_tiered_dashboard(
            model_summary,
            metric_summary,
            mds_rows,
            os.path.abspath(args.tiered_dashboard),
        )
        exec_summary_paths = generate_exec_summary(
            model_summary,
            metric_summary,
            mds_rows,
            os.path.abspath(args.exec_summary),
        )
    write_markdown(
        args.output,
        model_summary,
        attack_list,
        matrix_rows,
        mds_rows,
        metric_summary,
        kappa_summary,
        plot_paths,
        unparsed,
        input_path,
        mds_dir,
        radar_paths,
        tiered_paths,
        exec_summary_paths,
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
