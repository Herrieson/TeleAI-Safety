from typing import Dict, Type

from benchmark.metrics.base import Metric


class MetricRegistry:
    _registry: Dict[str, Type[Metric]] = {}

    @classmethod
    def register(cls, name: str, metric_cls: Type[Metric]) -> None:
        cls._registry[name] = metric_cls

    @classmethod
    def create(cls, name: str, config: dict) -> Metric:
        if name not in cls._registry:
            raise ValueError(f"Unknown metric: {name}")
        return cls._registry[name](config)
