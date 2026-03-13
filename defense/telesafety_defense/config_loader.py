from dataclasses import dataclass
import os
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class RuntimeConfig:
    generation_config: Dict[str, Any]
    dataset_items: List[Dict[str, Any]]
    strict_exists: bool
    attack_types: List[str]
    attack_data_path: str
    target_model: str
    backend: str
    model_path: Optional[str]
    batch_size: int
    save_dir: str
    resume: bool
    checkpoint_every: int
    log_level: str
    api: Dict[str, Any]


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _pick(cfg: Dict[str, Any], section: str, key: str, default=None):
    nested = cfg.get(section, {})
    if isinstance(nested, dict) and key in nested:
        return nested.get(key)
    return cfg.get(key, default)


def _normalize_dataset_items(raw_items: Any) -> List[Dict[str, Any]]:
    if not raw_items:
        return []
    if not isinstance(raw_items, list):
        raise ValueError("dataset.items must be a list of objects.")

    items: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            raise ValueError(f"dataset.items[{idx}] must be an object.")
        path = raw.get("path") or raw.get("data_path")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"dataset.items[{idx}] must include non-empty 'path'.")
        item: Dict[str, Any] = {"path": path.strip()}
        for key in ("name", "query_field", "output_name", "save_path", "target_model"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                item[key] = value.strip()
        items.append(item)
    return items


def normalize_runtime_config(filter_config: Dict[str, Any], model_name_hint: Optional[str]) -> RuntimeConfig:
    generation_config = {
        "do_sample": _pick(filter_config, "generation", "do_sample", False),
        "max_new_tokens": _pick(filter_config, "generation", "max_new_tokens", 512),
        "temperature": _pick(filter_config, "generation", "temperature", 1.0),
    }

    dataset_items = _normalize_dataset_items(
        _pick(filter_config, "dataset", "items", _pick(filter_config, "", "dataset_items", []))
    )
    strict_exists = bool(
        _pick(filter_config, "dataset", "strict_exists", _pick(filter_config, "", "strict_exists", False))
    )
    attack_types = list(_pick(filter_config, "dataset", "attack_types", []) or [])
    attack_data_path = str(_pick(filter_config, "dataset", "attack_data_path", ""))
    target_model = str(
        _pick(filter_config, "dataset", "target_model", None)
        or model_name_hint
        or "vicuna-7b-v1.5"
    )
    backend = str(_pick(filter_config, "runtime", "backend", _pick(filter_config, "", "backend", "auto"))).lower()
    model_path = _pick(filter_config, "runtime", "model_path", _pick(filter_config, "", "model_path", None))
    if model_path in (None, ""):
        model_path_env = _pick(
            filter_config,
            "runtime",
            "model_path_env",
            _pick(filter_config, "", "model_path_env", None),
        )
        if isinstance(model_path_env, str) and model_path_env.strip():
            model_path = os.getenv(model_path_env.strip(), None)
    if model_path is not None:
        model_path = str(model_path)
    batch_size = int(_pick(filter_config, "runtime", "batch_size", _pick(filter_config, "", "batch_size", 4)))
    save_dir = str(_pick(filter_config, "output", "save_results_dir", _pick(filter_config, "", "save_results_dir", "./results")))
    resume = bool(_pick(filter_config, "runtime", "resume", _pick(filter_config, "", "resume", False)))
    checkpoint_every = int(_pick(filter_config, "runtime", "checkpoint_every", _pick(filter_config, "", "checkpoint_every", 0)) or 0)
    log_level = str(_pick(filter_config, "runtime", "log_level", _pick(filter_config, "", "log_level", "INFO")))

    api = {
        "provider": _pick(filter_config, "api", "provider", _pick(filter_config, "", "api_provider", "openai")),
        "base_url": _pick(filter_config, "api", "base_url", _pick(filter_config, "", "api_base_url", None)),
        "model_name": _pick(filter_config, "api", "model_name", _pick(filter_config, "", "api_model_name", None)),
        "key": _pick(filter_config, "api", "key", _pick(filter_config, "", "api_key", None)),
        "key_env": _pick(filter_config, "api", "key_env", _pick(filter_config, "", "api_key_env", None)),
        "timeout": int(_pick(filter_config, "api", "timeout", _pick(filter_config, "", "api_timeout", 120))),
        "api_version": _pick(filter_config, "api", "api_version", _pick(filter_config, "", "api_version", None)),
        "deployment": _pick(filter_config, "api", "deployment", _pick(filter_config, "", "api_deployment", None)),
        "allowed_defenders": _pick(
            filter_config,
            "api",
            "allowed_defenders",
            _pick(filter_config, "", "api_allowed_defenders", None),
        ),
    }

    return RuntimeConfig(
        generation_config=generation_config,
        dataset_items=dataset_items,
        strict_exists=strict_exists,
        attack_types=attack_types,
        attack_data_path=attack_data_path,
        target_model=target_model,
        backend=backend,
        model_path=model_path,
        batch_size=batch_size,
        save_dir=save_dir,
        resume=resume,
        checkpoint_every=checkpoint_every,
        log_level=log_level,
        api=api,
    )
