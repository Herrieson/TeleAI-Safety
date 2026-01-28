from benchmark.models.base import ModelAdapter
from benchmark.schemas import ModelResponse


class OpenAIAdapter(ModelAdapter):
    def __init__(self, config: dict):
        super().__init__(config)
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("openai package is required for OpenAIAdapter") from exc

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, prompt: str) -> ModelResponse:
        model = self.config.get("name")
        system_prompt = self.config.get("system_prompt")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self.config.get("temperature", 0),
            max_tokens=self.config.get("max_tokens", 1024),
        )
        text = response.choices[0].message.content
        return ModelResponse(text=text, raw={"response": response.model_dump()})
