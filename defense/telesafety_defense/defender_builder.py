from pathlib import Path
import os
from typing import Any, Dict

import yaml
try:
    from loguru import logger
except ImportError:
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

from telesafety_defense.defender_registry import resolve_defender_class


def _load_trainer_config(config_source):
    if config_source is None:
        return {}
    if isinstance(config_source, str):
        with open(config_source, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    else:
        data = dict(config_source)
    if data.get("defender_type") == "BackdoorEnhancedAlignmentTrainer":
        data = {k: v for k, v in data.items() if k != "defender_type"}
    return data


def _prepare_backdooralign_assets(defender_params: Dict[str, Any]) -> Dict[str, Any]:
    train_if_missing = defender_params.pop("train_if_missing", False)
    trainer_cfg_inline = defender_params.pop("trainer", None)
    trainer_cfg_path = defender_params.pop("trainer_config_path", None)

    if not train_if_missing:
        return defender_params

    trainer_config = _load_trainer_config(trainer_cfg_path)
    if trainer_cfg_inline:
        trainer_config.update(trainer_cfg_inline)
    if not trainer_config:
        logger.warning("BackdoorAlign training requested but no trainer configuration provided.")
        return defender_params

    expected_model_path = defender_params.get("model") or trainer_config.get("output_dir")
    overwrite = bool(trainer_config.get("overwrite", False))
    model_missing = True
    if expected_model_path:
        model_missing = not Path(expected_model_path).exists()

    if overwrite or model_missing:
        trainer_cls = resolve_defender_class("BackdoorEnhancedAlignmentTrainer")
        trainer = trainer_cls(**trainer_config)
        trained_path = trainer.defend()
        defender_params["model"] = str(trained_path)
    else:
        defender_params["model"] = str(expected_model_path)
        logger.info("BackdoorAlign weights found at '{}'; skipping training.", expected_model_path)
    return defender_params


def _inject_hf_assets_if_needed(defender_type: str, defender_params: Dict[str, Any]) -> Dict[str, Any]:
    if "model" not in defender_params:
        return defender_params

    model_name = defender_params["model"]

    # Lazy import to keep module import light for test/runtime environments.
    import torch
    from transformers import AutoModelForCausalLM, AutoModelForSequenceClassification, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    try:
        if defender_type == "PromptGuard":
            model = AutoModelForSequenceClassification.from_pretrained(model_name).to(device)
        else:
            model = AutoModelForCausalLM.from_pretrained(model_name, device_map="auto")
    except Exception as exc:
        raise ValueError(f"Error loading model '{model_name}': {exc}") from exc

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side="left")
    except Exception as exc:
        raise ValueError(f"Error loading tokenizer for model '{model_name}': {exc}") from exc

    defender_params["model"] = model
    defender_params["tokenizer"] = tokenizer
    return defender_params


def _resolve_top_level_env_overrides(defender_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve top-level `*_env` entries by reading environment variables.
    Example:
      checkpoint_path_env: "JAILDAM_CHECKPOINT_PATH"
      -> checkpoint_path: os.getenv("JAILDAM_CHECKPOINT_PATH")
    """
    resolved = dict(defender_params)
    for key, env_name in list(defender_params.items()):
        if not key.endswith("_env"):
            continue
        if not isinstance(env_name, str) or not env_name.strip():
            continue
        value_key = key[: -len("_env")]
        current = resolved.get(value_key)
        if current is None or (isinstance(current, str) and current.strip() == ""):
            env_value = os.getenv(env_name.strip())
            if env_value not in (None, ""):
                resolved[value_key] = env_value
        # Top-level `*_env` is only for config resolution and should not be passed
        # into defender constructors unless explicitly supported in nested structures.
        resolved.pop(key, None)
    return resolved


def create_defender(defender_type: str, **kwargs):
    defender_class = resolve_defender_class(defender_type)
    try:
        return defender_class(**kwargs)
    except TypeError as exc:
        raise ValueError(f"Error creating defender: {exc}") from exc


def create_defender_from_config(config: Dict[str, Any]):
    defender_type = config.get("defender_type")
    if not defender_type:
        raise ValueError("YAML configuration must include 'defender_type'.")

    defender_params = {k: v for k, v in config.items() if k != "defender_type"}
    defender_params = _resolve_top_level_env_overrides(defender_params)
    if defender_type == "BackdoorEnhancedAlignment":
        defender_params = _prepare_backdooralign_assets(defender_params)
    defender_params = _inject_hf_assets_if_needed(defender_type, defender_params)
    return create_defender(defender_type, **defender_params)


def create_defender_from_yaml(yaml_path: str):
    try:
        with open(yaml_path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"YAML configuration file not found: {yaml_path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Error parsing YAML file: {exc}") from exc
    return create_defender_from_config(config)
