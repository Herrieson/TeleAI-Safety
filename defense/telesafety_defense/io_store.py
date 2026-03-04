import json
import os
from typing import Any, Dict, List


def load_records(path: str) -> List[Dict[str, Any]]:
    if path.endswith(".jsonl"):
        with open(path, "r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]
    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValueError(f"JSON payload must be a list, got: {type(payload)}")
        return payload
    raise ValueError(f"Unsupported file format: {path}")


def save_records(path: str, data: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def extract_queries(data: List[Dict[str, Any]]) -> List[str]:
    queries = []
    for item in data:
        if "final_query" in item:
            queries.append(item["final_query"])
        elif "final_prompt" in item:
            queries.append(item["final_prompt"])
        elif "rewritten" in item:
            queries.append(item["rewritten"])
        else:
            queries.append("")
    return queries
