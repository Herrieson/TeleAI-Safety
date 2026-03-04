import json
import os
from typing import Any, Dict, List, Optional, Tuple


IDENTITY_FIELDS = (
    "id",
    "sample_id",
    "uid",
    "final_query",
    "final_prompt",
    "rewritten",
    "query",
    "prompt",
)


def load_existing_results(save_path: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    if not save_path:
        return None
    if not os.path.exists(save_path):
        return None
    try:
        with open(save_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            return payload
    except Exception:
        return None
    return None


def _row_identity(row: Dict[str, Any]) -> Optional[str]:
    for key in IDENTITY_FIELDS:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return f"{key}:{text}"
    return None


def merge_existing_responses(
    data: List[Dict[str, Any]],
    existing: Optional[List[Dict[str, Any]]],
    *,
    response_field: str = "final_response",
) -> Tuple[List[Dict[str, Any]], int]:
    if not existing:
        return data, 0

    current_ids = [_row_identity(row) for row in data]
    existing_ids = [_row_identity(row) for row in existing]

    # Prefer identity-based restore to tolerate dataset reordering.
    if any(current_ids) and any(existing_ids):
        existing_map: Dict[str, Any] = {}
        duplicated = set()
        for row, row_id in zip(existing, existing_ids):
            if row_id is None or response_field not in row:
                continue
            if row_id in existing_map:
                duplicated.add(row_id)
                continue
            existing_map[row_id] = row[response_field]

        restored = 0
        merged: List[Dict[str, Any]] = []
        for current, row_id in zip(data, current_ids):
            row = dict(current)
            if row_id and row_id not in duplicated and row_id in existing_map:
                row[response_field] = existing_map[row_id]
                restored += 1
            merged.append(row)
        return merged, restored

    # Legacy fallback: index-based merge when we cannot build identities.
    if len(existing) != len(data):
        return data, 0

    restored = 0
    merged: List[Dict[str, Any]] = []
    for current, prev in zip(data, existing):
        row = dict(current)
        if response_field in prev:
            row[response_field] = prev[response_field]
            restored += 1
        merged.append(row)
    return merged, restored
