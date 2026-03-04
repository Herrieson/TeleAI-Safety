"""
LLMLingua Update
================

Single-file integration that refactors LLMLingua-main into a methods-style module.

What this file provides:
1) LLMLinguaCompressor: wrapper around LLMLingua / LongLLMLingua / LLMLingua-2 APIs.
2) LLMLinguaDefender(OutputDefender): SecurityLingua-style guard that supports
   `defend(model, messages)` for telesafety methods.
3) Config-driven batch runner equivalent to easy_defense/run_defense.py.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Sequence

import torch

try:
    import yaml
except Exception as exc:
    raise ImportError("PyYAML is required for LLMLingua_update.py") from exc

try:
    from telesafety_defense.base_factory import OutputDefender
    from telesafety_defense.utils import SORRY_RESPONSE
except Exception:
    class OutputDefender:  # type: ignore[override]
        def defend(self, model, messages):
            raise NotImplementedError

    SORRY_RESPONSE = "I'm sorry, but I cannot provide assistance or information on that topic."


def _ensure_llmlingua_importable(llmlingua_repo_root: str | None = None) -> None:
    """
    Make llmlingua package importable from local repo if not installed.
    """
    try:
        import llmlingua  # noqa: F401
        return
    except Exception:
        pass

    if llmlingua_repo_root:
        candidate = Path(llmlingua_repo_root).resolve()
    else:
        candidate = Path(__file__).resolve().parent / "LLMLingua-main"

    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

    try:
        import llmlingua  # noqa: F401
    except Exception as exc:
        raise ImportError(
            "Cannot import llmlingua. Install package or pass valid llmlingua_repo_root."
        ) from exc


class BaseTargetModel:
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class HuggingFaceTargetModel(BaseTargetModel):
    def __init__(self, model_path: str, device: str = "cuda", max_new_tokens: int = 512):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.max_new_tokens = max_new_tokens
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        dtype = torch.float16 if "cuda" in device else torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map=device,
            trust_remote_code=True,
            torch_dtype=dtype,
        )

    def generate(self, prompt: str) -> str:
        device = self.model.device
        inputs = self.tokenizer(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        text = self.tokenizer.decode(outputs[0][inputs.input_ids.shape[1] :], skip_special_tokens=True)
        return text.strip()


class AzureOpenAITargetModel(BaseTargetModel):
    def __init__(
        self,
        api_key: str,
        endpoint: str,
        model_name: str = "gpt-4",
        api_version: str = "2024-12-01-preview",
    ):
        from openai import AzureOpenAI

        self.client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key,
        )
        self.model_name = model_name

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
        )
        return (response.choices[0].message.content or "").strip()


class OpenAITargetModel(BaseTargetModel):
    def __init__(self, api_key: str, model_name: str = "gpt-3.5-turbo", base_url: str | None = None):
        import openai

        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return (response.choices[0].message.content or "").strip()


class MockTargetModel(BaseTargetModel):
    def generate(self, prompt: str) -> str:
        _ = prompt
        return "This is a mock response. The defense mechanism seems to work."


class ChatModelAdapter:
    """
    Adapter that converts a `.chat(messages)` style model into BaseTargetModel `.generate(prompt)`.
    """

    def __init__(self, chat_model):
        self.chat_model = chat_model

    def generate(self, prompt: str) -> str:
        response = self.chat_model.chat([{"role": "user", "content": prompt}])
        return response if isinstance(response, str) else str(response)


@dataclass
class DefenseConfig:
    model_name: str = "SecurityLingua/securitylingua-xlm-s2s"
    device: str = "cuda"
    llmlingua_repo_root: str | None = None


class LLMLinguaCompressor:
    """
    Wrapper over PromptCompressor to expose LLMLingua-family capabilities from one place.
    """

    def __init__(
        self,
        model_name: str = "NousResearch/Llama-2-7b-hf",
        device_map: str = "cuda",
        model_config: dict | None = None,
        open_api_config: dict | None = None,
        use_llmlingua2: bool = False,
        use_slingua: bool = False,
        llmlingua2_config: dict | None = None,
        llmlingua_repo_root: str | None = None,
    ):
        _ensure_llmlingua_importable(llmlingua_repo_root)
        from llmlingua import PromptCompressor

        self._compressor = PromptCompressor(
            model_name=model_name,
            device_map=device_map,
            model_config=model_config or {},
            open_api_config=open_api_config or {},
            use_llmlingua2=use_llmlingua2,
            use_slingua=use_slingua,
            llmlingua2_config=llmlingua2_config or {},
        )

    def compress_prompt(self, *args, **kwargs):
        return self._compressor.compress_prompt(*args, **kwargs)

    def structured_compress_prompt(self, *args, **kwargs):
        return self._compressor.structured_compress_prompt(*args, **kwargs)

    def compress_json(self, *args, **kwargs):
        return self._compressor.compress_json(*args, **kwargs)

    @property
    def raw(self):
        return self._compressor


class LLMLinguaDefender(OutputDefender):
    """
    SecurityLingua-style defender compatible with telesafety methods API.

    Flow:
    1) Extract user query from messages.
    2) Use SecurityLingua (PromptCompressor with use_slingua=True) to extract intention.
    3) Build augmented safe prompt.
    4) Ask target model for final response.
    """

    def __init__(
        self,
        defense_model_name: str = "SecurityLingua/securitylingua-xlm-s2s",
        device_map: str = "cuda",
        llmlingua_repo_root: str | None = None,
        safe_system_prompt: str = "You are a helpful and safe AI assistant.",
        refusal_text: str = "I'm sorry, I can't help with that.",
    ):
        self.defense_cfg = DefenseConfig(
            model_name=defense_model_name,
            device=device_map,
            llmlingua_repo_root=llmlingua_repo_root,
        )
        self.safe_system_prompt = safe_system_prompt
        self.refusal_text = refusal_text
        self.latest_trace: dict[str, Any] = {}
        self._defender = LLMLinguaCompressor(
            model_name=defense_model_name,
            device_map=device_map,
            use_slingua=True,
            use_llmlingua2=True,
            llmlingua_repo_root=llmlingua_repo_root,
        )

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

        target = ChatModelAdapter(model) if model is not None and hasattr(model, "chat") else None
        if target is None:
            raise ValueError("LLMLinguaDefender.defend requires `model` with `.chat(messages)`.")

        try:
            compress_result = self._defender.compress_prompt(user_input)
            intention = compress_result.get("compressed_prompt", "")
            if not intention:
                intention = user_input
            augmented_prompt = self._build_augmented_prompt(user_input, intention)
            response = target.generate(augmented_prompt)
            self.latest_trace = {
                "user_input": user_input,
                "extracted_intention": intention,
                "augmented_prompt": augmented_prompt,
                "response": response,
            }
            return response.strip()
        except Exception:
            return SORRY_RESPONSE


def _load_yaml_config(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_target_model_from_config(cfg: Mapping[str, Any]) -> BaseTargetModel:
    model_type = str(cfg.get("type", "mock")).lower()
    if model_type == "whitebox":
        return HuggingFaceTargetModel(
            model_path=str(cfg["path"]),
            device=str(cfg.get("device", "cuda")),
            max_new_tokens=int(cfg.get("max_new_tokens", 512)),
        )
    if model_type == "blackbox":
        platform = str(cfg.get("platform", "")).lower()
        if platform == "azure":
            return AzureOpenAITargetModel(
                api_key=str(cfg["api_key"]),
                endpoint=str(cfg["endpoint"]),
                model_name=str(cfg.get("model_name", "gpt-4")),
                api_version=str(cfg.get("api_version", "2024-12-01-preview")),
            )
        return OpenAITargetModel(
            api_key=str(cfg["api_key"]),
            model_name=str(cfg.get("model_name", "gpt-3.5-turbo")),
            base_url=cfg.get("base_url"),
        )
    return MockTargetModel()


def run_batch_defense(config_path: str) -> str:
    """
    Equivalent workflow of easy_defense/run_defense.py:
    - load yaml config
    - init SecurityLingua defender
    - init target model
    - process dataset items and save outputs
    """
    cfg = _load_yaml_config(config_path)

    defense_cfg = cfg.get("defense", {})
    data_cfg = cfg.get("data", {})
    target_cfg = cfg.get("target_model", {})

    input_path = str(data_cfg.get("input_path", "test_data.json"))
    output_path = str(data_cfg.get("output_path", "test_data.json"))

    defender = LLMLinguaDefender(
        defense_model_name=str(defense_cfg.get("model_name", "SecurityLingua/securitylingua-xlm-s2s")),
        device_map=str(defense_cfg.get("device", "cuda")),
        llmlingua_repo_root=cfg.get("llmlingua_repo_root"),
    )
    target_model = _build_target_model_from_config(target_cfg)

    with open(input_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    if not isinstance(dataset, list):
        raise ValueError("Input dataset must be a JSON list.")

    results = []
    for item in dataset:
        if not isinstance(item, dict):
            continue
        user_input = str(item.get("final_query", "")).strip()
        if not user_input:
            continue
        try:
            compress_result = defender._defender.compress_prompt(user_input)
            intention = compress_result.get("compressed_prompt", "") or user_input
            augmented_prompt = defender._build_augmented_prompt(user_input, intention)
            response = target_model.generate(augmented_prompt)

            out = item.copy()
            out["extracted_intention"] = intention
            out["final_response"] = response
            results.append(out)
        except Exception as exc:
            out = item.copy()
            out["error"] = str(exc)
            results.append(out)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    return output_path


def cli() -> int:
    parser = argparse.ArgumentParser(description="LLMLingua update module")
    sub = parser.add_subparsers(dest="cmd")

    p_batch = sub.add_parser("batch", help="Run SecurityLingua batch defense from yaml config")
    p_batch.add_argument("--config", type=str, required=True)

    p_compress = sub.add_parser("compress", help="Run one-shot compression")
    p_compress.add_argument("--text", type=str, required=True)
    p_compress.add_argument("--model-name", type=str, default="NousResearch/Llama-2-7b-hf")
    p_compress.add_argument("--device", type=str, default="cuda")
    p_compress.add_argument("--use-llmlingua2", action="store_true")
    p_compress.add_argument("--use-slingua", action="store_true")
    p_compress.add_argument("--llmlingua-repo-root", type=str, default=None)

    args = parser.parse_args()

    if args.cmd == "batch":
        out = run_batch_defense(args.config)
        print(out)
        return 0

    if args.cmd == "compress":
        compressor = LLMLinguaCompressor(
            model_name=args.model_name,
            device_map=args.device,
            use_llmlingua2=bool(args.use_llmlingua2),
            use_slingua=bool(args.use_slingua),
            llmlingua_repo_root=args.llmlingua_repo_root,
        )
        res = compressor.compress_prompt(args.text)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(cli())

