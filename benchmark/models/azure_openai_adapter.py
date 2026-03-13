import json
import os
import threading

from benchmark.models.base import ModelAdapter
from benchmark.schemas import ModelResponse


class AzureOpenAIAdapter(ModelAdapter):
    _API_MODE_CHAT = "chat_completions"
    _API_MODE_RESPONSES = "responses"

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
        self._azure_endpoint = config.get("azure_endpoint") or ""
        self._api_version = config.get("api_version") or ""

        configured_token_param = self.config.get("token_param")
        self._token_params_by_mode = {
            self._API_MODE_CHAT: self.config.get(
                "chat_token_param", configured_token_param or "max_tokens"
            ),
            self._API_MODE_RESPONSES: self.config.get(
                "responses_token_param", configured_token_param or "max_output_tokens"
            ),
        }
        self._use_temperature = "temperature" in self.config
        self._api_mode = self._normalize_api_mode(self.config.get("api_mode", "auto"))
        self._strict_api_mode = bool(self.config.get("strict_api_mode", False))
        self._api_fallback_order = self._normalize_api_fallback_order(
            self.config.get("api_fallback_order")
        )
        self._active_api_mode = None
        self._probe_max_tokens = int(self.config.get("api_probe_max_tokens", 1))
        self._probe_text = self.config.get("api_probe_text", "ping")
        default_cache_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".cache", "api_route_cache.json"
        )
        self._api_route_cache_path = self.config.get(
            "api_route_cache_path", default_cache_path
        )
        self._route_cache_lock = threading.Lock()
        self._route_probe_lock = threading.Lock()
        self._route_cache = self._load_route_cache()

    def generate(self, prompt: str) -> ModelResponse:
        deployment = self.config.get("deployment")
        if not deployment:
            raise ValueError("Azure deployment is required")

        system_prompt = self.config.get("system_prompt")
        route_source = "config"
        if self._api_mode == "auto":
            preferred_mode, route_source = self._resolve_preferred_api_mode(deployment)
            if preferred_mode:
                self._active_api_mode = preferred_mode

        candidate_api_modes = self._candidate_api_modes()
        attempted = []
        errors = []

        for index, api_mode in enumerate(candidate_api_modes):
            try:
                response, token_param = self._generate_with_mode(
                    api_mode=api_mode,
                    model=deployment,
                    prompt=prompt,
                    system_prompt=system_prompt,
                )
                self._active_api_mode = api_mode
                attempted.append(api_mode)
                self._set_cached_api_mode(deployment, api_mode)
                text = self._extract_text(api_mode, response)
                meta = {
                    "api_mode_used": api_mode,
                    "token_param_used": token_param,
                    "api_modes_attempted": attempted,
                    "fallback_count": max(0, len(attempted) - 1),
                    "api_route_source": route_source,
                }
                return ModelResponse(
                    text=text,
                    raw={"response": self._safe_model_dump(response)},
                    meta=meta,
                )
            except Exception as exc:
                attempted.append(api_mode)
                errors.append(f"{api_mode}: {exc}")
                if self._should_fallback_api_mode(exc):
                    self._invalidate_cached_api_mode(deployment, api_mode)
                if index < len(candidate_api_modes) - 1 and self._should_fallback_api_mode(exc):
                    continue
                raise

        raise RuntimeError(
            "Failed to generate model response after API compatibility retries: "
            + " | ".join(errors)
        )

    def _generate_with_mode(self, api_mode: str, model: str, prompt: str, system_prompt: str):
        if api_mode == self._API_MODE_CHAT:
            return self._generate_chat_completion(model, prompt, system_prompt)
        if api_mode == self._API_MODE_RESPONSES:
            return self._generate_responses(model, prompt, system_prompt)
        raise ValueError(f"Unsupported api_mode: {api_mode}")

    def _resolve_preferred_api_mode(self, model: str):
        cached_mode = self._get_cached_api_mode(model)
        if cached_mode:
            return cached_mode, "cache"
        if self._active_api_mode:
            return self._active_api_mode, "memory"
        with self._route_probe_lock:
            cached_mode = self._get_cached_api_mode(model)
            if cached_mode:
                return cached_mode, "cache"
            probed_mode = self._probe_api_mode(model)
            if probed_mode:
                self._set_cached_api_mode(model, probed_mode)
                return probed_mode, "probe"
            return None, "fallback_order"

    def _probe_api_mode(self, model: str):
        for api_mode in self._api_fallback_order:
            try:
                self._probe_with_mode(api_mode, model)
                return api_mode
            except Exception as exc:
                if self._should_fallback_api_mode(exc):
                    continue
                if self._is_token_param_error(str(exc)):
                    continue
                # Probe is best-effort. Non-routing errors should be surfaced by normal generate.
                return None
        return None

    def _probe_with_mode(self, api_mode: str, model: str):
        if api_mode == self._API_MODE_CHAT:
            return self._probe_chat_completion(model)
        if api_mode == self._API_MODE_RESPONSES:
            return self._probe_responses(model)
        raise ValueError(f"Unsupported api_mode: {api_mode}")

    def _probe_chat_completion(self, model: str):
        messages = [{"role": "user", "content": self._probe_text}]
        token_limit = self._probe_max_tokens
        token_candidates = self._token_param_candidates(self._API_MODE_CHAT)
        last_exc = None

        for token_param in token_candidates:
            request_kwargs = {
                "model": model,
                "messages": messages,
                token_param: token_limit,
            }
            try:
                self.client.chat.completions.create(**request_kwargs)
                self._token_params_by_mode[self._API_MODE_CHAT] = token_param
                return
            except Exception as exc:
                last_exc = exc
                if self._is_token_param_error(str(exc)):
                    continue
                raise
        if last_exc is not None:
            raise last_exc

    def _probe_responses(self, model: str):
        token_limit = self._probe_max_tokens
        token_candidates = self._token_param_candidates(self._API_MODE_RESPONSES)
        last_exc = None

        for token_param in token_candidates:
            request_kwargs = {
                "model": model,
                "input": self._probe_text,
                token_param: token_limit,
            }
            try:
                self.client.responses.create(**request_kwargs)
                self._token_params_by_mode[self._API_MODE_RESPONSES] = token_param
                return
            except Exception as exc:
                last_exc = exc
                if self._is_token_param_error(str(exc)):
                    continue
                raise
        if last_exc is not None:
            raise last_exc

    def _generate_chat_completion(self, model: str, prompt: str, system_prompt: str):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        token_limit = self.config.get("max_tokens", 1024)
        temperature = self.config.get("temperature")
        token_candidates = self._token_param_candidates(self._API_MODE_CHAT)
        last_exc = None

        for token_param in token_candidates:
            request_kwargs = {
                "model": model,
                "messages": messages,
                token_param: token_limit,
            }
            if self._use_temperature and temperature is not None:
                request_kwargs["temperature"] = temperature

            while True:
                try:
                    response = self.client.chat.completions.create(**request_kwargs)
                    self._token_params_by_mode[self._API_MODE_CHAT] = token_param
                    return response, token_param
                except Exception as exc:
                    last_exc = exc
                    err_msg = str(exc)
                    if "temperature" in request_kwargs and self._is_temperature_error(err_msg):
                        request_kwargs.pop("temperature", None)
                        self._use_temperature = False
                        continue
                    if self._is_token_param_error(err_msg):
                        break
                    raise

        raise RuntimeError(
            "Failed to create chat completion after token compatibility retries."
        ) from last_exc

    def _generate_responses(self, model: str, prompt: str, system_prompt: str):
        token_limit = self.config.get("max_tokens", 1024)
        temperature = self.config.get("temperature")
        token_candidates = self._token_param_candidates(self._API_MODE_RESPONSES)
        last_exc = None

        for token_param in token_candidates:
            request_kwargs = {
                "model": model,
                "input": prompt,
                token_param: token_limit,
            }
            if system_prompt:
                request_kwargs["instructions"] = system_prompt
            if self._use_temperature and temperature is not None:
                request_kwargs["temperature"] = temperature

            while True:
                try:
                    response = self.client.responses.create(**request_kwargs)
                    self._token_params_by_mode[self._API_MODE_RESPONSES] = token_param
                    return response, token_param
                except Exception as exc:
                    last_exc = exc
                    err_msg = str(exc)
                    if "temperature" in request_kwargs and self._is_temperature_error(err_msg):
                        request_kwargs.pop("temperature", None)
                        self._use_temperature = False
                        continue
                    if self._is_token_param_error(err_msg):
                        break
                    raise

        raise RuntimeError("Failed to create response after token compatibility retries.") from last_exc

    def _extract_text(self, api_mode: str, response) -> str:
        if api_mode == self._API_MODE_CHAT:
            return self._extract_chat_text(response)
        return self._extract_response_text(response)

    def _extract_chat_text(self, response) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        if message is None:
            return ""
        content = getattr(message, "content", "")
        return self._flatten_content(content)

    def _extract_response_text(self, response) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text:
            return output_text

        output = getattr(response, "output", None)
        if not isinstance(output, list):
            return ""

        parts = []
        for item in output:
            if isinstance(item, dict):
                content_items = item.get("content", [])
            else:
                content_items = getattr(item, "content", [])
            if not isinstance(content_items, list):
                continue
            for content in content_items:
                if isinstance(content, dict):
                    content_type = content.get("type")
                    text = content.get("text")
                else:
                    content_type = getattr(content, "type", None)
                    text = getattr(content, "text", None)
                if content_type in {"output_text", "text"}:
                    if isinstance(text, dict):
                        text = text.get("value")
                    elif text is not None and not isinstance(text, str):
                        text = getattr(text, "value", None) or str(text)
                    if isinstance(text, str) and text:
                        parts.append(text)
        return "".join(parts)

    def _flatten_content(self, content) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return "" if content is None else str(content)
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
            else:
                text = getattr(item, "text", None)
            if isinstance(text, dict):
                text = text.get("value")
            elif text is not None and not isinstance(text, str):
                text = getattr(text, "value", None) or str(text)
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)

    def _safe_model_dump(self, response):
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if hasattr(response, "to_dict"):
            return response.to_dict()
        return {"repr": repr(response)}

    def _build_route_cache_key(self, model: str) -> str:
        return f"azure_openai|{self._azure_endpoint}|{self._api_version}|{model}"

    def _get_cached_api_mode(self, model: str):
        cache_key = self._build_route_cache_key(model)
        with self._route_cache_lock:
            mode = self._route_cache.get(cache_key)
        if mode not in {self._API_MODE_CHAT, self._API_MODE_RESPONSES}:
            return None
        return mode

    def _set_cached_api_mode(self, model: str, mode: str) -> None:
        if self._api_mode != "auto":
            return
        if mode not in {self._API_MODE_CHAT, self._API_MODE_RESPONSES}:
            return
        cache_key = self._build_route_cache_key(model)
        with self._route_cache_lock:
            if self._route_cache.get(cache_key) == mode:
                return
            self._route_cache[cache_key] = mode
            self._persist_route_cache_locked()

    def _invalidate_cached_api_mode(self, model: str, failed_mode: str = None) -> None:
        if self._api_mode != "auto":
            return
        cache_key = self._build_route_cache_key(model)
        with self._route_cache_lock:
            cached_mode = self._route_cache.get(cache_key)
            if cached_mode is None:
                return
            if failed_mode and cached_mode != failed_mode:
                return
            self._route_cache.pop(cache_key, None)
            self._persist_route_cache_locked()

    def _load_route_cache(self):
        path = self._api_route_cache_path
        if not path:
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            parsed = {}
            for key, value in data.items():
                if not isinstance(key, str):
                    continue
                if value in {self._API_MODE_CHAT, self._API_MODE_RESPONSES}:
                    parsed[key] = value
            return parsed
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def _persist_route_cache_locked(self) -> None:
        path = self._api_route_cache_path
        if not path:
            return
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._route_cache, f, ensure_ascii=True, indent=2, sort_keys=True)

    def _candidate_api_modes(self):
        if self._api_mode == "auto":
            modes = list(self._api_fallback_order)
        else:
            modes = [self._api_mode]
            if not self._strict_api_mode:
                for mode in self._api_fallback_order:
                    if mode not in modes:
                        modes.append(mode)

        if self._active_api_mode in modes:
            modes.remove(self._active_api_mode)
            modes.insert(0, self._active_api_mode)

        if self._strict_api_mode and modes:
            return [modes[0]]
        return modes

    def _token_param_candidates(self, api_mode: str):
        configured = self._token_params_by_mode.get(api_mode)
        if api_mode == self._API_MODE_CHAT:
            defaults = ["max_tokens", "max_completion_tokens"]
        else:
            defaults = ["max_output_tokens", "max_completion_tokens", "max_tokens"]

        candidates = []
        if configured:
            candidates.append(configured)
        for item in defaults:
            if item not in candidates:
                candidates.append(item)
        return candidates

    def _should_fallback_api_mode(self, exc: Exception) -> bool:
        if self._strict_api_mode:
            return False
        err_msg = str(exc).lower()
        if "operationnotsupported" in err_msg:
            return True
        if "does not work with the specified model" in err_msg:
            return True
        if "unsupported operation" in err_msg:
            return True
        if "not supported" in err_msg and (
            "chatcompletion" in err_msg
            or "chat.completions" in err_msg
            or "responses" in err_msg
            or "operation" in err_msg
        ):
            return True
        return False

    def _is_temperature_error(self, err_msg: str) -> bool:
        lower = err_msg.lower()
        return "temperature" in lower and (
            "unsupported" in lower
            or "not allowed" in lower
            or "not supported" in lower
            or "invalid" in lower
            or "unknown" in lower
        )

    def _is_token_param_error(self, err_msg: str) -> bool:
        lower = err_msg.lower()
        has_token_name = (
            "max_tokens" in lower
            or "max_completion_tokens" in lower
            or "max_output_tokens" in lower
        )
        if not has_token_name:
            return False
        return (
            "unsupported" in lower
            or "not supported" in lower
            or "unknown" in lower
            or "not allowed" in lower
            or "invalid" in lower
            or "extra inputs are not permitted" in lower
        )

    def _normalize_api_mode(self, value: str) -> str:
        mode = str(value).strip().lower()
        aliases = {
            "auto": "auto",
            "chat": self._API_MODE_CHAT,
            "chatcompletion": self._API_MODE_CHAT,
            "chat_completions": self._API_MODE_CHAT,
            "responses": self._API_MODE_RESPONSES,
            "response": self._API_MODE_RESPONSES,
        }
        if mode not in aliases:
            raise ValueError(f"Invalid api_mode: {value}")
        return aliases[mode]

    def _normalize_api_fallback_order(self, value):
        if value is None:
            return [self._API_MODE_CHAT, self._API_MODE_RESPONSES]
        if not isinstance(value, list):
            raise ValueError("api_fallback_order must be a list")
        normalized = []
        for mode in value:
            mode_normalized = self._normalize_api_mode(mode)
            if mode_normalized == "auto":
                continue
            if mode_normalized not in normalized:
                normalized.append(mode_normalized)
        if not normalized:
            normalized = [self._API_MODE_CHAT, self._API_MODE_RESPONSES]
        for mode in [self._API_MODE_CHAT, self._API_MODE_RESPONSES]:
            if mode not in normalized:
                normalized.append(mode)
        return normalized
