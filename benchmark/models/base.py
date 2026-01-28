from abc import ABC, abstractmethod

from benchmark.schemas import ModelResponse


class ModelAdapter(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def generate(self, prompt: str) -> ModelResponse:
        raise NotImplementedError

    def batch_generate(self, prompts: list) -> list:
        return [self.generate(prompt) for prompt in prompts]
