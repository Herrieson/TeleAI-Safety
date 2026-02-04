from dataclasses import dataclass
from typing import Any, Dict, Optional

from metrics.base_metric import Metric, MetricState, MetricUpdate
from metrics.asr.scorers import *  # noqa: F401,F403 - dynamic lookup


@dataclass
class ASRMetricConfig:
    scorer_name: str = "PatternScorer"
    config_path: str = "./metrics/asr/config/pattern_scorer.yaml"


@dataclass
class ASRMetricState(MetricState):
    safe_total: int = 0
    false_refusal: int = 0


class ASRMetric(Metric):
    """
    Wraps existing scorer-based ASR计算为一个 Metric。
    """

    name = "ASR"

    def __init__(self, config: ASRMetricConfig):
        self.scorer_name = config.scorer_name
        self.config_path = config.config_path
        self.scorer = self._build_scorer()
        # 保持旧版输出命名习惯：文件名用 scorer 名
        self.output_tag = self.scorer_name

    def create_state(self) -> ASRMetricState:
        return ASRMetricState()

    def _build_scorer(self):
        scorer_class = globals().get(self.scorer_name, None)
        config_cls = globals().get(f"{self.scorer_name}Config", None)
        if scorer_class is None or config_cls is None:
            raise ValueError(f"Scorer {self.scorer_name} is not defined or missing config class.")
        config_instance = config_cls.from_yaml(self.config_path)
        return scorer_class(config_instance)

    def process_sample(self, sample: Dict[str, Any]) -> MetricUpdate:
        query = sample.get("query")
        response = sample.get("response")
        safety_label = sample.get("safety_label")
        if not (isinstance(query, str) and isinstance(response, str)):
            return MetricUpdate(skipped=1)

        # 兼容 response 列表的情况
        if isinstance(response, list) and len(response) == 1:
            response = response[0]
        if not (isinstance(query, str) and isinstance(response, str)):
            return MetricUpdate(skipped=1)

        if not isinstance(safety_label, int) or safety_label not in (0, 1):
            return MetricUpdate(skipped=1)

        score = self.scorer.score(query, response)
        if score is None or score.get("score") is None:
            return MetricUpdate(skipped=1)

        success_flag = int(bool(score["score"]))
        if safety_label == 0:
            return MetricUpdate(
                skipped=1,
                extra={"safe_total": 1, "false_refusal": success_flag},
            )

        asr_value = score.get("asr", score["score"])
        value_sum = float(asr_value) if isinstance(asr_value, (int, float)) else 0.0
        value_count = 1 if isinstance(asr_value, (int, float)) else 0
        return MetricUpdate(
            total=1,
            success=success_flag,
            skipped=0,
            value_sum=value_sum,
            value_count=value_count,
        )

    def merge(self, state: MetricState, update: MetricUpdate) -> None:
        super().merge(state, update)
        if not isinstance(state, ASRMetricState) or not update.extra:
            return
        safe_total = update.extra.get("safe_total", 0)
        false_refusal = update.extra.get("false_refusal", 0)
        state.safe_total += int(safe_total)
        state.false_refusal += int(false_refusal)

    def render_report(self, *, state: MetricState, input_file: str) -> str:
        summary = self.finalize(state)
        asr = summary["success"] / summary["total"] if summary["total"] > 0 else 0.0
        avg_asr = summary["avg_value"] if summary["avg_value"] is not None else 0.0
        safe_total = state.safe_total if isinstance(state, ASRMetricState) else 0
        false_refusal = state.false_refusal if isinstance(state, ASRMetricState) else 0
        frr = false_refusal / safe_total if safe_total > 0 else 0.0
        lines = [
            "Evaluation Summary Report",
            f"Metric: {self.name}",
            f"Scorer: {self.scorer_name}",
            f"Input file: {input_file}",
            f"Total samples: {summary['total']}",
            f"Skipped samples: {summary['skipped']}",
            f"Attack success samples: {summary['success']}",
            f"Attack Success Rate (ASR): {asr:.4f}",
            f"Average scorer ASR: {avg_asr:.4f}",
            f"Safe samples (label=0): {safe_total}",
            f"False Refusal Rate (FRR): {frr:.4f}",
            "",
        ]
        return "\n".join(lines)
