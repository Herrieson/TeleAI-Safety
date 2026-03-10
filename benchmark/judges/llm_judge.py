import json
import re
import time
from typing import Any, Dict, Optional

from benchmark.judges.base import Judge
from benchmark.models import ModelRegistry
from benchmark.schemas import JudgeResult, Sample, ModelResponse


class LLMJudge(Judge):
    def __init__(self, config: dict):
        super().__init__(config)
        model_cfg = config.get("model", {})
        model_type = model_cfg.get("type", "openai")
        self.model = ModelRegistry.create(model_type, model_cfg)
        self.prompt = config.get("prompt", "")
        self.system_prompt = config.get("system_prompt", "")
        self.max_parse_retries = int(config.get("max_parse_retries", 0))
        self.parse_retry_sleep_seconds = float(config.get("parse_retry_sleep_seconds", 0))

    def score(self, sample: Sample, response: ModelResponse) -> JudgeResult:
        format_kwargs = {
            "question": sample.question,
            "answer": sample.answer,
            "truth": sample.answer,
            "response": response.text,
            "model_answer": response.text,
            "pred": response.text,
            "task": sample.task,
            "meta": sample.meta,
            "sample_id": sample.id,
        }
        if isinstance(sample.meta, dict):
            format_kwargs.update(sample.meta)
        prompt = self.prompt.format(**format_kwargs)
        if self.system_prompt:
            full_prompt = f"{self.system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt
        last_text = ""
        attempts = 1 + max(0, self.max_parse_retries)
        for idx in range(attempts):
            judge_response = self.model.generate(full_prompt)
            last_text = judge_response.text
            payload = _load_judge_payload(last_text)
            if payload is not None:
                return JudgeResult(
                    score=float(payload.get("score", 0)),
                    label=str(payload.get("label", "")),
                    rationale=str(payload.get("rationale", "")),
                    extra=payload,
                )
            if idx < attempts - 1 and self.parse_retry_sleep_seconds > 0:
                time.sleep(self.parse_retry_sleep_seconds)
        return JudgeResult(score=0.0, label="parse_error", rationale=last_text)


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _wrap_score(value: Any) -> Optional[Dict]:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return {
        "score": score,
        "label": "scalar",
        "rationale": "",
    }


def _decode_payload(candidate: str):
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    if isinstance(decoded, dict):
        return decoded
    if isinstance(decoded, (int, float)):
        return _wrap_score(decoded)
    if isinstance(decoded, str):
        scalar = _wrap_score(decoded.strip())
        if scalar is not None:
            return scalar
    return None


def _load_judge_payload(text: str):
    decoded = _decode_payload(text)
    if decoded is not None:
        return decoded

    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        decoded = _decode_payload(fence_match.group(1).strip())
        if decoded is not None:
            return decoded

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        decoded = _decode_payload(candidate)
        if decoded is not None:
            return decoded

    number_match = _NUMBER_RE.search(text)
    if number_match:
        return _wrap_score(number_match.group(0))

    return None


def _load_json_payload(text: str):
    # Backward-compatible alias for older imports/calls.
    return _load_judge_payload(text)
