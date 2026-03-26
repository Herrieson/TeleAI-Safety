import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query

from .config import settings
from .dataset_catalog import list_quick_datasets
from .executor import cancel_run_execution, delete_run_artifacts, list_quick_supported_methods, start_run_execution
from .models import RunCreate, RunRecord, new_run_record
from .secret_store import secret_store
from .store import run_store


app = FastAPI(title=settings.app_name, version=settings.app_version)

LEADERBOARD_METRICS = [
    {"key": "asr", "label": "ASR", "better": "lower", "format": "percent", "precision": 4},
    {"key": "frr", "label": "FRR", "better": "lower", "format": "percent", "precision": 4},
    {"key": "mds", "label": "MDS", "better": "higher", "format": "number", "precision": 6},
    {"key": "bias", "label": "Bias", "better": "absolute_zero", "format": "number", "precision": 6},
    {"key": "wsl", "label": "WSL", "better": "lower", "format": "number", "precision": 6},
    {"key": "cm", "label": "CM", "better": "lower", "format": "number", "precision": 6},
    {"key": "code_ability", "label": "Code Ability", "better": "higher", "format": "number", "precision": 6},
    {"key": "hallucination", "label": "Hallucination", "better": "higher", "format": "number", "precision": 6},
]



@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "time": datetime.utcnow().isoformat(),
        "timezone": settings.timezone,
    }


@app.post("/v1/runs", response_model=RunRecord)
def create_run(payload: RunCreate) -> RunRecord:
    run = new_run_record(payload)
    created = run_store.add(run)
    if payload.quick_openai_api_key.strip():
        secret_store.set(
            created.run_id,
            {
                "quick_openai_api_key": payload.quick_openai_api_key.strip(),
            },
        )
    start_run_execution(created.run_id)
    return created


@app.get("/v1/runs", response_model=List[RunRecord])
def list_runs() -> List[RunRecord]:
    return run_store.list_all()


@app.get("/v1/runs/{run_id}", response_model=RunRecord)
def get_run(run_id: str) -> RunRecord:
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return run


@app.post("/v1/runs/{run_id}/cancel", response_model=RunRecord)
def cancel_run(run_id: str) -> RunRecord:
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    if run.status in ("succeeded", "failed", "canceled"):
        return run
    cancel_run_execution(run_id)
    run_store.cancel_running_stages(run_id)
    updated = run_store.update_status(run_id, "canceled", error="canceled by user")
    if updated is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return updated


@app.delete("/v1/runs/{run_id}")
def delete_run(run_id: str):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")

    cancel_run_execution(run_id)
    secret_store.pop(run_id)
    cleanup = delete_run_artifacts(run_id)
    deleted = run_store.delete(run_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return {
        "run_id": run_id,
        "deleted": True,
        **cleanup,
    }


@app.get("/v1/runs/{run_id}/artifacts")
def list_run_artifacts(run_id: str):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return {
        "run_id": run.run_id,
        "count": len(run.artifacts),
        "artifacts": run.artifacts,
    }


@app.get("/v1/runs/{run_id}/metrics/summary")
def get_metric_summary(run_id: str):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return {
        "run_id": run_id,
        "metric_summary": run.metric_summary,
    }


@app.get("/v1/runs/{run_id}/metrics/tasks")
def list_metric_tasks(run_id: str):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")

    tasks = _load_metric_tasks(run_id)
    return {
        "run_id": run_id,
        "count": len(tasks),
        "tasks": [_public_metric_task(row) for row in tasks],
    }


@app.get("/v1/runs/{run_id}/metrics/tasks/{task_id}/report")
def export_metric_task_report(run_id: str, task_id: str):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")

    tasks = _load_metric_tasks(run_id)
    selected = next((row for row in tasks if row["task_id"] == task_id), None)
    if selected is None:
        raise HTTPException(status_code=404, detail=f"metric task not found: {task_id}")

    report_content = _build_metric_task_report(run, selected)
    attack = _slugify(str(selected.get("attack_group") or "attack"), fallback="attack")
    scorer = _slugify(str(selected.get("scorer") or "scorer"), fallback="scorer")
    filename = f"eval-task-{run_id[:8]}-{attack}-{scorer}.md"

    return {
        "run_id": run_id,
        "task_id": task_id,
        "filename": filename,
        "content": report_content,
    }


@app.get("/v1/runs/{run_id}/logs")
def get_run_logs(
    run_id: str,
    stage: str = Query(default="", description="attack|benchmark|evaluate"),
    tail_lines: int = Query(default=200, ge=1, le=5000),
):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")

    selected = None
    if stage:
        for item in run.stages:
            if item.stage == stage:
                selected = item
                break
    if selected is None:
        for item in run.stages:
            if item.log_path:
                selected = item
                break

    if selected is None or not selected.log_path:
        return {"run_id": run_id, "stage": stage or "", "log_path": "", "content": ""}

    path = Path(selected.log_path)
    content = _tail(path, tail_lines) if path.exists() else ""
    return {
        "run_id": run_id,
        "stage": selected.stage,
        "log_path": selected.log_path,
        "content": content,
    }


def _run_eval_report_root(run_id: str) -> Path:
    return settings.repo_root / "evaluate" / "evaluation_report" / "runs" / run_id


def _eval_report_root() -> Path:
    return settings.repo_root / "evaluate" / "evaluation_report"


@app.get("/v1/leaderboard")
def get_leaderboard():
    source_path = _find_leaderboard_source_file()
    generated_at = datetime.utcnow().isoformat() + "Z"
    if source_path is None:
        return {
            "generated_at": generated_at,
            "source_csv": "",
            "source_updated_at": "",
            "model_count": 0,
            "metric_count": len(LEADERBOARD_METRICS),
            "metrics": _public_leaderboard_metrics(),
            "rows": [],
        }

    full_metrics_path = _leaderboard_full_csv_from_summary(source_path)
    asr_map = _compute_model_asr_aggregates(full_metrics_path)
    benchmark_map = _load_model_code_and_hallucination_scores()

    rows: List[Dict[str, object]] = []
    try:
        with source_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                record_type = (row.get("record_type") or "").strip().lower()
                if record_type != "model":
                    continue
                model = (row.get("model") or "").strip()
                if not model:
                    continue

                asr_ext = asr_map.get(model) or {}
                asr_effective = _to_float(asr_ext.get("asr_effective"))
                asr_strict = _to_float(row.get("avg_asr"))
                if asr_strict is None:
                    asr_strict = _to_float(asr_ext.get("asr_strict"))
                asr_legacy = _to_float(asr_ext.get("asr_legacy"))

                asr_values = [
                    value
                    for value in (asr_effective, asr_strict, asr_legacy)
                    if isinstance(value, (int, float))
                ]
                asr_value = _mean([float(value) for value in asr_values])

                benchmark_ext = benchmark_map.get(model) or {}

                metrics: Dict[str, Optional[float]] = {
                    "asr": asr_value,
                    "frr": _to_float(row.get("avg_frr")),
                    "mds": _to_float(row.get("mds")),
                    "bias": _to_float(row.get("bias")),
                    "wsl": _to_float(row.get("wsl")),
                    "cm": _to_float(row.get("cm")),
                    "code_ability": _to_float(benchmark_ext.get("code_ability")),
                    "hallucination": _to_float(benchmark_ext.get("hallucination")),
                    "asr_effective": asr_effective,
                    "asr_strict": asr_strict,
                    "asr_legacy": asr_legacy,
                }

                rows.append(
                    {
                        "model": model,
                        "metrics": metrics,
                    }
                )
    except OSError:
        rows = []

    rows.sort(key=lambda item: str(item.get("model") or ""))
    return {
        "generated_at": generated_at,
        "source_csv": _repo_relative_path(source_path),
        "source_updated_at": _file_updated_at(source_path),
        "model_count": len(rows),
        "metric_count": len(LEADERBOARD_METRICS),
        "metrics": _public_leaderboard_metrics(),
        "rows": rows,
    }



def _load_metric_tasks(run_id: str) -> List[Dict[str, object]]:
    eval_root = _run_eval_report_root(run_id)
    summary_path = eval_root / "asr" / "summary_long.csv"
    if not summary_path.exists() or not summary_path.is_file():
        return []

    rows: List[Dict[str, object]] = []
    try:
        with summary_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for idx, row in enumerate(reader, start=1):
                attack_group = (row.get("attack_group") or "").strip()
                scorer = (row.get("scorer") or "").strip()
                report_rel = (row.get("report_path") or "").strip()
                report_file = _safe_path_in_dir(eval_root / "asr", report_rel)
                input_file = (row.get("input_file") or "").strip()

                rows.append(
                    {
                        "task_id": str(idx),
                        "attack_run": (row.get("attack_run") or "").strip(),
                        "attack_group": attack_group,
                        "scorer": scorer,
                        "total_samples": _to_int(row.get("total_samples")),
                        "skipped_samples": _to_int(row.get("skipped_samples")),
                        "attack_success_samples": _to_int(row.get("attack_success_samples")),
                        "asr": _to_float(row.get("asr")),
                        "asr_strict": _to_float(row.get("asr_strict")),
                        "asr_effective": _to_float(row.get("asr_effective")),
                        "frr": _to_float(row.get("frr")),
                        "frr_invalid_rate": _to_float(row.get("frr_invalid_rate")),
                        "report_path": report_rel,
                        "input_file": input_file,
                        "_report_file": str(report_file) if report_file else "",
                        "_raw": row,
                        "_summary_path": str(summary_path),
                    }
                )
    except OSError:
        return []

    return rows


def _public_metric_task(task: Dict[str, object]) -> Dict[str, object]:
    return {
        "task_id": task.get("task_id") or "",
        "attack_run": task.get("attack_run") or "",
        "attack_group": task.get("attack_group") or "",
        "scorer": task.get("scorer") or "",
        "total_samples": task.get("total_samples"),
        "skipped_samples": task.get("skipped_samples"),
        "attack_success_samples": task.get("attack_success_samples"),
        "asr": task.get("asr"),
        "asr_strict": task.get("asr_strict"),
        "asr_effective": task.get("asr_effective"),
        "frr": task.get("frr"),
        "frr_invalid_rate": task.get("frr_invalid_rate"),
        "report_path": task.get("report_path") or "",
        "input_file": task.get("input_file") or "",
    }


def _build_metric_task_report(run: RunRecord, task: Dict[str, object]) -> str:
    now_text = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    summary_path = str(task.get("_summary_path") or "")
    report_file = str(task.get("_report_file") or "")
    report_detail = ""
    if report_file:
        try:
            report_detail = Path(report_file).read_text(encoding="utf-8", errors="replace")
        except OSError:
            report_detail = ""

    if len(report_detail) > 200000:
        report_detail = report_detail[:200000] + "\n\n...[truncated]"

    evaluate_log_path = ""
    for stage in run.stages:
        if stage.stage == "evaluate" and stage.log_path:
            evaluate_log_path = stage.log_path
            break

    task_payload = _public_metric_task(task)
    raw_row = task.get("_raw")

    lines = [
        "# Evaluation Task Report",
        "",
        f"- Generated at: {now_text}",
        f"- Run ID: {run.run_id}",
        f"- Run Name: {run.name}",
        f"- Task ID: {task_payload['task_id']}",
        f"- Mode: {run.mode}",
        f"- Eval Profile: {run.eval_profile or '-'}",
        "",
        "## Task Overview",
        "",
        f"- Attack Group: {task_payload['attack_group'] or '-'}",
        f"- Scorer: {task_payload['scorer'] or '-'}",
        f"- Attack Run: {task_payload['attack_run'] or '-'}",
        "",
        "## Key Metrics",
        "",
        f"- Total Samples: {task_payload['total_samples'] if task_payload['total_samples'] is not None else '-'}",
        f"- Skipped Samples: {task_payload['skipped_samples'] if task_payload['skipped_samples'] is not None else '-'}",
        f"- Attack Success Samples: {task_payload['attack_success_samples'] if task_payload['attack_success_samples'] is not None else '-'}",
        f"- ASR: {_format_metric(task_payload['asr'])}",
        f"- ASR Strict: {_format_metric(task_payload['asr_strict'])}",
        f"- ASR Effective: {_format_metric(task_payload['asr_effective'])}",
        f"- FRR: {_format_metric(task_payload['frr'])}",
        f"- FRR Invalid Rate: {_format_metric(task_payload['frr_invalid_rate'])}",
        "",
        "## Source Files",
        "",
        f"- summary_long.csv: {summary_path or '-'}",
        f"- per-task report: {report_file or '-'}",
        f"- input file: {task_payload['input_file'] or '-'}",
        f"- evaluate log: {evaluate_log_path or '-'}",
    ]

    if report_detail:
        lines.extend(
            [
                "",
                "## Detailed Output",
                "",
                "```text",
                report_detail,
                "```",
            ]
        )

    if isinstance(raw_row, dict):
        lines.extend(
            [
                "",
                "## Raw CSV Row",
                "",
                "```json",
                json.dumps(raw_row, ensure_ascii=False, indent=2),
                "```",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def _safe_path_in_dir(base: Path, rel_path: str) -> Optional[Path]:
    rel = (rel_path or "").strip()
    if not rel:
        return None
    root = base.resolve()
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def _to_int(value: Optional[str]) -> Optional[int]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _to_float(value: object) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _format_metric(value: object) -> str:
    if isinstance(value, (int, float)):
        row = float(value)
        if 0 <= row <= 1:
            return f"{row * 100:.2f}%"
        return f"{row:.6f}"
    return "-"


def _slugify(value: str, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z._-]+", "-", (value or "").strip()).strip("-._")
    return cleaned or fallback


def _tail(path: Path, tail_lines: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if not lines:
        return ""
    return "\n".join(lines[-tail_lines:])


def _find_leaderboard_source_file() -> Optional[Path]:
    report_root = _eval_report_root()
    preferred = report_root / "all_metrics_summary.csv"
    if preferred.exists() and preferred.is_file():
        return preferred

    run_root = report_root / "runs"
    if not run_root.exists() or not run_root.is_dir():
        return None

    candidates: List[Path] = []
    for path in run_root.glob("*/all_metrics_summary.csv"):
        if path.exists() and path.is_file():
            candidates.append(path)
    if not candidates:
        return None

    candidates.sort(key=lambda row: row.stat().st_mtime, reverse=True)
    return candidates[0]


def _leaderboard_full_csv_from_summary(summary_path: Path) -> Optional[Path]:
    full_path = summary_path.with_name("all_metrics_full.csv")
    if full_path.exists() and full_path.is_file():
        return full_path
    return None


def _mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _compute_model_asr_aggregates(full_metrics_path: Optional[Path]) -> Dict[str, Dict[str, Optional[float]]]:
    if full_metrics_path is None or not full_metrics_path.exists() or not full_metrics_path.is_file():
        return {}

    strict_map: Dict[str, List[float]] = {}
    effective_map: Dict[str, List[float]] = {}
    legacy_map: Dict[str, List[float]] = {}

    try:
        with full_metrics_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                model = (row.get("model") or row.get("attack_group") or "").strip()
                if not model:
                    continue

                strict = _to_float(row.get("ASR_avg_all_scorers"))
                effective = _to_float(row.get("ASR_effective_avg_all_scorers"))

                legacy_values: List[float] = []
                for key, value in row.items():
                    if not key.startswith("ASR_"):
                        continue
                    if "legacy" not in key.lower():
                        continue
                    parsed = _to_float(value)
                    if parsed is not None:
                        legacy_values.append(parsed)

                legacy = _mean(legacy_values)

                if strict is not None:
                    strict_map.setdefault(model, []).append(strict)
                if effective is not None:
                    effective_map.setdefault(model, []).append(effective)
                if legacy is not None:
                    legacy_map.setdefault(model, []).append(legacy)
    except OSError:
        return {}

    model_names = set(strict_map) | set(effective_map) | set(legacy_map)
    out: Dict[str, Dict[str, Optional[float]]] = {}
    for model in model_names:
        out[model] = {
            "asr_strict": _mean(strict_map.get(model, [])),
            "asr_effective": _mean(effective_map.get(model, [])),
            "asr_legacy": _mean(legacy_map.get(model, [])),
        }
    return out



def _load_benchmark_summary_overall(path: Path) -> Optional[float]:
    if not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return _to_float(payload.get("overall"))


def _load_model_code_and_hallucination_scores() -> Dict[str, Dict[str, Optional[float]]]:
    root = settings.repo_root / "benchmark" / "result" / "eval_from_result_auto"
    code_root = root / "code_merged"
    halluc_root = root / "hallucinations"

    code_scores: Dict[str, float] = {}
    if code_root.exists() and code_root.is_dir():
        for model_dir in sorted(code_root.iterdir()):
            if not model_dir.is_dir():
                continue
            overall = _load_benchmark_summary_overall(model_dir / "benchmark_summary.json")
            if overall is None:
                continue
            code_scores[model_dir.name] = overall

    hallucination_scores: Dict[str, float] = {}
    hallucination_parts = [
        "hallucinations_merged_law_text",
        "hallucinations_merged_legal_basics",
        "hallucinations_merged_scenario",
    ]
    if halluc_root.exists() and halluc_root.is_dir():
        for model_dir in sorted(halluc_root.iterdir()):
            if not model_dir.is_dir():
                continue
            values: List[float] = []
            for part in hallucination_parts:
                overall = _load_benchmark_summary_overall(model_dir / part / "benchmark_summary.json")
                if overall is not None:
                    values.append(overall)
            if values:
                hallucination_scores[model_dir.name] = sum(values)

    models = set(code_scores) | set(hallucination_scores)
    merged: Dict[str, Dict[str, Optional[float]]] = {}
    for model in models:
        merged[model] = {
            "code_ability": code_scores.get(model),
            "hallucination": hallucination_scores.get(model),
        }
    return merged


def _repo_relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(settings.repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _file_updated_at(path: Path) -> str:
    try:
        return datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z"
    except OSError:
        return ""


def _public_leaderboard_metrics() -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for spec in LEADERBOARD_METRICS:
        rows.append(
            {
                "key": spec["key"],
                "label": spec["label"],
                "better": spec["better"],
                "format": spec["format"],
                "precision": spec["precision"],
            }
        )
    return rows


@app.get("/v1/quick-attack/methods")
def get_quick_attack_methods():
    methods = list_quick_supported_methods()
    return {
        "count": len(methods),
        "methods": methods,
    }


@app.get("/v1/quick-attack/datasets")
def get_quick_attack_datasets():
    datasets = list_quick_datasets()
    return {
        "count": len(datasets),
        "datasets": datasets,
    }


@app.get("/v1/attack/config-options")
def get_attack_config_options():
    config_root = settings.repo_root / "attack" / "configs"
    directories: List[str] = []
    yaml_files: List[str] = []

    if config_root.exists() and config_root.is_dir():
        for path in sorted(config_root.rglob("*")):
            try:
                rel = path.relative_to(settings.repo_root / "attack").as_posix()
            except ValueError:
                continue
            if path.is_dir():
                if rel == "configs":
                    continue
                directories.append(rel)
                continue
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}:
                yaml_files.append(rel)

    return {
        "directory_count": len(directories),
        "yaml_file_count": len(yaml_files),
        "directories": directories,
        "yaml_files": yaml_files,
    }


@app.get("/v1/benchmark/config-options")
def get_benchmark_config_options():
    config_root = settings.repo_root / "benchmark" / "configs"
    run_root = config_root / "run"
    yaml_files: List[str] = []

    run_yaml = config_root / "run.yaml"
    if run_yaml.exists() and run_yaml.is_file():
        try:
            yaml_files.append(run_yaml.relative_to(settings.repo_root).as_posix())
        except ValueError:
            pass

    if run_root.exists() and run_root.is_dir():
        for path in sorted(run_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml"}:
                continue
            try:
                rel = path.relative_to(settings.repo_root).as_posix()
            except ValueError:
                continue
            yaml_files.append(rel)

    return {
        "yaml_file_count": len(yaml_files),
        "yaml_files": yaml_files,
    }
