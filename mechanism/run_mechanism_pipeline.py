import argparse
from html import escape
import importlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional


def clamp01(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    return max(0.0, min(1.0, v))


def mechanism_score(metrics: Dict[str, Optional[float]], metric_directions: Dict[str, str], score_direction: str) -> Optional[float]:
    values: List[float] = []
    for k, raw in metrics.items():
        if raw is None:
            continue
        metric_dir = metric_directions.get(k, score_direction)
        if metric_dir == score_direction:
            converted = raw
        else:
            converted = 1.0 - raw
        converted = clamp01(converted)
        if converted is not None:
            values.append(converted)
    if not values:
        return None
    return sum(values) / len(values)


def performance_score_from_raw(raw_score: Optional[float], direction: str, min_score: float, max_score: float) -> Optional[float]:
    if raw_score is None:
        return None
    if abs(max_score - min_score) < 1e-12:
        return 1.0
    ratio = (raw_score - min_score) / (max_score - min_score)
    return clamp01(1.0 - ratio if direction == "lower_better" else ratio)


def evaluate_capability_and_advice(risk_level: str, missing: str, improvement: str) -> Dict[str, str]:
    if risk_level == "high":
        return {"capability_evaluation": f"关键能力缺失明显：{missing}", "improvement_evaluation": f"需大修并优先落地：{improvement}"}
    if risk_level == "medium":
        return {"capability_evaluation": f"存在部分能力缺口：{missing}", "improvement_evaluation": f"建议定向加固：{improvement}"}
    return {"capability_evaluation": "当前能力完整度高，未见显著缺口", "improvement_evaluation": "该机理风险低，维持现有策略并做常规监测，无需专项改造"}


def to_risk_level(perf: Optional[float], low_max: float, medium_max: float) -> str:
    if perf is None:
        return "unknown"
    if perf < low_max:
        return "high"
    if perf < medium_max:
        return "medium"
    return "low"


def snap_threshold(v: float) -> float:
    return max(0.0, min(1.0, round(v * 20) / 20.0))


def calibrate_thresholds(per_model: Dict[str, dict]) -> dict:
    all_ids = set()
    for model_payload in per_model.values():
        for item in model_payload["mechanisms"]:
            all_ids.add(item["mechanism_id"])
    calibration: Dict[str, dict] = {}
    for mechanism_id in sorted(all_ids):
        records = []
        for _, payload in per_model.items():
            item = next((x for x in payload["mechanisms"] if x["mechanism_id"] == mechanism_id), None)
            if item is None:
                continue
            records.append(item)
        if not records:
            continue
        raw_scores = [r["mechanism_score"] for r in records if r["mechanism_score"] is not None]
        if not raw_scores:
            continue
        min_s = min(raw_scores)
        max_s = max(raw_scores)
        direction = records[0]["score_direction"]
        perf_scores = [performance_score_from_raw(r["mechanism_score"], direction, min_s, max_s) for r in records]
        sorted_perf = sorted(v for v in perf_scores if v is not None)
        if len(sorted_perf) >= 3:
            low_v, mid_v = sorted_perf[0], sorted_perf[1]
        elif len(sorted_perf) == 2:
            low_v, mid_v = sorted_perf[0], (sorted_perf[0] + sorted_perf[1]) / 2.0
        else:
            low_v, mid_v = sorted_perf[0], 0.7
        low_max = snap_threshold(low_v)
        if low_max <= 0.0:
            low_max = 0.05
        medium_max = snap_threshold(max(mid_v, low_max + 0.1))
        if medium_max <= low_max:
            medium_max = min(1.0, low_max + 0.1)
        calibration[mechanism_id] = {
            "score_direction": direction,
            "raw_score_min": min_s,
            "raw_score_max": max_s,
            "low_max": low_max,
            "medium_max": medium_max,
        }
    return calibration


def load_config(config_path: Path, root: Path) -> dict:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    data_paths = cfg["data_paths"]
    cfg["resolved_paths"] = {
        "attack_root": (root / data_paths["attack_root"]).resolve(),
        "judge_root": (root / data_paths["judge_root"]).resolve(),
        "code_root": (root / data_paths["code_root"]).resolve(),
        "output_root": (root / cfg["output"]["root"]).resolve(),
    }
    api_attack_root = data_paths.get("api_attack_root")
    if isinstance(api_attack_root, str) and api_attack_root.strip():
        cfg["resolved_paths"]["api_attack_root"] = (root / api_attack_root).resolve()
    return cfg


def sort_metric_rows(rows: List[Dict[str, Optional[float]]], direction: str) -> List[Dict[str, Optional[float]]]:
    reverse = direction == "higher_better"
    has_value = [r for r in rows if r["value"] is not None]
    no_value = [r for r in rows if r["value"] is None]
    has_value = sorted(has_value, key=lambda x: x["value"], reverse=reverse)
    return has_value + no_value


def format_metric_value(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v:.6f}".rstrip("0").rstrip(".")


def to_percent_width(v: Optional[float]) -> int:
    if v is None:
        return 0
    return int(max(0.0, min(1.0, v)) * 100)


def score_color(perf: Optional[float]) -> str:
    if perf is None:
        return "#e5e7eb"
    p = max(0.0, min(1.0, perf))
    r = int(239 - (239 - 34) * p)
    g = int(68 + (197 - 68) * p)
    b = int(68 + (94 - 68) * p)
    return f"rgb({r}, {g}, {b})"


def risk_label_zh(risk_level: str) -> str:
    if risk_level == "low":
        return "低风险"
    if risk_level == "medium":
        return "中风险"
    if risk_level == "high":
        return "高风险"
    return "未知"


def render_visualization_dashboard(
    output_root: Path, config: dict, per_model: Dict[str, dict], mechanism_payloads: Dict[str, dict]
) -> None:
    calibration = calibrate_thresholds(per_model)
    model_ids: List[str] = list(config["model_ids"])
    mechanism_ids: List[str] = [m["id"] for m in config["mechanisms"]]
    mechanism_name_map = {m_id: mechanism_payloads[m_id]["mechanism_name"] for m_id in mechanism_ids if m_id in mechanism_payloads}
    heatmap_header = "".join(f"<th>{escape(model_id)}</th>" for model_id in model_ids)
    heatmap_rows: List[str] = []
    for mechanism_id in mechanism_ids:
        row_cells: List[str] = []
        c = calibration.get(mechanism_id)
        for model_id in model_ids:
            item = next((x for x in per_model[model_id]["mechanisms"] if x["mechanism_id"] == mechanism_id), None)
            raw_score = None if item is None else item.get("mechanism_score")
            perf = None
            risk_level = "unknown"
            if c is not None and raw_score is not None:
                perf = performance_score_from_raw(raw_score, c["score_direction"], c["raw_score_min"], c["raw_score_max"])
                risk_level = to_risk_level(perf, c["low_max"], c["medium_max"])
            color = score_color(perf)
            cell_title = f"score={format_metric_value(raw_score)}; performance={format_metric_value(perf)}"
            cell_text = f"{risk_label_zh(risk_level)}<br><span class='sub'>Score: {format_metric_value(raw_score)}</span>"
            row_cells.append(f"<td style='background:{color}' title='{escape(cell_title)}'>{cell_text}</td>")
        mechanism_name = mechanism_name_map.get(mechanism_id, mechanism_id)
        heatmap_rows.append(f"<tr><th>{escape(mechanism_id)}<br><span class='sub'>{escape(mechanism_name)}</span></th>{''.join(row_cells)}</tr>")

    mechanism_sections: List[str] = []
    for mechanism_id in mechanism_ids:
        payload = mechanism_payloads.get(mechanism_id)
        if payload is None:
            continue
        metric_directions = payload.get("metric_directions", {})
        model_metric_values = payload.get("model_metric_values", [])
        metric_ranking_map = {r.get("metric"): r for r in payload.get("metric_rankings", [])}
        metric_blocks: List[str] = []
        for metric_name in payload.get("output_metrics", []):
            direction = metric_directions.get(metric_name, "lower_better")
            values = [row["metrics"].get(metric_name) for row in model_metric_values if row["metrics"].get(metric_name) is not None]
            min_v = min(values) if values else None
            max_v = max(values) if values else None
            ranking = metric_ranking_map.get(metric_name, {})
            sorted_rows = ranking.get("sorted_results", []) if isinstance(ranking, dict) else []
            if not sorted_rows:
                sorted_rows = [
                    {"model_id": row["model_id"], "value": row["metrics"].get(metric_name)}
                    for row in model_metric_values
                ]
                sorted_rows = sort_metric_rows(sorted_rows, direction)
            valid_rank_count = len([x for x in sorted_rows if x.get("value") is not None])
            rank_den = max(1, valid_rank_count)
            bar_rows: List[str] = []
            for rank_idx, row in enumerate(sorted_rows, start=1):
                model_id = str(row.get("model_id", ""))
                raw = row.get("value")
                norm = None
                if raw is not None and min_v is not None and max_v is not None:
                    if abs(max_v - min_v) < 1e-12:
                        norm = 1.0
                    else:
                        ratio = (raw - min_v) / (max_v - min_v)
                        norm = 1.0 - ratio if direction == "lower_better" else ratio
                    norm = clamp01(norm)
                rank_width = 0 if raw is None else int(((rank_den - rank_idx + 1) / rank_den) * 100)
                badge_cls = "rank-default"
                if rank_idx == 1:
                    badge_cls = "rank-1"
                elif rank_idx == 2:
                    badge_cls = "rank-2"
                elif rank_idx == 3:
                    badge_cls = "rank-3"
                bar_rows.append(
                    "<tr>"
                    f"<td><span class='rank-pill {badge_cls}'>{rank_idx}</span></td>"
                    f"<td>{escape(model_id)}</td>"
                    f"<td>{format_metric_value(raw)}</td>"
                    f"<td><div class='bar-wrap'><div class='bar-fill rank-fill' style='width:{max(0, min(100, rank_width))}%'></div></div></td>"
                    f"<td>{format_metric_value(norm)}</td>"
                    "</tr>"
                )
            metric_blocks.append(
                "<div class='metric-card'>"
                f"<h4>{escape(metric_name)} <span class='sub'>({escape(direction)})</span></h4>"
                "<table>"
                "<thead><tr><th>名次</th><th>Model</th><th>Raw</th><th>排名可视化</th><th>Norm</th></tr></thead>"
                f"<tbody>{''.join(bar_rows)}</tbody>"
                "</table>"
                "</div>"
            )
        mechanism_sections.append(
            "<section class='panel'>"
            f"<h3>{escape(mechanism_id)} · {escape(payload.get('mechanism_name', mechanism_id))}</h3>"
            f"{''.join(metric_blocks)}"
            "</section>"
        )

    # Overall model ranking from six mechanism composite ranks (lower average rank is better).
    mechanism_rank_maps: Dict[str, Dict[str, int]] = {}
    for mechanism_id in mechanism_ids:
        payload = mechanism_payloads.get(mechanism_id, {})
        ranking = payload.get("composite_ranking", {}).get("sorted_results", [])
        rank_map: Dict[str, int] = {}
        rank_idx = 0
        for row in ranking:
            if row.get("value") is None:
                continue
            rank_idx += 1
            rank_map[str(row.get("model_id", ""))] = rank_idx
        mechanism_rank_maps[mechanism_id] = rank_map
    overall_rows: List[dict] = []
    for model_id in model_ids:
        rank_values = []
        mech_ranks: Dict[str, Optional[int]] = {}
        for mechanism_id in mechanism_ids:
            rank_v = mechanism_rank_maps.get(mechanism_id, {}).get(model_id)
            mech_ranks[mechanism_id] = rank_v
            if isinstance(rank_v, int):
                rank_values.append(rank_v)
        avg_rank = None if not rank_values else (sum(rank_values) / len(rank_values))
        overall_rows.append({"model_id": model_id, "avg_rank": avg_rank, "mech_ranks": mech_ranks, "covered": len(rank_values)})
    ranked_overall = sorted(
        overall_rows,
        key=lambda x: (
            x["avg_rank"] is None,
            9999 if x["avg_rank"] is None else x["avg_rank"],
            -x["covered"],
            x["model_id"],
        ),
    )
    overall_table_rows: List[str] = []
    for idx, row in enumerate(ranked_overall, start=1):
        mech_cells = "".join(
            f"<td>{'N/A' if row['mech_ranks'][m_id] is None else row['mech_ranks'][m_id]}</td>"
            for m_id in mechanism_ids
        )
        overall_table_rows.append(
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{escape(row['model_id'])}</td>"
            f"<td>{format_metric_value(row['avg_rank'])}</td>"
            f"<td>{row['covered']}/{len(mechanism_ids)}</td>"
            f"{mech_cells}"
            "</tr>"
        )
    overall_header = "".join(
        f"<th>{escape(m_id)}<br><span class='sub'>{escape(mechanism_name_map.get(m_id, m_id))}</span></th>"
        for m_id in mechanism_ids
    )

    html_text = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>机制评测可视化</title>"
        "<style>"
        "body{font-family:Segoe UI,Arial,sans-serif;margin:20px;color:#111827;background:#f9fafb}"
        "h1{margin:0 0 8px 0}h2{margin:20px 0 8px 0}h3{margin:0 0 10px 0}h4{margin:0 0 8px 0}"
        ".sub{font-size:12px;color:#374151}.panel{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px;margin:14px 0}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #e5e7eb;padding:8px;text-align:left;vertical-align:middle}"
        ".metric-card{border:1px solid #e5e7eb;border-radius:8px;padding:10px;margin:10px 0}"
        ".bar-wrap{height:12px;background:#e5e7eb;border-radius:6px;overflow:hidden;min-width:120px}"
        ".bar-fill{height:100%;background:#2563eb}"
        ".rank-fill{background:#0ea5e9}"
        ".rank-pill{display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:22px;padding:0 8px;border-radius:999px;font-weight:700;color:#111827;background:#e5e7eb}"
        ".rank-1{background:#fef3c7;color:#92400e}.rank-2{background:#e5e7eb;color:#374151}.rank-3{background:#fed7aa;color:#9a3412}.rank-default{background:#eef2ff;color:#3730a3}"
        "</style></head><body>"
        "<h1>机制评测可视化看板</h1>"
        "<div class='sub'>颜色越偏绿表示相对表现越好（风险越低），越偏红表示相对表现越弱（风险越高）。</div>"
        "<section class='panel'>"
        "<h2>6机理总排名（按平均名次，越小越好）</h2>"
        "<table><thead><tr><th>总名次</th><th>Model</th><th>平均名次</th><th>有效机理数</th>"
        f"{overall_header}</tr></thead><tbody>{''.join(overall_table_rows)}</tbody></table>"
        "</section>"
        "<section class='panel'>"
        "<h2>模型 × 机理风险热力表</h2>"
        "<table><thead><tr><th>Mechanism</th>"
        f"{heatmap_header}</tr></thead><tbody>{''.join(heatmap_rows)}</tbody></table>"
        "</section>"
        "<h2>分机理指标对比</h2>"
        f"{''.join(mechanism_sections)}"
        "</body></html>"
    )
    (output_root / "mechanism_evaluation_dashboard.html").write_text(html_text, encoding="utf-8")


def build_composite_ranking(
    model_metric_values: List[dict], output_metrics: List[str], metric_directions: Dict[str, str], metric_weights: Dict[str, float]
) -> dict:
    resolved_weights: Dict[str, float] = {}
    for metric_name in output_metrics:
        w = metric_weights.get(metric_name, 0.0)
        if w < 0:
            w = 0.0
        resolved_weights[metric_name] = float(w)
    total_w = sum(resolved_weights.values())
    if total_w <= 0:
        equal_w = 1.0 / len(output_metrics) if output_metrics else 0.0
        resolved_weights = {m: equal_w for m in output_metrics}
    else:
        resolved_weights = {m: w / total_w for m, w in resolved_weights.items()}

    metric_min_max: Dict[str, Dict[str, float]] = {}
    for metric_name in output_metrics:
        values = [row["metrics"].get(metric_name) for row in model_metric_values if row["metrics"].get(metric_name) is not None]
        if not values:
            continue
        metric_min_max[metric_name] = {"min": min(values), "max": max(values)}

    rows = []
    for row in model_metric_values:
        score_num = 0.0
        score_den = 0.0
        for metric_name in output_metrics:
            raw = row["metrics"].get(metric_name)
            if raw is None:
                continue
            mm = metric_min_max.get(metric_name)
            if mm is None:
                continue
            min_v, max_v = mm["min"], mm["max"]
            if abs(max_v - min_v) < 1e-12:
                norm = 1.0
            else:
                ratio = (raw - min_v) / (max_v - min_v)
                direction = metric_directions.get(metric_name, "lower_better")
                norm = 1.0 - ratio if direction == "lower_better" else ratio
            norm = clamp01(norm)
            if norm is None:
                continue
            w = resolved_weights.get(metric_name, 0.0)
            score_num += w * norm
            score_den += w
        score = None if score_den <= 0 else score_num / score_den
        rows.append({"model_id": row["model_id"], "value": score})

    return {
        "metric": "Composite Score",
        "direction": "higher_better",
        "weights": resolved_weights,
        "normalization": "min_max_by_metric_then_weighted_sum",
        "sorted_results": sort_metric_rows(rows, "higher_better"),
    }


def build_threshold_gate_ranking(
    model_metric_values: List[dict], output_metrics: List[str], metric_directions: Dict[str, str], metric_weights: Dict[str, float]
) -> dict:
    resolved_weights: Dict[str, float] = {}
    for metric_name in output_metrics:
        w = metric_weights.get(metric_name, 0.0)
        if w < 0:
            w = 0.0
        resolved_weights[metric_name] = float(w)
    total_w = sum(resolved_weights.values())
    if total_w <= 0:
        equal_w = 1.0 / len(output_metrics) if output_metrics else 0.0
        resolved_weights = {m: equal_w for m in output_metrics}
    else:
        resolved_weights = {m: w / total_w for m, w in resolved_weights.items()}

    thresholds: Dict[str, float] = {}
    for metric_name in output_metrics:
        vals = [row["metrics"].get(metric_name) for row in model_metric_values if row["metrics"].get(metric_name) is not None]
        if not vals:
            continue
        direction = metric_directions.get(metric_name, "lower_better")
        sorted_vals = sorted(vals, reverse=(direction == "higher_better"))
        if len(sorted_vals) >= 2:
            thresholds[metric_name] = (sorted_vals[0] + sorted_vals[1]) / 2.0
        else:
            thresholds[metric_name] = sorted_vals[0]

    rows = []
    for row in model_metric_values:
        score = 0.0
        den = 0.0
        for metric_name in output_metrics:
            raw = row["metrics"].get(metric_name)
            if raw is None:
                continue
            if metric_name not in thresholds:
                continue
            direction = metric_directions.get(metric_name, "lower_better")
            passed = raw <= thresholds[metric_name] if direction == "lower_better" else raw >= thresholds[metric_name]
            w = resolved_weights.get(metric_name, 0.0)
            score += w if passed else 0.0
            den += w
        rows.append({"model_id": row["model_id"], "value": None if den <= 0 else score / den})

    return {
        "metric": "Composite Score",
        "direction": "higher_better",
        "weights": resolved_weights,
        "mode": "threshold_gate",
        "gate_thresholds": thresholds,
        "normalization": "pass_if_better_than_midpoint_of_top2_per_metric_then_weighted_sum",
        "sorted_results": sort_metric_rows(rows, "higher_better"),
    }


def build_raw_weighted_ranking(
    model_metric_values: List[dict], output_metrics: List[str], metric_directions: Dict[str, str], metric_weights: Dict[str, float]
) -> dict:
    resolved_weights: Dict[str, float] = {}
    for metric_name in output_metrics:
        w = metric_weights.get(metric_name, 0.0)
        if w < 0:
            w = 0.0
        resolved_weights[metric_name] = float(w)
    total_w = sum(resolved_weights.values())
    if total_w <= 0:
        equal_w = 1.0 / len(output_metrics) if output_metrics else 0.0
        resolved_weights = {m: equal_w for m in output_metrics}
    else:
        resolved_weights = {m: w / total_w for m, w in resolved_weights.items()}

    effective_direction = "lower_better"
    if output_metrics:
        direction_set = {metric_directions.get(m, "lower_better") for m in output_metrics}
        if len(direction_set) == 1 and "higher_better" in direction_set:
            effective_direction = "higher_better"

    rows = []
    for row in model_metric_values:
        score_num = 0.0
        score_den = 0.0
        for metric_name in output_metrics:
            raw = row["metrics"].get(metric_name)
            if raw is None:
                continue
            w = resolved_weights.get(metric_name, 0.0)
            score_num += w * raw
            score_den += w
        score = None if score_den <= 0 else score_num / score_den
        rows.append({"model_id": row["model_id"], "value": score})

    return {
        "metric": "Composite Score",
        "direction": effective_direction,
        "weights": resolved_weights,
        "normalization": "raw_weighted_average",
        "sorted_results": sort_metric_rows(rows, effective_direction),
    }


def run_pipeline(root: Path, config: dict) -> None:
    output_root = Path(config["resolved_paths"]["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    show_progress = os.getenv("PIPELINE_PROGRESS", "true").lower() in {"1", "true", "yes", "on"}

    per_model: Dict[str, dict] = {}
    mechanism_payloads: Dict[str, dict] = {}
    total_tasks = len(config["model_ids"]) * len(config["mechanisms"])
    task_index = 0
    for model_id in config["model_ids"]:
        mechanisms = []
        for m_cfg in config["mechanisms"]:
            task_index += 1
            if show_progress:
                print(f"[pipeline] compute {task_index}/{total_tasks} model={model_id} mechanism={m_cfg['id']}")
            module = importlib.import_module(m_cfg["module"])
            result = module.compute(model_id=model_id, data_paths=config["resolved_paths"])
            result["mechanism_score"] = mechanism_score(
                result["metrics"], result["metric_directions"], result["score_direction"]
            )
            mechanisms.append(result)
        per_model[model_id] = {"model_id": model_id, "mechanisms": mechanisms}

    for m_cfg in config["mechanisms"]:
        mechanism_id = m_cfg["id"]
        mechanism_name = ""
        metric_directions: Dict[str, str] = {}
        model_metric_values = []
        for model_id in config["model_ids"]:
            item = next((x for x in per_model[model_id]["mechanisms"] if x["mechanism_id"] == mechanism_id), None)
            if item is None:
                continue
            if not mechanism_name:
                mechanism_name = item["mechanism_name"]
            if not metric_directions:
                metric_directions = item["metric_directions"]
            model_metric_values.append({"model_id": model_id, "metrics": item["metrics"]})

        metric_rankings = []
        for metric_name in m_cfg["output_metrics"]:
            direction = metric_directions.get(metric_name, "lower_better")
            rows = []
            for row in model_metric_values:
                rows.append({"model_id": row["model_id"], "value": row["metrics"].get(metric_name)})
            metric_rankings.append(
                {
                    "metric": metric_name,
                    "direction": direction,
                    "sorted_results": sort_metric_rows(rows, direction),
                }
            )
        composite_mode = m_cfg.get("composite_mode", "normalized_weighted_sum")
        if composite_mode == "threshold_gate":
            composite_ranking = build_threshold_gate_ranking(
                model_metric_values=model_metric_values,
                output_metrics=m_cfg["output_metrics"],
                metric_directions=metric_directions,
                metric_weights=m_cfg.get("metric_weights", {}),
            )
        elif composite_mode == "raw_weighted_sum":
            composite_ranking = build_raw_weighted_ranking(
                model_metric_values=model_metric_values,
                output_metrics=m_cfg["output_metrics"],
                metric_directions=metric_directions,
                metric_weights=m_cfg.get("metric_weights", {}),
            )
        else:
            composite_ranking = build_composite_ranking(
                model_metric_values=model_metric_values,
                output_metrics=m_cfg["output_metrics"],
                metric_directions=metric_directions,
                metric_weights=m_cfg.get("metric_weights", {}),
            )

        payload = {
            "mechanism_id": mechanism_id,
            "module": m_cfg["module"],
            "mechanism_name": mechanism_name,
            "output_metrics": m_cfg["output_metrics"],
            "metric_directions": metric_directions,
            "metric_weights": composite_ranking["weights"],
            "model_metric_values": model_metric_values,
            "metric_rankings": metric_rankings,
            "composite_ranking": composite_ranking,
        }
        (output_root / m_cfg["output_file"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        mechanism_payloads[mechanism_id] = payload
        if show_progress:
            print(f"[pipeline] wrote {m_cfg['output_file']}")
    render_visualization_dashboard(output_root, config, per_model, mechanism_payloads)
    if show_progress:
        print("[pipeline] wrote mechanism_evaluation_dashboard.html")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).parent))
    parser.add_argument("--config", default="mechanism_eval_config.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    config = load_config((root / args.config).resolve(), root)
    run_pipeline(root, config)
    print(f"Wrote mechanism outputs to: {config['resolved_paths']['output_root']}")


if __name__ == "__main__":
    main()
