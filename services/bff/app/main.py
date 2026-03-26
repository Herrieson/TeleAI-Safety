from datetime import datetime

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .orchestrator_client import (
    get_attack_config_options as orchestrator_get_attack_config_options,
    get_benchmark_config_options as orchestrator_get_benchmark_config_options,
    cancel_run as orchestrator_cancel_run,
    create_run as orchestrator_create_run,
    delete_run as orchestrator_delete_run,
    export_metric_task_report as orchestrator_export_metric_task_report,
    get_logs as orchestrator_get_logs,
    get_metric_summary as orchestrator_get_metric_summary,
    get_metric_tasks as orchestrator_get_metric_tasks,
    get_leaderboard as orchestrator_get_leaderboard,
    get_quick_attack_datasets as orchestrator_get_quick_attack_datasets,
    get_quick_attack_methods as orchestrator_get_quick_attack_methods,
    get_run as orchestrator_get_run,
    health as orchestrator_health,
    list_artifacts as orchestrator_list_artifacts,
    list_runs as orchestrator_list_runs,
)
from .schemas import RunCreateRequest


app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "time": datetime.utcnow().isoformat(),
    }


@app.get("/api/health")
def api_health() -> dict:
    upstream = orchestrator_health()
    return {
        "status": "ok",
        "service": settings.app_name,
        "orchestrator": upstream,
    }


@app.post("/api/runs")
def create_run(payload: RunCreateRequest):
    return orchestrator_create_run(payload.model_dump())


@app.get("/api/runs")
def list_runs():
    return orchestrator_list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return orchestrator_get_run(run_id)


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    return orchestrator_cancel_run(run_id)


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str):
    return orchestrator_delete_run(run_id)


@app.get("/api/runs/{run_id}/artifacts")
def list_artifacts(run_id: str):
    return orchestrator_list_artifacts(run_id)


@app.get("/api/runs/{run_id}/logs")
def get_logs(
    run_id: str,
    stage: str = Query(default=""),
    tail_lines: int = Query(default=200, ge=1, le=5000),
):
    return orchestrator_get_logs(run_id=run_id, stage=stage, tail_lines=tail_lines)


@app.get("/api/runs/{run_id}/metrics/summary")
def get_metric_summary(run_id: str):
    return orchestrator_get_metric_summary(run_id)


@app.get("/api/runs/{run_id}/metrics/tasks")
def get_metric_tasks(run_id: str):
    return orchestrator_get_metric_tasks(run_id)


@app.get("/api/runs/{run_id}/metrics/tasks/{task_id}/report")
def export_metric_task_report(run_id: str, task_id: str):
    return orchestrator_export_metric_task_report(run_id, task_id)


@app.get("/api/leaderboard")
def get_leaderboard():
    return orchestrator_get_leaderboard()


@app.get("/api/quick-attack/methods")
def get_quick_attack_methods():
    return orchestrator_get_quick_attack_methods()


@app.get("/api/quick-attack/datasets")
def get_quick_attack_datasets():
    return orchestrator_get_quick_attack_datasets()


@app.get("/api/attack/config-options")
def get_attack_config_options():
    return orchestrator_get_attack_config_options()


@app.get("/api/benchmark/config-options")
def get_benchmark_config_options():
    return orchestrator_get_benchmark_config_options()
