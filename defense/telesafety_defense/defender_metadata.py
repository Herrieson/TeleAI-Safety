from typing import Dict


_DEFAULT_CAPABILITIES = {
    # Whether runtime pipeline must provide a `model.chat(...)` backend.
    "requires_pipeline_model": True,
    # Whether this defender can be paired with runtime pipeline API backend.
    "supports_pipeline_api_model": False,
}


DEFENDER_METADATA: Dict[str, Dict[str, object]] = {
    "PassThrough": {
        "class_name": "PassThroughDefender",
        "tier": "stable",
        "supports_pipeline_api_model": True,
    },
    "DRO": {"class_name": "DRODefender", "tier": "stable"},
    "RAIN": {"class_name": "RAINDefender", "tier": "stable"},
    "JBShield": {"class_name": "JBShieldDefender", "tier": "stable"},
    "RePE": {"class_name": "RePEDefender", "tier": "stable"},
    "RPO": {
        "class_name": "RPODefender",
        "tier": "stable",
        "supports_pipeline_api_model": True,
    },
    "GradientCuff": {"class_name": "GradientCuffDefender", "tier": "legacy"},
    "GradSafe": {"class_name": "GradSafeDefender", "tier": "legacy"},
    "BackTranslation": {"class_name": "BackTranslationDefender", "tier": "legacy"},
    "DPS": {
        "class_name": "DPSDefender",
        "tier": "experimental",
        "supports_pipeline_api_model": True,
    },
    "LLMLingua": {
        "class_name": "LLMLinguaDefender",
        "tier": "experimental",
        "supports_pipeline_api_model": True,
    },
    "EraseCheck": {
        "class_name": "EraseCheckDefender",
        "tier": "legacy",
        "supports_pipeline_api_model": True,
    },
    "SafeDecoding": {"class_name": "SafeDecodingDefender", "tier": "legacy"},
    "JailDAM": {
        "class_name": "JailDAMDefender",
        "tier": "experimental",
        "supports_pipeline_api_model": True,
    },
    "SmoothLLM": {
        "class_name": "SmoothLLMDefender",
        "tier": "legacy",
        "supports_pipeline_api_model": True,
    },
    "SemanticSmoothLLM": {
        "class_name": "SemanticSmoothLLMDefender",
        "tier": "legacy",
        "supports_pipeline_api_model": True,
    },
    "RobustAlign": {"class_name": "RobustAlignDefender", "tier": "legacy"},
    "GuardReasoner": {
        "class_name": "GuardReasonerDefender",
        "tier": "experimental",
        "supports_pipeline_api_model": True,
    },
    "CourtGuard": {
        "class_name": "CourtGuardDefender",
        "tier": "experimental",
        "requires_pipeline_model": False,
        "supports_pipeline_api_model": True,
    },
    "CavGan": {"class_name": "CavGanDefender", "tier": "experimental"},
    "BackdoorEnhancedAlignment": {
        "class_name": "BackdoorEnhancedAlignmentDefender",
        "tier": "experimental",
        "supports_pipeline_api_model": True,
    },
    "BackdoorEnhancedAlignmentTrainer": {"class_name": "BackdoorEnhancedAlignmentTrainer", "tier": "experimental"},
    "DELMAN": {"class_name": "DELMANDefender", "tier": "experimental"},
    "DELMANTrainer": {"class_name": "DELMANTrainer", "tier": "experimental"},
    "ContinuousAdvTrain": {"class_name": "ContinuousAdvTrainTrainer", "tier": "experimental"},
    "ContinuousAdvTrainTrainer": {"class_name": "ContinuousAdvTrainTrainer", "tier": "experimental"},
}


def get_defender_capabilities(defender_type: str) -> Dict[str, object]:
    meta = dict(DEFENDER_METADATA.get(defender_type, {}))
    capabilities = dict(_DEFAULT_CAPABILITIES)
    capabilities.update({k: v for k, v in meta.items() if k in _DEFAULT_CAPABILITIES})
    meta.update(capabilities)
    return meta


def defender_requires_pipeline_model(defender_type: str) -> bool:
    return bool(get_defender_capabilities(defender_type).get("requires_pipeline_model", True))


def defender_supports_pipeline_api_model(defender_type: str) -> bool:
    return bool(
        get_defender_capabilities(defender_type).get("supports_pipeline_api_model", False)
    )


def defender_supports_api(defender_type: str) -> bool:
    # Backward-compatible alias used by older code/tests.
    return defender_supports_pipeline_api_model(defender_type)
