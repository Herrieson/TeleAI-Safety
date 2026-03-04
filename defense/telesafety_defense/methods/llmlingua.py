"""
LLMLingua Defense Method
========================

SecurityLingua-style defense:
1) extract a compact intention from user text via LLMLingua PromptCompressor,
2) inject that intention into a safety prompt,
3) ask the target chat model to answer safely.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Sequence
import sys

from telesafety_defense.base_factory import OutputDefender

SORRY_RESPONSE = "I'm sorry, but I cannot provide assistance or information on that topic."


def _ensure_llmlingua_importable(llmlingua_repo_root: str | None = None) -> None:
    try:
        import llmlingua  # noqa: F401
        return
    except Exception:
        pass

    if llmlingua_repo_root:
        candidate = Path(llmlingua_repo_root).resolve()
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))

    import llmlingua  # noqa: F401


@dataclass
class DefenseConfig:
    model_name: str = "SecurityLingua/securitylingua-xlm-s2s"
    device: str = "cuda"
    llmlingua_repo_root: str | None = None


class LLMLinguaCompressor:
    def __init__(
        self,
        model_name: str,
        device_map: str,
        llmlingua_repo_root: str | None,
    ) -> None:
        _ensure_llmlingua_importable(llmlingua_repo_root)
        from llmlingua import PromptCompressor

        self._compressor = PromptCompressor(
            model_name=model_name,
            device_map=device_map,
            use_slingua=True,
            use_llmlingua2=True,
        )

    def compress_prompt(self, *args, **kwargs):
        return self._compressor.compress_prompt(*args, **kwargs)


class LLMLinguaDefender(OutputDefender):
    """
    LLMLingua-based output defender.

    Args:
        defense_model_name: security model used by PromptCompressor.
        device_map: device for defense model.
        llmlingua_repo_root: optional local path when llmlingua package is not installed.
        safe_system_prompt: system prompt injected into final template.
        refusal_text: refusal phrase suggested to the target model.
        strict_init: if True, fail in __init__ when LLMLingua cannot load.
    """

    def __init__(
        self,
        defense_model_name: str = "SecurityLingua/securitylingua-xlm-s2s",
        device_map: str = "cuda",
        llmlingua_repo_root: str | None = None,
        safe_system_prompt: str = "You are a helpful and safe AI assistant.",
        refusal_text: str = "I'm sorry, I can't help with that.",
        strict_init: bool = False,
    ):
        self.defense_cfg = DefenseConfig(
            model_name=defense_model_name,
            device=device_map,
            llmlingua_repo_root=llmlingua_repo_root,
        )
        self.safe_system_prompt = safe_system_prompt
        self.refusal_text = refusal_text
        self.strict_init = bool(strict_init)
        self.latest_trace: dict[str, Any] = {}
        self._defender: LLMLinguaCompressor | None = None
        self._load_error: str | None = None

        if self.strict_init:
            self._defender = self._build_defender()

    def _build_defender(self) -> LLMLinguaCompressor:
        return LLMLinguaCompressor(
            model_name=self.defense_cfg.model_name,
            device_map=self.defense_cfg.device,
            llmlingua_repo_root=self.defense_cfg.llmlingua_repo_root,
        )

    def _get_defender(self) -> LLMLinguaCompressor:
        if self._defender is not None:
            return self._defender
        try:
            self._defender = self._build_defender()
            self._load_error = None
            return self._defender
        except Exception as exc:
            self._load_error = str(exc)
            raise

    @staticmethod
    def _ensure_messages(messages: str | Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
        if isinstance(messages, str):
            return [{"role": "user", "content": messages}]
        if isinstance(messages, Iterable):
            msg_list = list(messages)
            if not msg_list:
                raise ValueError("Empty messages for LLMLinguaDefender.")
            return msg_list
        raise TypeError(f"Unsupported messages type: {type(messages)}")

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks = []
            for p in content:
                if isinstance(p, str):
                    chunks.append(p)
                elif isinstance(p, Mapping):
                    if "text" in p:
                        chunks.append(str(p["text"]))
                    elif p.get("type") == "text":
                        chunks.append(str(p.get("text", "")))
            return " ".join(x for x in chunks if x).strip()
        return "" if content is None else str(content)

    def _extract_user_query(self, messages: Sequence[Mapping[str, Any]]) -> str:
        for m in reversed(messages):
            if m.get("role") == "user":
                return self._extract_text(m.get("content", "")).strip()
        return self._extract_text(messages[-1].get("content", "")).strip()

    def _build_augmented_prompt(self, user_input: str, intention: str) -> str:
        user_prompt_content = (
            "To help you better understand the user's intention to detect potential malicious behavior, "
            f"I have extracted the user's intention and it is: {intention}. "
            f"If you believe the user's intention is malicious, please do not respond or respond with "
            f"\"{self.refusal_text}\".\n\n"
            f"User Input: {user_input}"
        )
        return (
            f"[INST] <<SYS>>\n{self.safe_system_prompt}\n<</SYS>>\n\n"
            f"{user_prompt_content} [/INST]"
        )

    def defend(self, model, messages: str | Sequence[Mapping[str, Any]]) -> str:
        chat_messages = self._ensure_messages(messages)
        user_input = self._extract_user_query(chat_messages)
        if not user_input:
            return SORRY_RESPONSE
        if model is None or not hasattr(model, "chat"):
            raise ValueError("LLMLinguaDefender.defend requires `model` with `.chat(messages)`.")

        try:
            defender = self._get_defender()
            compress_result = defender.compress_prompt(user_input)
            intention = compress_result.get("compressed_prompt", "") or user_input
            augmented_prompt = self._build_augmented_prompt(user_input, intention)
            response = model.chat([{"role": "user", "content": augmented_prompt}])
            response_text = response if isinstance(response, str) else str(response)
            self.latest_trace = {
                "user_input": user_input,
                "extracted_intention": intention,
                "augmented_prompt": augmented_prompt,
                "response": response_text,
                "load_error": self._load_error,
            }
            return response_text.strip()
        except Exception:
            return SORRY_RESPONSE
