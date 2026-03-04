from typing import Dict


DEFENDER_METADATA: Dict[str, Dict[str, object]] = {
    "PassThrough": {"class_name": "PassThroughDefender", "tier": "stable", "supports_api": True},
    "DRO": {"class_name": "DRODefender", "tier": "stable", "supports_api": False},
    "RAIN": {"class_name": "RAINDefender", "tier": "stable", "supports_api": False},
    "JBShield": {"class_name": "JBShieldDefender", "tier": "stable", "supports_api": False},
    "RePE": {"class_name": "RePEDefender", "tier": "stable", "supports_api": False},
    "RPO": {"class_name": "RPODefender", "tier": "stable", "supports_api": False},
    "GradientCuff": {"class_name": "GradientCuffDefender", "tier": "legacy", "supports_api": False},
    "GradSafe": {"class_name": "GradSafeDefender", "tier": "legacy", "supports_api": False},
    "BackTranslation": {"class_name": "BackTranslationDefender", "tier": "legacy", "supports_api": False},
    "DPS": {"class_name": "DPSDefender", "tier": "experimental", "supports_api": False},
    "LLMLingua": {"class_name": "LLMLinguaDefender", "tier": "experimental", "supports_api": False},
    "EraseCheck": {"class_name": "EraseCheckDefender", "tier": "legacy", "supports_api": False},
    "SafeDecoding": {"class_name": "SafeDecodingDefender", "tier": "legacy", "supports_api": False},
    "JailDAM": {"class_name": "JailDAMDefender", "tier": "experimental", "supports_api": False},
    "SmoothLLM": {"class_name": "SmoothLLMDefender", "tier": "legacy", "supports_api": False},
    "SemanticSmoothLLM": {"class_name": "SemanticSmoothLLMDefender", "tier": "legacy", "supports_api": False},
    "RobustAlign": {"class_name": "RobustAlignDefender", "tier": "legacy", "supports_api": False},
    "GuardReasoner": {"class_name": "GuardReasonerDefender", "tier": "experimental", "supports_api": False},
    "CourtGuard": {"class_name": "CourtGuardDefender", "tier": "experimental", "supports_api": False},
    "CavGan": {"class_name": "CavGanDefender", "tier": "experimental", "supports_api": False},
    "BackdoorEnhancedAlignment": {"class_name": "BackdoorEnhancedAlignmentDefender", "tier": "experimental", "supports_api": False},
    "BackdoorEnhancedAlignmentTrainer": {"class_name": "BackdoorEnhancedAlignmentTrainer", "tier": "experimental", "supports_api": False},
    "DELMAN": {"class_name": "DELMANDefender", "tier": "experimental", "supports_api": False},
    "DELMANTrainer": {"class_name": "DELMANTrainer", "tier": "experimental", "supports_api": False},
    "ContinuousAdvTrain": {"class_name": "ContinuousAdvTrainTrainer", "tier": "experimental", "supports_api": False},
    "ContinuousAdvTrainTrainer": {"class_name": "ContinuousAdvTrainTrainer", "tier": "experimental", "supports_api": False},
}


def defender_supports_api(defender_type: str) -> bool:
    meta = DEFENDER_METADATA.get(defender_type, {})
    return bool(meta.get("supports_api", False))
