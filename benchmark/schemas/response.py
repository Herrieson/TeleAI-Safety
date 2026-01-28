from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ModelResponse:
    text: str
    raw: Dict = field(default_factory=dict)
    meta: Dict = field(default_factory=dict)
