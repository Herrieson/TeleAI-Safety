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

import torch
from loguru import logger
from transformers import AutoModelForCausalLM, AutoTokenizer

from telesafety_defense.defender_builder import create_defender_from_yaml
from telesafety_defense.backend_policy import validate_api_defender_compatibility
from telesafety_defense.base_factory import TrainingDefender
from telesafety_defense.config_loader import load_yaml, normalize_runtime_config
from telesafety_defense.engine import defend_chat
from telesafety_defense.model_loader import load_model


def _build_model_and_defenders(defender, defender_config: dict, runtime_cfg):
    defenders: List[Any] = []
    model_ref = None
    tokenizer_ref = None
    model_name_hint = defender_config.get("model_name")

    if isinstance(defender, TrainingDefender):
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
        model = load_model(
            model=model_ref,
            tokenizer=tokenizer_ref,
            model_name=model_name_hint or "trained-model",
            generation_config=runtime_cfg.generation_config,
        )
        logger.info("Model wrapper created from defender's model and tokenizer")
        return model, defenders

    api_key = runtime_cfg.api.get("key")
    api_key_env = runtime_cfg.api.get("key_env")
    if not api_key and api_key_env:
        api_key = os.getenv(api_key_env)
    api_base_url = runtime_cfg.api.get("base_url")
    api_model_name = runtime_cfg.api.get("model_name") or runtime_cfg.target_model

    if not (api_base_url and api_model_name and api_key):
        raise ValueError(
            "No local model/tokenizer found and API settings are incomplete. "
            "Please set api.base_url/api.model_name/api.key (or api.key_env)."
        )

    model = load_model(
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
        defender_type=defender_config.get("defender_type"),
    )
    return model, defenders


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

    logger.remove()
    logger.add(sys.stderr, level=runtime_cfg.log_level, format="{time} | {level} | {message}")
    logger.info("Loaded filter configuration from: {}", filter_config_path)
    logger.info("Loaded defender configuration from: {}", defender_config_path)

    defender = create_defender_from_yaml(defender_config_path)
    logger.info("Loaded defender type: {}", defender_config.get("defender_type"))

    model, defenders = _build_model_and_defenders(defender, defender_config, runtime_cfg)

    logger.info("Attack types: {}", runtime_cfg.attack_types)
    logger.info("Attack data path: {}", runtime_cfg.attack_data_path)
    logger.info("Target model: {}", runtime_cfg.target_model)
    logger.info("Batch size: {}", runtime_cfg.batch_size)
    logger.info("Save directory: {}", runtime_cfg.save_dir)
    logger.info("Resume enabled: {}", runtime_cfg.resume)
    logger.info("Checkpoint every: {}", runtime_cfg.checkpoint_every)

    defender_type = defender_config.get("defender_type")
    for attack_type in runtime_cfg.attack_types:
        logger.info("Processing attack type: {}", attack_type)
        data_path = os.path.join(
            runtime_cfg.attack_data_path, f"{attack_type}_{runtime_cfg.target_model}.jsonl"
        )
        if not os.path.exists(data_path):
            logger.warning("Data file not found: {}", data_path)
            continue
        save_path = os.path.join(
            runtime_cfg.save_dir, f"{attack_type}_{runtime_cfg.target_model}_{defender_type}.json"
        )
        try:
            result = defend_chat(
                data_path=data_path,
                model=model,
                defenders=defenders,
                batch_size=runtime_cfg.batch_size,
                save_path=save_path,
                resume=runtime_cfg.resume,
                checkpoint_every=runtime_cfg.checkpoint_every,
            )
            logger.info("Successfully processed {}: {} queries", attack_type, len(result["queries"]))
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as exc:
            logger.error("Error processing {}: {}", attack_type, exc)
            continue

    logger.info("Defense processing completed!")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time} | {level} | {message}")
    main()
