import json
import re

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

    def score(self, sample: Sample, response: ModelResponse) -> JudgeResult:
        prompt = self.prompt.format(
            question=sample.question,
            answer=sample.answer,
            response=response.text,
            task=sample.task,
        )
        if self.system_prompt:
            full_prompt = f"{self.system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt
        judge_response = self.model.generate(full_prompt)
        payload = _load_json_payload(judge_response.text)
        if payload is None:
            return JudgeResult(score=0.0, label="parse_error", rationale=judge_response.text)
        return JudgeResult(
            score=float(payload.get("score", 0)),
            label=str(payload.get("label", "")),
            rationale=str(payload.get("rationale", "")),
            extra=payload,
        )


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _load_json_payload(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None
