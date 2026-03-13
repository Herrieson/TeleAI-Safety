"""
Telesafety Defense Runner
=========================

Thin CLI entrypoint:
- loads configs
- builds runtime backend (local/API)
- dispatches evaluation engine per attack type
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, List

try:
    from loguru import logger
except ImportError:  # pragma: no cover - optional dependency fallback
    import logging

    class _StdLoggerAdapter:
        def __init__(self, name: str):
            self._logger = logging.getLogger(name)

        @staticmethod
        def _format(msg, *args):
            if not args:
                return msg
            try:
                return msg.format(*args)
            except Exception:
                return f"{msg} | args={args}"

        def info(self, msg, *args):
            self._logger.info(self._format(msg, *args))

        def warning(self, msg, *args):
            self._logger.warning(self._format(msg, *args))

        def error(self, msg, *args):
            self._logger.error(self._format(msg, *args))

    logger = _StdLoggerAdapter(__name__)

try:
    import torch
except ImportError:  # pragma: no cover - runtime fallback for API-only/lightweight environments
    class _TorchCompat:
        class cuda:
            @staticmethod
            def is_available() -> bool:
                return False

            @staticmethod
            def empty_cache() -> None:
                return None

    torch = _TorchCompat()  # type: ignore[assignment]

from telesafety_defense.defender_builder import create_defender_from_yaml
from telesafety_defense.backend_policy import (
    validate_api_defender_compatibility,
    validate_pipeline_model_requirement,
)
from telesafety_defense.base_factory import TrainingDefender
from telesafety_defense.config_loader import load_yaml, normalize_runtime_config


def _load_model(*args, **kwargs):
    from telesafety_defense.model_loader import load_model as _runtime_load_model

    return _runtime_load_model(*args, **kwargs)


def _normalize_backend_mode(raw_backend: str) -> str:
    mode = (raw_backend or "auto").strip().lower()
    if mode not in {"auto", "local", "api"}:
        raise ValueError(
            f"Unsupported runtime.backend='{raw_backend}'. "
            "Expected one of: auto, local, api."
        )
    return mode


def _resolve_pipeline_local_model_path(runtime_cfg, defender_config: dict) -> str | None:
    # Keep pipeline model explicit to avoid accidentally reusing method-private assets.
    return runtime_cfg.model_path or defender_config.get("model_path")


def _safe_stem(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in raw.strip())
    return safe or "dataset"


def _build_eval_jobs(runtime_cfg, defender_type: str) -> List[dict]:
    jobs: List[dict] = []

    if runtime_cfg.dataset_items:
        for idx, item in enumerate(runtime_cfg.dataset_items):
            data_path = item["path"]
            item_name = item.get("name") or Path(data_path).stem or f"dataset_{idx}"
            output_name = item.get("output_name") or item_name
            save_path = item.get("save_path")
            if not save_path:
                save_path = os.path.join(
                    runtime_cfg.save_dir,
                    f"{_safe_stem(output_name)}_{defender_type}.json",
                )
            jobs.append(
                {
                    "name": item_name,
                    "data_path": data_path,
                    "save_path": save_path,
                    "query_field": item.get("query_field"),
                }
            )
        return jobs

    for attack_type in runtime_cfg.attack_types:
        data_path = os.path.join(
            runtime_cfg.attack_data_path, f"{attack_type}_{runtime_cfg.target_model}.jsonl"
        )
        save_path = os.path.join(
            runtime_cfg.save_dir, f"{attack_type}_{runtime_cfg.target_model}_{defender_type}.json"
        )
        jobs.append(
            {
                "name": attack_type,
                "data_path": data_path,
                "save_path": save_path,
                "query_field": None,
            }
        )
    return jobs


def _build_model_and_defenders(defender, defender_config: dict, runtime_cfg):
    defenders: List[Any] = []
    model_ref = None
    tokenizer_ref = None
    model_name_hint = defender_config.get("model_name")
    defender_type = defender_config.get("defender_type")
    backend_mode = _normalize_backend_mode(runtime_cfg.backend)

    if isinstance(defender, TrainingDefender):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("Detected training defender. Running training before evaluation.")
        trained_model_path = defender.defend()
        logger.info("Training completed. Loading checkpoint from {}", trained_model_path)
        load_kwargs = {"device_map": "auto"} if torch.cuda.is_available() else {}
        model_ref = AutoModelForCausalLM.from_pretrained(trained_model_path, **load_kwargs).eval()
        tokenizer_ref = AutoTokenizer.from_pretrained(trained_model_path, padding_side="left")
        if tokenizer_ref.pad_token is None:
            tokenizer_ref.pad_token = tokenizer_ref.eos_token
            tokenizer_ref.pad_token_id = tokenizer_ref.eos_token_id
        model_name_hint = (
            defender_config.get("trained_model_name")
            or defender_config.get("model_name")
            or Path(trained_model_path).name
        )
    else:
        defenders = [defender]
        model_ref = getattr(defender, "model", None)
        tokenizer_ref = getattr(defender, "tokenizer", None)
        model_name_hint = getattr(defender, "model_name", model_name_hint)
        if model_ref is not None and hasattr(model_ref, "model") and hasattr(model_ref, "tokenizer"):
            if tokenizer_ref is None:
                tokenizer_ref = model_ref.tokenizer
            model_ref = model_ref.model

    if model_ref is not None and tokenizer_ref is not None:
        if tokenizer_ref.pad_token is None:
            tokenizer_ref.pad_token = tokenizer_ref.eos_token
            tokenizer_ref.pad_token_id = tokenizer_ref.eos_token_id
        model = _load_model(
            # model loader import is deferred to keep CLI import light.
            model=model_ref,
            tokenizer=tokenizer_ref,
            model_name=model_name_hint or "trained-model",
            generation_config=runtime_cfg.generation_config,
        )
        logger.info("Model wrapper created from defender's model and tokenizer")
        return model, defenders

    local_model_path = _resolve_pipeline_local_model_path(runtime_cfg, defender_config)
    if backend_mode in {"auto", "local"} and local_model_path:
        model = _load_model(
            model_name=model_name_hint or runtime_cfg.target_model,
            model_path=local_model_path,
            generation_config=runtime_cfg.generation_config,
        )
        logger.info("Using local model backend from model_path: {}", local_model_path)
        return model, defenders

    if backend_mode == "local":
        validate_pipeline_model_requirement(defender_type, model=None)
        logger.info(
            "runtime.backend=local with no pipeline model. Continuing because '{}' does not require it.",
            defender_type,
        )
        return None, defenders

    api_key = runtime_cfg.api.get("key")
    api_key_env = runtime_cfg.api.get("key_env")
    if not api_key and api_key_env:
        api_key = os.getenv(api_key_env)
    api_base_url = runtime_cfg.api.get("base_url")
    api_model_name = runtime_cfg.api.get("model_name") or runtime_cfg.target_model

    api_ready = bool(api_base_url and api_model_name and api_key)
    if api_ready:
        model = _load_model(
            model_name=api_model_name,
            api_key=api_key,
            base_url=api_base_url,
            generation_config=runtime_cfg.generation_config,
            timeout=runtime_cfg.api.get("timeout", 120),
            provider=runtime_cfg.api.get("provider", "openai"),
            api_version=runtime_cfg.api.get("api_version"),
            deployment=runtime_cfg.api.get("deployment"),
        )
        logger.info("Using API model backend: {}", api_model_name)
        validate_api_defender_compatibility(
            defenders,
            allowed_classes=runtime_cfg.api.get("allowed_defenders"),
            defender_type=defender_type,
            enforce_defender_api_support=True,
        )
        return model, defenders

    if backend_mode == "api":
        raise ValueError(
            "runtime.backend='api' but API settings are incomplete. "
            "Please set api.base_url/api.model_name/api.key (or api.key_env)."
        )

    # auto mode without local/API runtime backend: only valid for defenders that
    # can fully operate with native backends (e.g., CourtGuard detector/target backends).
    validate_pipeline_model_requirement(defender_type, model=None)
    logger.info(
        "No pipeline model backend resolved in auto mode. "
        "Continuing with defender-native backend for '{}'.",
        defender_type,
    )
    return None, defenders


def main():
    parser = argparse.ArgumentParser(description="Run Telesafety Defense")
    parser.add_argument("--defender_config", type=str, required=True, help="Path to defender YAML")
    parser.add_argument("--filter_config", type=str, required=True, help="Path to filter/config YAML")
    args = parser.parse_args()

    defender_config_path = args.defender_config
    filter_config_path = args.filter_config
    if not os.path.exists(defender_config_path):
        logger.error("Defender configuration file not found: {}", defender_config_path)
        return
    if not os.path.exists(filter_config_path):
        logger.error("Filter configuration file not found: {}", filter_config_path)
        return

    filter_config = load_yaml(filter_config_path)
    defender_config = load_yaml(defender_config_path)
    runtime_cfg = normalize_runtime_config(filter_config, defender_config.get("model_name"))

    if hasattr(logger, "remove") and hasattr(logger, "add"):
        logger.remove()
        logger.add(sys.stderr, level=runtime_cfg.log_level, format="{time} | {level} | {message}")
    else:  # stdlib logging fallback
        import logging

        logging.basicConfig(
            stream=sys.stderr,
            level=getattr(logging, runtime_cfg.log_level.upper(), logging.INFO),
            format="%(asctime)s | %(levelname)s | %(message)s",
        )
    logger.info("Loaded filter configuration from: {}", filter_config_path)
    logger.info("Loaded defender configuration from: {}", defender_config_path)

    defender = create_defender_from_yaml(defender_config_path)
    logger.info("Loaded defender type: {}", defender_config.get("defender_type"))

    model, defenders = _build_model_and_defenders(defender, defender_config, runtime_cfg)

    logger.info("Attack types: {}", runtime_cfg.attack_types)
    logger.info("Attack data path: {}", runtime_cfg.attack_data_path)
    logger.info("Configured dataset.items count: {}", len(runtime_cfg.dataset_items))
    logger.info("Dataset strict_exists: {}", runtime_cfg.strict_exists)
    logger.info("Target model: {}", runtime_cfg.target_model)
    logger.info("Runtime backend mode: {}", runtime_cfg.backend)
    logger.info("Runtime local model path: {}", runtime_cfg.model_path)
    logger.info("Batch size: {}", runtime_cfg.batch_size)
    logger.info("Save directory: {}", runtime_cfg.save_dir)
    logger.info("Resume enabled: {}", runtime_cfg.resume)
    logger.info("Checkpoint every: {}", runtime_cfg.checkpoint_every)

    defender_type = defender_config.get("defender_type")
    from telesafety_defense.engine import defend_chat

    jobs = _build_eval_jobs(runtime_cfg, defender_type=defender_type)
    if not jobs:
        logger.warning(
            "No evaluation jobs found. Configure dataset.items or attack_types in filter config."
        )
    for job in jobs:
        job_name = job["name"]
        data_path = job["data_path"]
        save_path = job["save_path"]
        query_field = job.get("query_field")

        logger.info("Processing dataset: {}", job_name)
        if not os.path.exists(data_path):
            if runtime_cfg.strict_exists:
                raise FileNotFoundError(f"Data file not found: {data_path}")
            logger.warning("Data file not found: {}", data_path)
            continue
        try:
            result = defend_chat(
                data_path=data_path,
                model=model,
                defenders=defenders,
                batch_size=runtime_cfg.batch_size,
                save_path=save_path,
                resume=runtime_cfg.resume,
                checkpoint_every=runtime_cfg.checkpoint_every,
                query_field=query_field,
            )
            logger.info("Successfully processed {}: {} queries", job_name, len(result["queries"]))
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as exc:
            logger.error("Error processing {}: {}", job_name, exc)
            continue

    logger.info("Defense processing completed!")


if __name__ == "__main__":
    if hasattr(logger, "remove") and hasattr(logger, "add"):
        logger.remove()
        logger.add(sys.stderr, level="INFO", format="{time} | {level} | {message}")
    main()
