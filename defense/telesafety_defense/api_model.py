from typing import Any, Dict, Optional

from telesafety_defense.api_client import OpenAICompatibleChatClient


class OpenAICompatibleModel:
    """Minimal chat wrapper for OpenAI-compatible /chat/completions APIs."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str,
        generation_config: Optional[Dict[str, Any]] = None,
        timeout: int = 120,
        provider: str = "openai",
        api_version: Optional[str] = None,
        deployment: Optional[str] = None,
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = int(timeout)
        self.generation_config = dict(generation_config or {})
        self.provider = (provider or "openai").lower()
        self.api_version = api_version
        self.deployment = deployment
        self.client = OpenAICompatibleChatClient(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            provider=provider,
            api_version=api_version,
            deployment=deployment,
        )

    def chat(self, messages, **kwargs):
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        max_new_tokens = kwargs.get(
            "max_new_tokens", self.generation_config.get("max_new_tokens")
        )
        temperature = kwargs.get("temperature", self.generation_config.get("temperature"))
        top_p = kwargs.get("top_p", self.generation_config.get("top_p"))
        return self.client.chat(
            messages,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
        )
