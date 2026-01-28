from typing import List

from benchmark.metrics.base import Metric
from benchmark.schemas import JudgeResult, MetricResult


class AggregateMetric(Metric):
    def compute(self, results: List[JudgeResult]) -> MetricResult:
        if not results:
            return MetricResult(overall=0.0)
        scores = [r.score for r in results]
        overall = sum(scores) / len(scores)
        return MetricResult(overall=overall)
