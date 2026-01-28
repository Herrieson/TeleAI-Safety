from benchmark.models.base import ModelAdapter
from benchmark.models.registry import ModelRegistry
from benchmark.models.local_adapter import LocalAdapter
from benchmark.models.openai_adapter import OpenAIAdapter
from benchmark.models.azure_openai_adapter import AzureOpenAIAdapter

ModelRegistry.register("local", LocalAdapter)
ModelRegistry.register("openai", OpenAIAdapter)
ModelRegistry.register("azure_openai", AzureOpenAIAdapter)

__all__ = ["ModelAdapter", "ModelRegistry"]
