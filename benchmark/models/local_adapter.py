from benchmark.models.base import ModelAdapter
from benchmark.schemas import ModelResponse


class LocalAdapter(ModelAdapter):
    def generate(self, prompt: str) -> ModelResponse:
        mode = self.config.get("mode", "echo")
        if mode == "echo":
            return ModelResponse(text=prompt, meta={"mode": mode})
        if mode == "static":
            text = self.config.get("text", "")
            return ModelResponse(text=text, meta={"mode": mode})
        raise ValueError(f"Unknown local adapter mode: {mode}")
