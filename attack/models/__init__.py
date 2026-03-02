import os

from .openai_model import OpenAIModel
from .azure_openai_model import AzureOpenAIModel
from .grok_model import GrokModel
from .formatter import *

# Optional heavy deps
try:
    from .local_model import LocalModel  # noqa: F401
except Exception:
    LocalModel = None

try:
    from .vllm_model import VLLMModel  # noqa: F401
except Exception:
    VLLMModel = None


def load_model(model_type=None, model_name=None, model_path=None, config=None):
    if model_type is None:
        return None
    model_type_lower = model_type.lower() if model_type else ""

    # ✅ Grok API model (route by model_type, not model_name substring)
    if 'grok' in model_type_lower:
        print("Loading GrokModel...")
        grok_base_url = getattr(config, "grok_url", None) or getattr(config, "base_url", None)
        grok_api_key = getattr(config, "grok_key", None) or getattr(config, "api_key", None)
        if not grok_base_url:
            raise ValueError("Missing Grok endpoint. Set `grok_url` (or `base_url`).")
        if not grok_api_key:
            raise ValueError("Missing Grok API key. Set `grok_key` (or `api_key`).")
        return GrokModel(
            model_name=model_name,
            base_url=grok_base_url,
            api_key=grok_api_key,
        )

    # ✅ AzureOpenAI model
    if 'azure' in model_type_lower:
        print("Loading AzureModel...")
        azure_base_url = getattr(config, "azure_url", None)
        azure_api_key = getattr(config, "azure_key", None)
        if not azure_base_url or (isinstance(azure_base_url, str) and "${" in azure_base_url):
            raise ValueError("Missing Azure endpoint. Set `azure_url` or export AZURE_OPENAI_ENDPOINT.")
        if not azure_api_key or (isinstance(azure_api_key, str) and "${" in azure_api_key):
            raise ValueError("Missing Azure API key. Set `azure_key` or export AZURE_OPENAI_API_KEY.")

        api_version = getattr(config, "azure_api_version", None) or os.getenv("AZURE_OPENAI_API_VERSION") or "2024-12-01-preview"
        return AzureOpenAIModel(
            model_name=model_name,       # 如 o1-preview / gpt-35-turbo
            base_url=azure_base_url,     # https://xxx.openai.azure.com/
            api_key=azure_api_key,
            api_version=api_version,
            # generation_config=config.generation_config
        )
    # ✅ OpenAI 模型处理（API Key 模式）
    elif 'openai' in model_type_lower:
        print("Loading OpenAIModel...")
        return OpenAIModel(
            model_name=model_name,
            base_url=config.base_url,
            api_key=config.api_key,
            # generation_config=config.generation_config
        )
    # ✅ 默认使用 HuggingFace 本地模型
    else:
        if LocalModel is None:
            raise ImportError("LocalModel dependencies (e.g., transformers/fastchat/torch) are not installed.")
        print("Loading LocalModel...")
        from transformers import AutoModelForCausalLM, AutoTokenizer  # lazy import to keep optional
        import torch

        model = AutoModelForCausalLM.from_pretrained(model_path, device_map="auto").eval()
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            tokenizer.pad_token_id = tokenizer.eos_token_id
        torch.cuda.empty_cache()

        generation_config = None
        if config and hasattr(config, 'generation_config'):
            generation_config = config.generation_config
            print(f"Using generation config: {generation_config}")

        return LocalModel(model, tokenizer, model_name, generation_config)
