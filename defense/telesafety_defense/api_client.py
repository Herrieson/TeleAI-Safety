import json
import urllib.request
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from typing import Any, Dict, Optional


class OpenAICompatibleChatClient:
    """HTTP client for OpenAI-compatible chat-completions providers."""

    def __init__(
        self,
        *,
        model_name: str,
        api_key: str,
        base_url: str,
        timeout: int = 120,
        provider: str = "openai",
        api_version: Optional[str] = None,
        deployment: Optional[str] = None,
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = int(timeout)
        self.provider = (provider or "openai").lower()
        self.api_version = api_version
        self.deployment = deployment

    def _append_api_version(self, url: str) -> str:
        if not self.api_version:
            return url
        parsed = urlparse(url)
        query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_items.setdefault("api-version", self.api_version)
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query_items), parsed.fragment)
        )

    def chat_url(self) -> str:
        if self.provider == "azure":
            if self.base_url.endswith("/chat/completions"):
                return self._append_api_version(self.base_url)
            if self.deployment:
                base = self.base_url.rstrip("/")
                url = f"{base}/openai/deployments/{self.deployment}/chat/completions"
                return self._append_api_version(url)
            raise ValueError(
                "Azure provider requires either base_url ending with '/chat/completions' "
                "or deployment configured via 'api_deployment'."
            )
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.provider == "azure":
            headers["api-key"] = self.api_key
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def request_payload(
        self,
        messages,
        *,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"messages": messages}
        if self.provider != "azure":
            payload["model"] = self.model_name
        if max_new_tokens is not None:
            payload["max_tokens"] = int(max_new_tokens)
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if top_p is not None:
            payload["top_p"] = float(top_p)
        return payload

    def chat(
        self,
        messages,
        *,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> str:
        payload = self.request_payload(
            messages,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        request = urllib.request.Request(
            self.chat_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers=self.headers(),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        choices = body.get("choices", [])
        if not choices:
            raise ValueError(f"Invalid API response, missing choices: {body}")
        message = choices[0].get("message", {})
        content = message.get("content")
        if content is None:
            raise ValueError(f"Invalid API response, missing message content: {body}")
        return content
