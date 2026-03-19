from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, Query

from .config import settings
from .dataset_catalog import list_quick_datasets
from .executor import cancel_run_execution, delete_run_artifacts, list_quick_supported_methods, start_run_execution
from .models import RunCreate, RunRecord, new_run_record
from .secret_store import secret_store
from .store import run_store


app = FastAPI(title=settings.app_name, version=settings.app_version)


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


def _tail(path: Path, tail_lines: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if not lines:
        return ""
    return "\n".join(lines[-tail_lines:])


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
