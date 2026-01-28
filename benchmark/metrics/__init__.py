from benchmark.metrics.base import Metric
from benchmark.metrics.registry import MetricRegistry
from benchmark.metrics.aggregate import AggregateMetric
from benchmark.metrics.accuracy import AccuracyMetric

MetricRegistry.register("aggregate", AggregateMetric)
MetricRegistry.register("accuracy", AccuracyMetric)

__all__ = ["Metric", "MetricRegistry"]
