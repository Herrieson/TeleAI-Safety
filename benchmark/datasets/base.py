from abc import ABC, abstractmethod
from typing import Iterable

from benchmark.schemas import Sample


class DatasetAdapter(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def load(self) -> Iterable[Sample]:
        raise NotImplementedError

    def list_splits(self) -> list:
        return ["default"]

    def get_split(self, name: str) -> Iterable[Sample]:
        if name != "default":
            raise ValueError(f"Unknown split: {name}")
        return self.load()
