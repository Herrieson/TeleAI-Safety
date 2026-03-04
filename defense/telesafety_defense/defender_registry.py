from importlib import import_module
from typing import Dict, Optional


DEFENDER_REGISTRY: Dict[str, Optional[str]] = {
    # Internal defenders
    "DRO": "telesafety_defense.methods.dro:DRODefender",
    "SmoothLLM": "telesafety_defense.methods.smoothllm:SmoothLLMDefender",
    "SelfReminder": None,
    "GoalPrioritization": None,
    "PromptGuard": None,
    "RPO": "telesafety_defense.methods.rpo:RPODefender",
    "CavGan": "telesafety_defense.methods.cavgan:CavGanDefender",
    "RePE": "telesafety_defense.methods.repe:RePEDefender",
    "SemanticSmoothLLM": "telesafety_defense.methods.semanticsmoothllm:SemanticSmoothLLMDefender",
    "GradientCuff": "telesafety_defense.methods.gradient_cuff:GradientCuffDefender",
    "JBShield": "telesafety_defense.methods.jbshield:JBShieldDefender",
    "RAIN": "telesafety_defense.methods.rain:RAINDefender",
    "BackTranslation": "telesafety_defense.methods.backtranslation:BackTranslationDefender",
    "DPS": "telesafety_defense.methods.dps:DPSDefender",
    "LLMLingua": "telesafety_defense.methods.llmlingua:LLMLinguaDefender",
    "GradSafe": "telesafety_defense.methods.gradsafe:GradSafeDefender",
    "JailDAM": "telesafety_defense.methods.jaildam:JailDAMDefender",
    "BackdoorEnhancedAlignment": "telesafety_defense.methods.backdoor_enhanced_alignment:BackdoorEnhancedAlignmentDefender",
    "BackdoorEnhancedAlignmentTrainer": "telesafety_defense.methods.backdoor_enhanced_alignment:BackdoorEnhancedAlignmentTrainer",
    "DELMAN": "telesafety_defense.methods.delman:DELMANDefender",
    "DELMANTrainer": "telesafety_defense.methods.delman:DELMANTrainer",
    "ContinuousAdvTrain": "telesafety_defense.methods.continuous_adv_train:ContinuousAdvTrainTrainer",
    "ContinuousAdvTrainTrainer": "telesafety_defense.methods.continuous_adv_train:ContinuousAdvTrainTrainer",
    # External defenders
    "RobustAlign": "telesafety_defense.methods.robust_alignment:RobustAlignDefender",
    "EraseCheck": "telesafety_defense.methods.erase_and_check:EraseCheckDefender",
    "SafeDecoding": "telesafety_defense.methods.safe_decoding:SafeDecodingDefender",
    "ICD": None,
    "PPL": None,
    "Paraphrase": None,
    "SelfExam": None,
    "Aligner": None,
    "PARDEN": None,
    "GuardReasoner": "telesafety_defense.methods.guardreasoner:GuardReasonerDefender",
    "CourtGuard": "telesafety_defense.methods.courtguard:CourtGuardDefender",
    "PassThrough": "telesafety_defense.methods.passthrough:PassThroughDefender",
}


def list_registered_defenders() -> list[str]:
    return list(DEFENDER_REGISTRY.keys())


def resolve_defender_class(defender_type: str):
    if defender_type not in DEFENDER_REGISTRY:
        raise ValueError(
            f"Unknown defender type: {defender_type}, Select From: {list_registered_defenders()}"
        )
    class_path = DEFENDER_REGISTRY[defender_type]
    if class_path is None:
        raise ValueError(
            f"Defender type '{defender_type}' is reserved but not implemented yet."
        )
    module_path, class_name = class_path.split(":")
    module = import_module(module_path)
    return getattr(module, class_name)
