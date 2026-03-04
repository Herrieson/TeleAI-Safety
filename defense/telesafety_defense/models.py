"""
Backward-compatible model exports.

Prefer importing from:
- telesafety_defense.local_model
- telesafety_defense.api_model
- telesafety_defense.model_loader
"""

from telesafety_defense.api_model import OpenAICompatibleModel
from telesafety_defense.local_model import LocalModel
from telesafety_defense.model_loader import load_model

__all__ = ["LocalModel", "OpenAICompatibleModel", "load_model"]
