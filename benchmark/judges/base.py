from abc import ABC, abstractmethod

from benchmark.schemas import JudgeResult, Sample, ModelResponse


class Judge(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def score(self, sample: Sample, response: ModelResponse) -> JudgeResult:
        raise NotImplementedError
