import json
from typing import Any, Dict, Optional
from urllib import error, request
from urllib.parse import quote

from fastapi import HTTPException

from .config import settings


def _call(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{settings.orchestrator_base_url}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, method=method, data=data, headers=headers)
    try:
        with request.urlopen(req, timeout=settings.timeout_seconds) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        detail = raw or str(exc)
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"orchestrator unreachable: {exc.reason}") from exc


def health() -> Any:
    return _call("GET", "/health")


def create_run(payload: Dict[str, Any]) -> Any:
    return _call("POST", "/v1/runs", payload=payload)


def list_runs() -> Any:
    return _call("GET", "/v1/runs")


def get_run(run_id: str) -> Any:
    return _call("GET", f"/v1/runs/{run_id}")


def cancel_run(run_id: str) -> Any:
    return _call("POST", f"/v1/runs/{run_id}/cancel")


def delete_run(run_id: str) -> Any:
    return _call("DELETE", f"/v1/runs/{run_id}")


def list_artifacts(run_id: str) -> Any:
    return _call("GET", f"/v1/runs/{run_id}/artifacts")


def get_logs(run_id: str, stage: str = "", tail_lines: int = 200) -> Any:
    path = f"/v1/runs/{run_id}/logs?tail_lines={tail_lines}"
    if stage:
        path += f"&stage={stage}"
    return _call("GET", path)


def get_metric_summary(run_id: str) -> Any:
    return _call("GET", f"/v1/runs/{run_id}/metrics/summary")


def get_metric_tasks(run_id: str) -> Any:
    return _call("GET", f"/v1/runs/{run_id}/metrics/tasks")


def export_metric_task_report(run_id: str, task_id: str) -> Any:
    encoded_task_id = quote(task_id, safe="")
    return _call("GET", f"/v1/runs/{run_id}/metrics/tasks/{encoded_task_id}/report")


def get_quick_attack_methods() -> Any:
    return _call("GET", "/v1/quick-attack/methods")


def get_quick_attack_datasets() -> Any:
    return _call("GET", "/v1/quick-attack/datasets")


def get_attack_config_options() -> Any:
    return _call("GET", "/v1/attack/config-options")


def get_benchmark_config_options() -> Any:
    return _call("GET", "/v1/benchmark/config-options")


def get_leaderboard() -> Any:
    return _call("GET", "/v1/leaderboard")


def get_managed_target_models() -> Any:
    return _call("GET", "/v1/managed-target-models")
