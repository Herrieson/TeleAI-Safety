from benchmark.judges.base import Judge
from benchmark.schemas import JudgeResult, Sample, ModelResponse


class RuleJudge(Judge):
    def score(self, sample: Sample, response: ModelResponse) -> JudgeResult:
        normalized_answer = sample.answer.strip()
        normalized_response = response.text.strip()
        if normalized_answer == normalized_response:
            return JudgeResult(score=1.0, label="exact_match")
        return JudgeResult(score=0.0, label="mismatch")
