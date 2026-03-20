import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

from .config import settings
from .models import ArtifactRecord, RunRecord, StageStatus


class InMemoryRunStore:
    def __init__(self, snapshot_path: Optional[Path] = None):
        self._runs: Dict[str, RunRecord] = {}
        self._lock = Lock()
        default_path = settings.run_log_root / "_state" / "runs_store.json"
        self._snapshot_path = snapshot_path or default_path
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        path = self._snapshot_path
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return

        rows = raw.get("runs") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            return

        loaded: Dict[str, RunRecord] = {}
        for item in rows:
            try:
                run = RunRecord.model_validate(item)
            except Exception:
                continue
            loaded[run.run_id] = run
        self._runs = loaded

    def _persist_locked(self) -> None:
        path = self._snapshot_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "saved_at": datetime.utcnow().isoformat(),
            "runs": [run.model_dump(mode="json") for run in self._runs.values()],
        }
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def add(self, run: RunRecord) -> RunRecord:
        with self._lock:
            self._runs[run.run_id] = run
            self._persist_locked()
            return run

    def get(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            return self._runs.get(run_id)

    def list_all(self) -> List[RunRecord]:
        with self._lock:
            rows = list(self._runs.values())
        return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def update_status(self, run_id: str, status: str, error: str = "") -> Optional[RunRecord]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            now = datetime.utcnow()
            run.status = status  # type: ignore[assignment]
            run.updated_at = now
            run.error = error
            if status in ("succeeded", "failed", "canceled"):
                run.ended_at = now
            self._runs[run_id] = run
            self._persist_locked()
            return run

    def update_stage(
        self,
        run_id: str,
        stage_name: str,
        status: StageStatus,
        *,
        command: Optional[str] = None,
        log_path: Optional[str] = None,
        exit_code: Optional[int] = None,
        error: Optional[str] = None,
    ) -> Optional[RunRecord]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            now = datetime.utcnow()
            for stage in run.stages:
                if stage.stage != stage_name:
                    continue
                if command is not None:
                    stage.command = command
                if log_path is not None:
                    stage.log_path = log_path
                if error is not None:
                    stage.error = error
                stage.status = status
                stage.updated_at = now
                if status == "running" and stage.started_at is None:
                    stage.started_at = now
                if status in ("succeeded", "failed", "canceled"):
                    stage.ended_at = now
                if exit_code is not None:
                    stage.exit_code = exit_code
                break
            run.updated_at = now
            self._runs[run_id] = run
            self._persist_locked()
            return run

    def cancel_running_stages(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            now = datetime.utcnow()
            for stage in run.stages:
                if stage.status == "running":
                    stage.status = "canceled"
                    stage.updated_at = now
                    stage.ended_at = now
                    if stage.error == "":
                        stage.error = "canceled by user"
            run.updated_at = now
            self._runs[run_id] = run
            self._persist_locked()
            return run

    def add_artifacts(self, run_id: str, artifacts: List[ArtifactRecord]) -> Optional[RunRecord]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            existing = {item.path for item in run.artifacts}
            for artifact in artifacts:
                if artifact.path in existing:
                    continue
                run.artifacts.append(artifact)
                existing.add(artifact.path)
            run.updated_at = datetime.utcnow()
            self._runs[run_id] = run
            self._persist_locked()
            return run

    def update_metric_summary(self, run_id: str, summary: dict) -> Optional[RunRecord]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            run.metric_summary = summary
            run.updated_at = datetime.utcnow()
            self._runs[run_id] = run
            self._persist_locked()
            return run

    def set_result_manifest(self, run_id: str, manifest_path: str) -> Optional[RunRecord]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            run.result_manifest = manifest_path
            run.updated_at = datetime.utcnow()
            self._runs[run_id] = run
            self._persist_locked()
            return run

    def update_attack_config_dir(self, run_id: str, attack_config_dir: str) -> Optional[RunRecord]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            run.attack_config_dir = attack_config_dir
            run.updated_at = datetime.utcnow()
            self._runs[run_id] = run
            self._persist_locked()
            return run

    def update_results_root(self, run_id: str, results_root: str) -> Optional[RunRecord]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            run.results_root = results_root
            run.updated_at = datetime.utcnow()
            self._runs[run_id] = run
            self._persist_locked()
            return run

    def delete(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            removed = self._runs.pop(run_id, None)
            self._persist_locked()
            return removed


run_store = InMemoryRunStore()
