from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Sample:
    id: str
    task: str
    question: str
    answer: str
    meta: Dict = field(default_factory=dict)
