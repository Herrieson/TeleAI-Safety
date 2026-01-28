from dataclasses import dataclass, field
from typing import Dict


@dataclass
class MetricResult:
    overall: float
    by_task: Dict = field(default_factory=dict)
    by_category: Dict = field(default_factory=dict)
    extra: Dict = field(default_factory=dict)
