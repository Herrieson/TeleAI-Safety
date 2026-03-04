"""
Compatibility facade for defender creation.

Canonical modules:
- telesafety_defense.defender_registry
- telesafety_defense.defender_builder
"""

from telesafety_defense.defender_builder import (
    create_defender,
    create_defender_from_config,
    create_defender_from_yaml,
)
from telesafety_defense.defender_registry import DEFENDER_REGISTRY, list_registered_defenders

__all__ = [
    "DEFENDER_REGISTRY",
    "list_registered_defenders",
    "create_defender",
    "create_defender_from_config",
    "create_defender_from_yaml",
]
