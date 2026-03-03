from benchmark.judges.base import Judge
from benchmark.schemas import JudgeResult, ModelResponse, Sample


class NoopJudge(Judge):
    def score(self, sample: Sample, response: ModelResponse) -> JudgeResult:
        return JudgeResult(score=0.0, label="noop", rationale="No judging performed.")
