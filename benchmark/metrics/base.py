from abc import ABC, abstractmethod
from typing import List

from benchmark.schemas import JudgeResult, MetricResult


class Metric(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def compute(self, results: List[JudgeResult]) -> MetricResult:
        raise NotImplementedError
