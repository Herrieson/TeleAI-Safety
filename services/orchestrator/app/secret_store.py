from threading import Lock
from typing import Dict, Optional


class InMemorySecretStore:
    def __init__(self):
        self._items: Dict[str, Dict[str, str]] = {}
        self._lock = Lock()

    def set(self, run_id: str, secret: Dict[str, str]) -> None:
        with self._lock:
            self._items[run_id] = secret

    def get(self, run_id: str) -> Optional[Dict[str, str]]:
        with self._lock:
            return self._items.get(run_id)

    def pop(self, run_id: str) -> Optional[Dict[str, str]]:
        with self._lock:
            return self._items.pop(run_id, None)


secret_store = InMemorySecretStore()

