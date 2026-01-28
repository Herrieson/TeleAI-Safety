from typing import List

from benchmark.metrics.base import Metric
from benchmark.schemas import JudgeResult, MetricResult


class AccuracyMetric(Metric):
    def compute(self, results: List[JudgeResult]) -> MetricResult:
        if not results:
            return MetricResult(overall=0.0)
        correct = sum(1 for r in results if r.score >= 1.0)
        return MetricResult(overall=correct / len(results))
