from typing import Dict, Type

from benchmark.datasets.base import DatasetAdapter


class DatasetRegistry:
    _registry: Dict[str, Type[DatasetAdapter]] = {}

    @classmethod
    def register(cls, name: str, adapter_cls: Type[DatasetAdapter]) -> None:
        cls._registry[name] = adapter_cls

    @classmethod
    def create(cls, name: str, config: dict) -> DatasetAdapter:
        if name not in cls._registry:
            raise ValueError(f"Unknown dataset adapter: {name}")
        return cls._registry[name](config)
