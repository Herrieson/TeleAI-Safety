from dataclasses import dataclass, field
from typing import Dict


@dataclass
class JudgeResult:
    score: float
    label: str = ""
    rationale: str = ""
    extra: Dict = field(default_factory=dict)
