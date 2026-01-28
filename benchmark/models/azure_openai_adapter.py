from benchmark.models.base import ModelAdapter
from benchmark.schemas import ModelResponse


class AzureOpenAIAdapter(ModelAdapter):
    def __init__(self, config: dict):
        super().__init__(config)
        try:
            from openai import AzureOpenAI
        except ImportError as exc:
            raise ImportError("openai package is required for AzureOpenAIAdapter") from exc

        self.client = AzureOpenAI(
            api_key=config.get("api_key"),
            azure_endpoint=config.get("azure_endpoint"),
            api_version=config.get("api_version"),
        )

    def generate(self, prompt: str) -> ModelResponse:
        deployment = self.config.get("deployment")
        system_prompt = self.config.get("system_prompt")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = self.client.chat.completions.create(
            model=deployment,
            messages=messages,
            temperature=self.config.get("temperature", 0),
            max_tokens=self.config.get("max_tokens", 1024),
        )
        text = response.choices[0].message.content
        return ModelResponse(text=text, raw={"response": response.model_dump()})
