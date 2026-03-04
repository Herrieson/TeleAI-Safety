"""
Telesafety Defense Framework
============================

A framework for AI safety defense methods, refactored from AISafetyLab.
"""

from .base_factory import (
    Defender, 
    InputDefender, 
    OutputDefender,
    InferenceDefender,
    TrainingDefender
)


def create_defender(*args, **kwargs):
    from .defender_builder import create_defender as _create_defender
    return _create_defender(*args, **kwargs)


def create_defender_from_yaml(*args, **kwargs):
    from .defender_builder import create_defender_from_yaml as _create_defender_from_yaml
    return _create_defender_from_yaml(*args, **kwargs)


__all__ = [
    "Defender",
    "InputDefender",
    "OutputDefender",
    "InferenceDefender",
    "TrainingDefender",
    "create_defender",
    "create_defender_from_yaml",
]
