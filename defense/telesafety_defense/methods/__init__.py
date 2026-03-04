"""
Defense Methods Module
======================

This module contains various defense method implementations.
"""

from importlib import import_module


_LAZY_EXPORTS = {
    "DRODefender": "telesafety_defense.methods.dro:DRODefender",
    "SmoothLLMDefender": "telesafety_defense.methods.smoothllm:SmoothLLMDefender",
    "GradientCuffDefender": "telesafety_defense.methods.gradient_cuff:GradientCuffDefender",
    "JBShieldDefender": "telesafety_defense.methods.jbshield:JBShieldDefender",
    "RAINDefender": "telesafety_defense.methods.rain:RAINDefender",
    "BackTranslationDefender": "telesafety_defense.methods.backtranslation:BackTranslationDefender",
    "DPSDefender": "telesafety_defense.methods.dps:DPSDefender",
    "LLMLinguaDefender": "telesafety_defense.methods.llmlingua:LLMLinguaDefender",
    "BackdoorEnhancedAlignmentDefender": "telesafety_defense.methods.backdoor_enhanced_alignment:BackdoorEnhancedAlignmentDefender",
    "BackdoorEnhancedAlignmentTrainer": "telesafety_defense.methods.backdoor_enhanced_alignment:BackdoorEnhancedAlignmentTrainer",
    "DELMANDefender": "telesafety_defense.methods.delman:DELMANDefender",
    "DELMANTrainer": "telesafety_defense.methods.delman:DELMANTrainer",
    "ContinuousAdvTrainTrainer": "telesafety_defense.methods.continuous_adv_train:ContinuousAdvTrainTrainer",
    "EraseCheckDefender": "telesafety_defense.methods.erase_and_check:EraseCheckDefender",
    "SafeDecodingDefender": "telesafety_defense.methods.safe_decoding:SafeDecodingDefender",
    "JailDAMDefender": "telesafety_defense.methods.jaildam:JailDAMDefender",
    "GradSafeDefender": "telesafety_defense.methods.gradsafe:GradSafeDefender",
    "GuardReasonerDefender": "telesafety_defense.methods.guardreasoner:GuardReasonerDefender",
    "CourtGuardDefender": "telesafety_defense.methods.courtguard:CourtGuardDefender",
    "PassThroughDefender": "telesafety_defense.methods.passthrough:PassThroughDefender",
}


def __getattr__(name):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, class_name = target.split(":")
    module = import_module(module_path)
    value = getattr(module, class_name)
    globals()[name] = value
    return value


__all__ = [
    "DRODefender",
    "SmoothLLMDefender",
    "GradientCuffDefender",
    "JBShieldDefender",
    "RAINDefender",
    "BackTranslationDefender",
    "DPSDefender",
    "LLMLinguaDefender",
    "BackdoorEnhancedAlignmentDefender",
    "BackdoorEnhancedAlignmentTrainer",
    "DELMANDefender",
    "DELMANTrainer",
    "ContinuousAdvTrainTrainer",
    "EraseCheckDefender",
    "SafeDecodingDefender",
    "JailDAMDefender",
    "GradSafeDefender",
    "GuardReasonerDefender",
    "CourtGuardDefender",
    "PassThroughDefender",
]
