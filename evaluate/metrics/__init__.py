from .base_metric import Metric, MetricState, MetricUpdate  # noqa: F401
from .asr_metric import ASRMetric, ASRMetricConfig  # noqa: F401
from .mds_metric import MDSMetric, MDSMetricConfig  # noqa: F401


def get_metric(metric_name: str, **kwargs):
    """
    Simple factory. Extend here when adding new metrics.
    """
    name = metric_name.lower()
    if name == "asr":
        return ASRMetric(ASRMetricConfig(**kwargs))
    if name == "mds":
        return MDSMetric(MDSMetricConfig(**kwargs))
    raise ValueError(f"Unsupported metric: {metric_name}")
