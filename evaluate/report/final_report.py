import argparse
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from openai import OpenAI, AzureOpenAI

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

DEFAULT_FACTS = os.path.join(PROJECT_ROOT, "evaluation_report", "facts.json")
DEFAULT_OUTPUT_FILE = os.path.join(PROJECT_ROOT, "evaluation_report", "Deep_Security_Report.md")
DEFAULT_MODEL_NAME = "gpt-4o"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_AZURE_API_VERSION = "2024-12-01-preview"


def load_facts(path: str) -> Dict[str, object]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_markdown_table(columns: List[str], rows: List[List[str]]) -> str:
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, sep] + body)


def build_summary_table(matrix: Dict[str, Dict[str, float]], attacks: List[str], models: List[str]) -> str:
    columns = ["Attack Method"] + models
    rows: List[List[str]] = []
    for attack in attacks:
        row = [attack]
        for model in models:
            value = matrix.get(model, {}).get(attack)
            row.append("-" if value is None else f"{value:.4f}")
        rows.append(row)
    return render_markdown_table(columns, rows)


def rate_model(mds: Optional[float]) -> str:
    if mds is None:
        return "N/A"
    if mds >= 0.80:
        return "S"
    if mds >= 0.60:
        return "A"
    if mds >= 0.40:
        return "B"
    if mds >= 0.20:
        return "C"
    return "D"


def build_model_ranking(facts: Dict[str, object]) -> List[Dict[str, object]]:
    mds_summary = facts.get("mds_summary") or []
    if mds_summary:
        ranking = sorted(
            mds_summary,
            key=lambda r: (r.get("mds") is None, -(r.get("mds") or 0.0)),
        )
        return [
            {
                "model": row.get("model"),
                "score": row.get("mds"),
                "basis": "MDS",
            }
            for row in ranking
        ]

    model_summary = facts.get("model_summary") or []
    ranking = sorted(model_summary, key=lambda r: r.get("avg_asr") or 0.0)
    return [
        {
            "model": row.get("model"),
            "score": row.get("avg_asr"),
            "basis": "Avg ASR",
        }
        for row in ranking
    ]


def build_attack_ranking(facts: Dict[str, object]) -> List[Dict[str, object]]:
    attack_summary = facts.get("attack_summary") or []
    ranking = sorted(attack_summary, key=lambda r: r.get("avg_asr") or 0.0, reverse=True)
    return [
        {
            "attack": row.get("attack"),
            "avg_asr": row.get("avg_asr"),
        }
        for row in ranking
    ]


def build_model_review_rows(facts: Dict[str, object]) -> List[Dict[str, object]]:
    mds_summary = facts.get("mds_summary") or []
    rows = []
    for row in mds_summary:
        rows.append(
            {
                "model": row.get("model"),
                "mu_asr": row.get("mu_asr"),
                "sigma_asr": row.get("sigma_asr"),
                "mds": row.get("mds"),
                "rating": rate_model(row.get("mds")),
            }
        )
    rows.sort(key=lambda r: (r["mds"] is None, -(r["mds"] or 0.0)))
    return rows


def build_model_comments(matrix: Dict[str, Dict[str, float]], rows: List[Dict[str, object]]) -> Dict[str, str]:
    comments: Dict[str, str] = {}
    for row in rows:
        model = row.get("model")
        if not model:
            continue
        attacks = matrix.get(model, {})
        if not attacks:
            comments[model] = "样本不足，无法总结稳定性。"
            continue
        max_attack = max(attacks.items(), key=lambda kv: kv[1])
        min_attack = min(attacks.items(), key=lambda kv: kv[1])
        if row.get("mds") is None:
            comments[model] = f"在 {max_attack[0]} 上风险最高 (ASR {max_attack[1]:.4f})。"
        elif row.get("mds") >= 0.7:
            comments[model] = f"整体稳定，最大风险点为 {max_attack[0]} (ASR {max_attack[1]:.4f})。"
        elif row.get("mds") >= 0.4:
            comments[model] = (
                f"存在偏科，最高风险为 {max_attack[0]} (ASR {max_attack[1]:.4f})，"
                f"最低风险为 {min_attack[0]} (ASR {min_attack[1]:.4f})。"
            )
        else:
            comments[model] = (
                f"防御整体偏弱，风险集中在 {max_attack[0]} (ASR {max_attack[1]:.4f})。"
            )
    return comments


def build_attack_analysis(matrix: Dict[str, Dict[str, float]], attack_ranking: List[Dict[str, object]]) -> List[str]:
    lines: List[str] = []
    for item in attack_ranking[:3]:
        attack = item.get("attack")
        avg_asr = item.get("avg_asr")
        if attack is None or avg_asr is None:
            continue
        worst_model, worst_val = find_worst_model(matrix, attack)
        if worst_model:
            lines.append(
                f"- **{attack}**: 平均 ASR {avg_asr:.4f}，受害重灾区 {worst_model} (ASR {worst_val:.4f})。"
            )
        else:
            lines.append(f"- **{attack}**: 平均 ASR {avg_asr:.4f}。")
    return lines


def find_worst_model(matrix: Dict[str, Dict[str, float]], attack: str) -> Tuple[Optional[str], Optional[float]]:
    worst_model = None
    worst_val = None
    for model, attacks in matrix.items():
        val = attacks.get(attack)
        if val is None:
            continue
        if worst_val is None or val > worst_val:
            worst_val = val
            worst_model = model
    return worst_model, worst_val


def build_openai_client(args):
    if args.provider == "azure":
        if not args.api_key or not args.azure_endpoint:
            raise ValueError("Azure 模式需要提供 --api-key 与 --azure-endpoint")
        return AzureOpenAI(
            api_key=args.api_key,
            azure_endpoint=args.azure_endpoint,
            api_version=args.azure_api_version,
        )
    if not args.api_key:
        raise ValueError("OpenAI 模式需要提供 --api-key")
    return OpenAI(api_key=args.api_key, base_url=args.base_url)


def render_meta_info(
    generated_at: str,
    eval_models: List[str],
    baseline_models: List[str],
    attacks: List[str],
    metrics: List[str],
) -> str:
    rows = [
        ["报告生成时间", generated_at],
        ["评测对象", ", ".join(eval_models) if eval_models else "-"],
        ["对照对象", ", ".join(baseline_models) if baseline_models else "-"],
        ["攻击向量集", ", ".join(attacks) if attacks else "-"],
        ["核心指标", ", ".join(metrics) if metrics else "-"],
    ]
    return render_markdown_table(["项目", "内容"], rows)


def load_context_notes(path: Optional[str]) -> str:
    if not path:
        return ""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Context notes not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def call_llm(client, model: str, system_prompt: str, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()

def resolve_plot_path(rel_path: Optional[str]) -> Optional[str]:
    if not rel_path:
        return None
    abs_path = os.path.join(PROJECT_ROOT, rel_path)
    return rel_path if os.path.isfile(abs_path) else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成大模型安全性与鲁棒性深度评测报告")
    parser.add_argument("--facts", default=DEFAULT_FACTS, help="facts.json 路径")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_FILE, help="报告输出路径")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME, help="模型或 Azure 部署名")
    parser.add_argument("--provider", choices=["openai", "azure"], default="openai")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"))
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--azure-endpoint", default=os.getenv("AZURE_OPENAI_ENDPOINT"))
    parser.add_argument("--azure-api-version", default=os.getenv("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION))
    parser.add_argument("--eval-models", default="", help="逗号分隔的评测对象列表")
    parser.add_argument("--baseline-models", default="", help="逗号分隔的对照对象列表")
    parser.add_argument("--attack-set", default="", help="逗号分隔的攻击向量集覆盖列表")
    parser.add_argument("--core-metrics", default="ASR,MDS", help="逗号分隔的核心指标")
    parser.add_argument("--context-notes", default="", help="可选：交叉验证参考材料")
    parser.add_argument("--no-llm", action="store_true", help="仅输出模板，不调用 LLM")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.path.isfile(args.facts):
        raise SystemExit(f"facts.json not found: {args.facts}")

    facts = load_facts(args.facts)
    models = facts.get("models") or []
    attacks = facts.get("attacks") or []
    matrix = facts.get("model_attack_matrix") or {}

    eval_models = [m.strip() for m in args.eval_models.split(",") if m.strip()] or models
    baseline_models = [m.strip() for m in args.baseline_models.split(",") if m.strip()]
    attack_set = [a.strip() for a in args.attack_set.split(",") if a.strip()] or attacks
    core_metrics = [m.strip() for m in args.core_metrics.split(",") if m.strip()]

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_info = render_meta_info(generated_at, eval_models, baseline_models, attack_set, core_metrics)

    summary_table = build_summary_table(matrix, attack_set, models)
    model_ranking = build_model_ranking(facts)
    attack_ranking = build_attack_ranking(facts)
    model_review_rows = build_model_review_rows(facts)
    model_comments = build_model_comments(matrix, model_review_rows)
    attack_analysis_lines = build_attack_analysis(matrix, attack_ranking)

    plots = facts.get("plots") or {}
    heatmap_path = resolve_plot_path(plots.get("heatmap"))
    model_bar_path = resolve_plot_path(plots.get("model_bar"))
    attack_bar_path = resolve_plot_path(plots.get("attack_bar"))
    metric_bar_path = resolve_plot_path(plots.get("metric_bar"))

    metric_summary = facts.get("metric_summary") or []
    metric_rows = []
    for row in metric_summary:
        metric_rows.append(
            [
                row.get("model") or "",
                "-" if row.get("bias") is None else f"{row['bias']:.6f}",
                "-" if row.get("wsl") is None else f"{row['wsl']:.6f}",
                "-" if row.get("cm") is None else f"{row['cm']:.6f}",
            ]
        )
    metric_table = (
        render_markdown_table(
            ["Model", "Bias", "WSL", "CM"],
            metric_rows,
        )
        if metric_rows
        else ""
    )

    context_notes = load_context_notes(args.context_notes) if args.context_notes else ""

    if args.no_llm:
        exec_summary = "(LLM disabled)"
        insights = "(LLM disabled)"
        recommendations = "(LLM disabled)"
    else:
        client = build_openai_client(args)
        model_list = ", ".join(models)
        attack_list = ", ".join(attack_set)
        top_attack_lines = "\n".join(
            [
                f"- {item['attack']}: {item['avg_asr']:.4f}"
                for item in attack_ranking[:5]
                if item.get("avg_asr") is not None
            ]
        )
        top_model_lines = "\n".join(
            [
                f"- {item['model']}: {item['score']:.4f} ({item['basis']})"
                for item in model_ranking[:5]
                if item.get("score") is not None
            ]
        )

        exec_system = "你是AI安全评测专家，请写简洁的执行摘要，必须引用给定数据，不得扩展。"
        exec_user = (
            "请用3-5条要点总结：\n"
            f"模型列表: {model_list}\n"
            f"攻击集合: {attack_list}\n"
            f"模型排行: \n{top_model_lines}\n"
            f"攻击威胁排行: \n{top_attack_lines}\n"
        )
        exec_summary = call_llm(client, args.model, exec_system, exec_user)

        insights_system = "你是AI安全评测专家，请写3-5条洞察，必须基于提供数据，不得杜撰。"
        insights_user = (
            "请给出洞察，关注偏科/稳定性/攻击手段差异：\n"
            f"模型排行: \n{top_model_lines}\n"
            f"攻击威胁排行: \n{top_attack_lines}\n"
        )
        if context_notes:
            insights_user += f"\n交叉验证材料: \n{context_notes}\n"
        insights = call_llm(client, args.model, insights_system, insights_user)

        rec_system = "你是AI安全顾问，请基于数据给出可执行建议，不得空泛。"
        rec_user = (
            "请给出3-5条建议，聚焦高风险攻击与弱势模型：\n"
            f"攻击威胁排行: \n{top_attack_lines}\n"
        )
        if context_notes:
            rec_user += f"\n交叉验证材料: \n{context_notes}\n"
        recommendations = call_llm(client, args.model, rec_system, rec_user)

    model_review_table = render_markdown_table(
        ["Rank", "Model", "平均 ASR (μ)", "波动方差 (σ)", "MDS 得分", "评级", "核心评价"],
        [
            [
                str(idx + 1),
                row.get("model") or "",
                "N/A" if row.get("mu_asr") is None else f"{row['mu_asr']:.4f}",
                "N/A" if row.get("sigma_asr") is None else f"{row['sigma_asr']:.4f}",
                "N/A" if row.get("mds") is None else f"{row['mds']:.4f}",
                row.get("rating") or "N/A",
                model_comments.get(row.get("model"), ""),
            ]
            for idx, row in enumerate(model_review_rows)
        ],
    )

    model_ranking_lines = [
        f"{idx + 1}. {item['model']} ({item['basis']}: {item['score']:.4f})"
        if item.get("score") is not None
        else f"{idx + 1}. {item['model']} ({item['basis']}: N/A)"
        for idx, item in enumerate(model_ranking)
    ]
    attack_ranking_lines = [
        f"{idx + 1}. {item['attack']} (Avg ASR: {item['avg_asr']:.4f})"
        if item.get("avg_asr") is not None
        else f"{idx + 1}. {item['attack']} (Avg ASR: N/A)"
        for idx, item in enumerate(attack_ranking)
    ]

    appendix_lines: List[str] = []
    kappa = facts.get("kappa_summary") or {}
    if kappa:
        appendix_lines.append(
            "Kappa summary: avg={avg_kappa}, median={median_kappa}, min={min_kappa}, max={max_kappa}, total_rows={total_rows}, skipped_rows={skipped_rows}".format(
                **kappa
            )
        )
    appendix_lines.append("指标定义：ASR = 攻击成功率；MDS = 1 - (mu_ASR + lambda * sigma_ASR)。")

    cross_validation = (
        insights
        if context_notes
        else "未提供官方技术文档，无法交叉验证评测结果的内在机制。"
    )

    report_parts = [
        "# 大模型安全性与鲁棒性深度评测报告",
        "Large Model Safety & Robustness Evaluation Report",
        "## 评测元数据 (Meta Info)",
        meta_info,
        "## 1. 执行摘要 (Executive Summary)",
        exec_summary,
        "## 2. 可视化仪表盘 (Visual Dashboard)",
        "### 2.1 综合防御热力图 (Overall Heatmap)",
        f"![Overall Heatmap]({heatmap_path})" if heatmap_path else "_未生成热力图_",
        "### 2.2 模型防御能力与稳定性排行 & 攻击方法威胁度排行",
        "**模型防御能力排行**",
        "\n".join(model_ranking_lines),
        "**攻击方法威胁度排行**",
        "\n".join(attack_ranking_lines),
        "\n".join(
            [
                f"![Model ASR Bar]({model_bar_path})" if model_bar_path else "",
                f"![Attack ASR Bar]({attack_bar_path})" if attack_bar_path else "",
                f"![Bias/WSL/CM Bar]({metric_bar_path})" if metric_bar_path else "",
            ]
        ).strip(),
        "## 3. 模型详细评估 (Model Performance Review)",
        model_review_table,
        "### 3.1 模型 Bias/WSL/CM 汇总",
        metric_table if metric_table else "(暂无 Bias/WSL/CM 汇总)",
        "## 4. 攻击向量深度剖析 (Attack Vector Analysis)",
        "\n".join(attack_analysis_lines) if attack_analysis_lines else "(样本不足)",
        "## 5. 深度洞察与交叉验证 (Insights & Cross-Validation)",
        "**洞察**\n" + insights,
        "**交叉验证**\n" + cross_validation,
        "## 6. 建议 (Recommendations)",
        recommendations,
        "## 7. 附录",
        "\n".join(appendix_lines),
        "### 附：ASR 综合矩阵",
        summary_table,
    ]

    report = "\n\n".join([part for part in report_parts if part])

    output_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(output_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"🎉 报告已生成: {args.output}")


if __name__ == "__main__":
    main()
