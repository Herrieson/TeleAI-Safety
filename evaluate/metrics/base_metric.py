from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class MetricUpdate:
    """
    Per-sample metric update.
    - total: number of samples considered (0/1)
    - success: count of positive/success cases (definition depends on metric)
    - skipped: samples ignored due to parse/metric issues
    - value_sum/value_count: aggregate numeric metric values (for averages)
    """
    total: int = 0
    success: int = 0
    skipped: int = 0
    value_sum: float = 0.0
    value_count: int = 0
    extra: Optional[Dict[str, Any]] = None


@dataclass
class MetricState:
    total: int = 0
    success: int = 0
    skipped: int = 0
    value_sum: float = 0.0
    value_count: int = 0


class Metric:
    """
    Minimal metric interface. Implementors should be stateless for thread-safety.
    """

    name: str = "Metric"
    # Used for output file naming; override for custom suffixes.
    output_tag: str = "metric"

    def create_state(self) -> MetricState:
        return MetricState()

    def process_sample(self, sample: Dict[str, Any]) -> MetricUpdate:
        raise NotImplementedError

    def merge(self, state: MetricState, update: MetricUpdate) -> None:
        state.total += update.total
        state.success += update.success
        state.skipped += update.skipped
        state.value_sum += update.value_sum
        state.value_count += update.value_count

    def finalize(self, state: MetricState) -> Dict[str, Any]:
        avg_value: Optional[float] = None
        if state.value_count > 0:
            avg_value = state.value_sum / state.value_count
        return {
            "total": state.total,
            "success": state.success,
            "skipped": state.skipped,
            "avg_value": avg_value,
        }

    def render_report(
        self, *, state: MetricState, input_file: str
    ) -> str:
        summary = self.finalize(state)
        lines = [
            "Evaluation Summary Report",
            f"Metric: {self.name}",
            f"Input file: {input_file}",
            f"Total samples: {summary['total']}",
            f"Skipped samples: {summary['skipped']}",
            f"Success samples: {summary['success']}",
        ]
        if summary["avg_value"] is not None:
            lines.append(f"Average value: {summary['avg_value']:.4f}")
        return "\n".join(lines) + "\n"
