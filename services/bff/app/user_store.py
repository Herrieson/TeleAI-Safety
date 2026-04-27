import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Literal, Optional

from pydantic import BaseModel, Field


UserRole = Literal["admin", "user"]


class UserRecord(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password_hash: str
    role: UserRole = "user"
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class UserStore:
    def __init__(self, snapshot_path: Path):
        self._snapshot_path = snapshot_path
        self._lock = Lock()
        self._users: dict[str, UserRecord] = {}
        self._snapshot_mtime_ns: int | None = None
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self._snapshot_path.exists():
            self._users = {}
            self._snapshot_mtime_ns = None
            return
        try:
            stat = self._snapshot_path.stat()
        except OSError:
            return
        try:
            raw = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
        except Exception:
            return
        rows = raw.get("users") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            return

        loaded: dict[str, UserRecord] = {}
        for item in rows:
            try:
                user = UserRecord.model_validate(item)
            except Exception:
                continue
            loaded[user.username] = user
        self._users = loaded
        self._snapshot_mtime_ns = stat.st_mtime_ns

    def _reload_if_changed_locked(self) -> None:
        if not self._snapshot_path.exists():
            if self._users:
                self._users = {}
                self._snapshot_mtime_ns = None
            return
        try:
            stat = self._snapshot_path.stat()
        except OSError:
            return
        if self._snapshot_mtime_ns == stat.st_mtime_ns:
            return
        self._load_from_disk()

    def _persist_locked(self) -> None:
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "saved_at": datetime.utcnow().isoformat(),
            "users": [user.model_dump(mode="json") for user in self._users.values()],
        }
        temp_path = self._snapshot_path.with_suffix(self._snapshot_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self._snapshot_path)
        try:
            self._snapshot_mtime_ns = self._snapshot_path.stat().st_mtime_ns
        except OSError:
            self._snapshot_mtime_ns = None

    def get(self, username: str) -> Optional[UserRecord]:
        with self._lock:
            self._reload_if_changed_locked()
            return self._users.get(username)

    def upsert(self, *, username: str, password_hash: str, role: UserRole, enabled: bool = True) -> UserRecord:
        now = datetime.utcnow()
        with self._lock:
            existing = self._users.get(username)
            created_at = existing.created_at if existing is not None else now
            record = UserRecord(
                username=username,
                password_hash=password_hash,
                role=role,
                enabled=enabled,
                created_at=created_at,
                updated_at=now,
            )
            self._users[username] = record
            self._persist_locked()
            return record

    def set_enabled(self, username: str, enabled: bool) -> Optional[UserRecord]:
        with self._lock:
            existing = self._users.get(username)
            if existing is None:
                return None
            existing.enabled = enabled
            existing.updated_at = datetime.utcnow()
            self._users[username] = existing
            self._persist_locked()
            return existing


def normalize_username(value: str) -> str:
    return value.strip().lower()
