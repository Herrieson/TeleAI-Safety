from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class RuntimeConfig:
    generation_config: Dict[str, Any]
    attack_types: List[str]
    attack_data_path: str
    target_model: str
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


def normalize_runtime_config(filter_config: Dict[str, Any], model_name_hint: Optional[str]) -> RuntimeConfig:
    generation_config = {
        "do_sample": _pick(filter_config, "generation", "do_sample", False),
        "max_new_tokens": _pick(filter_config, "generation", "max_new_tokens", 512),
        "temperature": _pick(filter_config, "generation", "temperature", 1.0),
    }

    attack_types = list(_pick(filter_config, "dataset", "attack_types", []) or [])
    attack_data_path = str(_pick(filter_config, "dataset", "attack_data_path", ""))
    target_model = str(
        _pick(filter_config, "dataset", "target_model", None)
        or model_name_hint
        or "vicuna-7b-v1.5"
    )
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
        attack_types=attack_types,
        attack_data_path=attack_data_path,
        target_model=target_model,
        batch_size=batch_size,
        save_dir=save_dir,
        resume=resume,
        checkpoint_every=checkpoint_every,
        log_level=log_level,
        api=api,
    )
