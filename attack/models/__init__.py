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
    model_name_lower = model_name.lower() if model_name else ""
    model_type_lower = model_type.lower() if model_type else ""

    # ✅ AzureOpenAI 模型处理
    if 'azure' in model_type_lower:
        print("Loading AzureModel...")
        if 'grok' in model_name_lower:
            print("Loading GrokModel...")
            return GrokModel(
                model_name=model_name,      
                base_url=config.grok_url,           
                api_key=config.grok_key,
                # generation_config=config.generation_config
            )
        else:
            return AzureOpenAIModel(
                model_name=model_name,       # 如 o1-preview / gpt-35-turbo
                base_url=config.azure_url,           # https://xxx.openai.azure.com/
                api_key=config.azure_key,
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
