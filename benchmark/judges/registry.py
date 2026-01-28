from typing import Dict, Type

from benchmark.judges.base import Judge


class JudgeRegistry:
    _registry: Dict[str, Type[Judge]] = {}

    @classmethod
    def register(cls, name: str, judge_cls: Type[Judge]) -> None:
        cls._registry[name] = judge_cls

    @classmethod
    def create(cls, name: str, config: dict) -> Judge:
        if name not in cls._registry:
            raise ValueError(f"Unknown judge: {name}")
        return cls._registry[name](config)
