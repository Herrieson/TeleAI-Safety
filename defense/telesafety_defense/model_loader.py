from typing import Dict, Optional

try:
    import torch
except ImportError:  # pragma: no cover - optional for API-only runs/tests
    torch = None  # type: ignore[assignment]
from transformers import AutoModelForCausalLM, AutoTokenizer

from telesafety_defense.api_model import OpenAICompatibleModel
from telesafety_defense.local_model import LocalModel


def load_model(
    model=None,
    tokenizer=None,
    model_name: str = "unknown",
    model_path: str = None,
    api_key: str = None,
    base_url: str = None,
    generation_config: Optional[Dict] = None,
    **kwargs,
):
    if model is not None and tokenizer is not None:
        return LocalModel(model, tokenizer, model_name, generation_config)

    if model_path:
        if not model:
            if torch is None:
                raise ImportError("torch is required to load local model_path backends.")
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True,
            ).eval()
        if not tokenizer:
            tokenizer = AutoTokenizer.from_pretrained(model_path, padding_side="left")
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
                tokenizer.pad_token_id = tokenizer.eos_token_id
        return LocalModel(model, tokenizer, model_name, generation_config)

    if api_key and base_url:
        return OpenAICompatibleModel(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            generation_config=generation_config,
            timeout=kwargs.get("timeout", 120),
            provider=kwargs.get("provider", "openai"),
            api_version=kwargs.get("api_version"),
            deployment=kwargs.get("deployment"),
        )

    raise ValueError("Must provide either model+tokenizer or model_path or api_key+base_url")
