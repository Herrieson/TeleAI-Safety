import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import settings


def mechanism_output_root() -> Path:
    return settings.mechanism_output_root


def mechanism_dashboard_path() -> Path:
    return mechanism_output_root() / "mechanism_evaluation_dashboard.html"


def _safe_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_json(path: Path) -> Optional[dict]:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _mechanism_json_files() -> List[Path]:
    root = mechanism_output_root()
    if not root.exists():
        return []
    return sorted(
        [
            path
            for path in root.glob("mechanism_*.json")
            if path.is_file() and path.name != "mechanism_evaluation_dashboard.html"
        ]
    )


def _extract_metric_snapshot(payload: dict) -> List[dict]:
    rankings = payload.get("metric_rankings") or []
    model_metric_values = payload.get("model_metric_values") or []
    direction_map = payload.get("metric_directions") or {}
    metrics: List[dict] = []
    for metric_name in payload.get("output_metrics") or []:
        ranking = next((item for item in rankings if item.get("metric") == metric_name), None)
        sorted_results = ranking.get("sorted_results") if isinstance(ranking, dict) else None
        if not sorted_results:
            continue
        best = next((item for item in sorted_results if item.get("value") is not None), None)
        worst = next((item for item in reversed(sorted_results) if item.get("value") is not None), None)
        avg_values = []
        for row in model_metric_values:
            metric_value = _safe_float((row.get("metrics") or {}).get(metric_name))
            if metric_value is not None:
                avg_values.append(metric_value)
        average = None if not avg_values else sum(avg_values) / len(avg_values)
        metrics.append(
            {
                "metric": metric_name,
                "direction": direction_map.get(metric_name, "lower_better"),
                "best_model": None if best is None else best.get("model_id"),
                "best_value": None if best is None else _safe_float(best.get("value")),
                "worst_model": None if worst is None else worst.get("model_id"),
                "worst_value": None if worst is None else _safe_float(worst.get("value")),
                "average_value": average,
            }
        )
    return metrics


def load_mechanism_overview() -> dict:
    root = mechanism_output_root()
    files = _mechanism_json_files()
    mechanisms: List[dict] = []
    model_ids = set()

    for path in files:
        payload = _load_json(path)
        if not payload:
            continue
        composite_results = ((payload.get("composite_ranking") or {}).get("sorted_results")) or []
        top_model = next((item for item in composite_results if item.get("value") is not None), None)
        mechanisms.append(
            {
                "mechanism_id": payload.get("mechanism_id") or path.stem,
                "mechanism_name": payload.get("mechanism_name") or path.stem,
                "module": payload.get("module") or "",
                "output_file": path.name,
                "metric_count": len(payload.get("output_metrics") or []),
                "model_count": len(payload.get("model_metric_values") or []),
                "top_model": None if top_model is None else top_model.get("model_id"),
                "top_score": None if top_model is None else _safe_float(top_model.get("value")),
                "metrics": _extract_metric_snapshot(payload),
            }
        )
        for row in payload.get("model_metric_values") or []:
            model_id = str(row.get("model_id") or "").strip()
            if model_id:
                model_ids.add(model_id)

    dashboard_path = mechanism_dashboard_path()
    generated_at = None
    if dashboard_path.exists():
        generated_at = dashboard_path.stat().st_mtime
    elif files:
        generated_at = max(path.stat().st_mtime for path in files)

    return {
        "available": bool(files),
        "output_root": str(root),
        "dashboard_available": dashboard_path.exists(),
        "dashboard_path": str(dashboard_path),
        "generated_at": generated_at,
        "mechanism_count": len(mechanisms),
        "model_count": len(model_ids),
        "mechanisms": mechanisms,
    }


def load_mechanism_leaderboard() -> dict:
    files = _mechanism_json_files()
    mechanisms_meta: List[dict] = []
    model_rows: Dict[str, dict] = {}

    for path in files:
        payload = _load_json(path)
        if not payload:
            continue
        mechanism_id = payload.get("mechanism_id") or path.stem
        mechanism_name = payload.get("mechanism_name") or path.stem
        composite_results = ((payload.get("composite_ranking") or {}).get("sorted_results")) or []
        mechanisms_meta.append(
            {
                "mechanism_id": mechanism_id,
                "mechanism_name": mechanism_name,
            }
        )

        rank_index = 0
        for item in composite_results:
            score = _safe_float(item.get("value"))
            if score is None:
                continue
            model_id = str(item.get("model_id") or "").strip()
            if not model_id:
                continue
            rank_index += 1
            row = model_rows.setdefault(
                model_id,
                {
                    "model_id": model_id,
                    "covered": 0,
                    "avg_rank": None,
                    "mechanism_ranks": {},
                },
            )
            row["mechanism_ranks"][mechanism_id] = {"rank": rank_index, "score": score}

    mechanism_ids = [item["mechanism_id"] for item in mechanisms_meta]
    rows: List[dict] = []
    for model_id, row in model_rows.items():
        rank_values = [entry["rank"] for entry in row["mechanism_ranks"].values() if isinstance(entry.get("rank"), int)]
        covered = len(rank_values)
        avg_rank = None if not rank_values else (sum(rank_values) / len(rank_values))
        completed_rank_map = {
            mechanism_id: row["mechanism_ranks"].get(mechanism_id, {"rank": None, "score": None})
            for mechanism_id in mechanism_ids
        }
        rows.append(
            {
                "model_id": model_id,
                "covered": covered,
                "avg_rank": avg_rank,
                "mechanism_ranks": completed_rank_map,
            }
        )

    rows.sort(
        key=lambda item: (
            item["avg_rank"] is None,
            9999 if item["avg_rank"] is None else item["avg_rank"],
            -item["covered"],
            item["model_id"],
        )
    )

    generated_at = None
    dashboard_path = mechanism_dashboard_path()
    if dashboard_path.exists():
        generated_at = dashboard_path.stat().st_mtime
    elif files:
        generated_at = max(path.stat().st_mtime for path in files)

    return {
        "available": bool(mechanisms_meta),
        "generated_at": generated_at,
        "mechanism_count": len(mechanisms_meta),
        "model_count": len(rows),
        "mechanisms": mechanisms_meta,
        "rows": rows,
    }


def load_mechanism_dashboard_html() -> Optional[str]:
    path = mechanism_dashboard_path()
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
