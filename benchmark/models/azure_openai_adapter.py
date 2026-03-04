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
        self._token_param = self.config.get("token_param", "max_tokens")
        self._use_temperature = "temperature" in self.config

    def generate(self, prompt: str) -> ModelResponse:
        deployment = self.config.get("deployment")
        system_prompt = self.config.get("system_prompt")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        token_limit = self.config.get("max_tokens", 1024)
        token_param = self._token_param
        temperature = self.config.get("temperature")
        request_kwargs = {
            "model": deployment,
            "messages": messages,
            token_param: token_limit,
        }
        if self._use_temperature and temperature is not None:
            request_kwargs["temperature"] = temperature

        for _ in range(3):
            try:
                response = self.client.chat.completions.create(**request_kwargs)
                break
            except Exception as exc:
                err_msg = str(exc)
                # Some reasoning models reject `max_tokens` and require `max_completion_tokens`.
                if token_param == "max_tokens" and "max_completion_tokens" in err_msg:
                    request_kwargs.pop("max_tokens", None)
                    request_kwargs["max_completion_tokens"] = token_limit
                    self._token_param = "max_completion_tokens"
                    token_param = "max_completion_tokens"
                    continue
                if token_param == "max_completion_tokens" and "max_tokens" in err_msg:
                    request_kwargs.pop("max_completion_tokens", None)
                    request_kwargs["max_tokens"] = token_limit
                    self._token_param = "max_tokens"
                    token_param = "max_tokens"
                    continue
                # Some models only allow default temperature; retry without temperature.
                if "temperature" in request_kwargs and "temperature" in err_msg:
                    request_kwargs.pop("temperature", None)
                    self._use_temperature = False
                    continue
                raise
        else:
            raise RuntimeError("Failed to create chat completion after compatibility retries.")
        text = response.choices[0].message.content
        return ModelResponse(text=text, raw={"response": response.model_dump()})
