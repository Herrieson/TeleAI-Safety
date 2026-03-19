from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .config import settings


_CATALOG_PATH = Path(__file__).with_name("quick_dataset_catalog.yaml")


def list_quick_datasets() -> List[Dict[str, Any]]:
    raw = _load_catalog_yaml()
    rows = raw.get("datasets")
    if not isinstance(rows, list):
        return []

    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key", "")).strip()
        name = str(row.get("name", "")).strip()
        rel_path = str(row.get("path", "")).strip()
        desc = str(row.get("description", "")).strip()
        if not key or not name or not rel_path:
            continue
        resolved = _resolve_repo_path(rel_path)
        out.append(
            {
                "key": key,
                "name": name,
                "path": rel_path,
                "description": desc,
                "exists": resolved.exists(),
            }
        )
    return out


def resolve_quick_dataset_path(dataset_key: str) -> Tuple[Optional[str], str]:
    key = (dataset_key or "").strip()
    if not key:
        return None, "quick_dataset_key is required"

    catalog = list_quick_datasets()
    match = next((row for row in catalog if row.get("key") == key), None)
    if match is None:
        return None, f"unknown quick dataset key: {key}"

    path_raw = (match.get("path") or "").strip()
    path = _resolve_repo_path(path_raw)
    if not path.exists():
        return None, f"dataset path not found for key={key}: {path}"
    return str(path), ""


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return settings.repo_root / path


def _load_catalog_yaml() -> Dict:
    if not _CATALOG_PATH.exists():
        return {}
    try:
        with _CATALOG_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if isinstance(data, dict):
            return data
        return {}
    except OSError:
        return {}
