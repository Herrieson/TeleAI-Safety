from datetime import datetime
from threading import Lock
from time import monotonic

from fastapi import FastAPI, HTTPException, Query, Request
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
    get_managed_target_models as orchestrator_get_managed_target_models,
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


_managed_submit_lock = Lock()
_managed_last_submit_by_ip: dict[str, float] = {}


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


def _extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _count_active_managed_runs(runs: list[dict]) -> int:
    count = 0
    for row in runs:
        status = str(row.get("status") or "").strip().lower()
        if status not in {"pending", "running"}:
            continue
        managed_id = str(row.get("managed_target_model_id") or "").strip()
        if managed_id:
            count += 1
    return count


def _count_active_managed_runs_for_ip(runs: list[dict], ip: str) -> int:
    count = 0
    for row in runs:
        status = str(row.get("status") or "").strip().lower()
        if status not in {"pending", "running"}:
            continue
        managed_id = str(row.get("managed_target_model_id") or "").strip()
        requester_ip = str(row.get("requester_ip") or "").strip()
        if managed_id and requester_ip == ip:
            count += 1
    return count


def _is_ip_whitelisted(ip: str) -> bool:
    if not ip:
        return False
    return ip in settings.managed_mode_ip_whitelist


def _is_invite_code_valid(invite_code: str) -> bool:
    raw = (invite_code or "").strip()
    if not raw:
        return False
    return raw in settings.managed_mode_invite_codes


def _managed_access_policy(client_ip: str) -> dict:
    access_enabled = settings.managed_mode_access_control_enabled
    ip_whitelisted = _is_ip_whitelisted(client_ip)
    invite_code_required = access_enabled and (not ip_whitelisted) and bool(settings.managed_mode_invite_codes)
    return {
        "access_control_enabled": access_enabled,
        "ip_whitelisted": ip_whitelisted,
        "invite_code_required": invite_code_required,
    }


def _enforce_managed_access(*, client_ip: str, invite_code: str) -> None:
    if not settings.managed_mode_access_control_enabled:
        return
    if _is_ip_whitelisted(client_ip):
        return
    if settings.managed_mode_invite_codes and _is_invite_code_valid(invite_code):
        return
    if settings.managed_mode_invite_codes:
        raise HTTPException(
            status_code=403,
            detail="managed mode is restricted. Please provide a valid invite code or contact admin for whitelist access.",
        )
    raise HTTPException(
        status_code=403,
        detail="managed mode is restricted to admin whitelist clients.",
    )


def _enforce_managed_run_limits(*, client_ip: str) -> None:
    runs_payload = orchestrator_list_runs()
    if not isinstance(runs_payload, list):
        return

    active_managed = _count_active_managed_runs(runs_payload)
    if active_managed >= settings.managed_mode_max_active_runs_global:
        raise HTTPException(
            status_code=429,
            detail=(
                "managed mode is busy right now: active managed runs reached global limit "
                f"({settings.managed_mode_max_active_runs_global}). Please retry later."
            ),
        )

    active_for_ip = _count_active_managed_runs_for_ip(runs_payload, client_ip)
    if active_for_ip >= settings.managed_mode_max_active_runs_per_ip:
        raise HTTPException(
            status_code=429,
            detail=(
                "managed mode limit reached for current client: active managed runs per IP exceeded "
                f"({settings.managed_mode_max_active_runs_per_ip}). Please wait for existing runs to finish."
            ),
        )

    now = monotonic()
    with _managed_submit_lock:
        last_submit = _managed_last_submit_by_ip.get(client_ip, 0.0)
        elapsed = now - last_submit
        wait_seconds = settings.managed_mode_min_interval_seconds - elapsed
        if wait_seconds > 0:
            raise HTTPException(
                status_code=429,
                detail=(
                    "managed mode cooldown in effect. Please retry in "
                    f"{int(wait_seconds) + 1}s."
                ),
            )


@app.post("/api/runs")
def create_run(payload: RunCreateRequest, request: Request):
    client_ip = _extract_client_ip(request)
    payload_dict = payload.model_dump()
    payload_dict["requester_ip"] = client_ip
    payload_dict.pop("managed_access_code", None)

    is_managed_mode = bool(str(payload.managed_target_model_id or "").strip())
    if is_managed_mode:
        _enforce_managed_access(client_ip=client_ip, invite_code=payload.managed_access_code)
        _enforce_managed_run_limits(client_ip=client_ip)

    created = orchestrator_create_run(payload_dict)
    if is_managed_mode:
        with _managed_submit_lock:
            _managed_last_submit_by_ip[client_ip] = monotonic()
    return created


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


@app.get("/api/managed-target-models")
def get_managed_target_models(request: Request):
    client_ip = _extract_client_ip(request)
    access_policy = _managed_access_policy(client_ip)
    data = orchestrator_get_managed_target_models()
    if not isinstance(data, dict):
        data = {}
    data["policy"] = {
        "max_active_runs_global": settings.managed_mode_max_active_runs_global,
        "max_active_runs_per_ip": settings.managed_mode_max_active_runs_per_ip,
        "min_interval_seconds": settings.managed_mode_min_interval_seconds,
        **access_policy,
    }
    return data


@app.get("/api/attack/config-options")
def get_attack_config_options():
    return orchestrator_get_attack_config_options()


@app.get("/api/benchmark/config-options")
def get_benchmark_config_options():
    return orchestrator_get_benchmark_config_options()
