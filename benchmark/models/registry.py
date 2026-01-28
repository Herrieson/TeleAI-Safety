from typing import Dict, Type

from benchmark.models.base import ModelAdapter


class ModelRegistry:
    _registry: Dict[str, Type[ModelAdapter]] = {}

    @classmethod
    def register(cls, name: str, adapter_cls: Type[ModelAdapter]) -> None:
        cls._registry[name] = adapter_cls

    @classmethod
    def create(cls, name: str, config: dict) -> ModelAdapter:
        if name not in cls._registry:
            raise ValueError(f"Unknown model adapter: {name}")
        return cls._registry[name](config)
