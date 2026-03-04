from typing import Iterable, Optional, Sequence
from telesafety_defense.defender_metadata import defender_supports_api


DEFAULT_API_ALLOWED_DEFENDER_CLASSES = ("PassThroughDefender",)


def validate_api_defender_compatibility(
    defenders: Iterable[object],
    allowed_classes: Optional[Sequence[str]] = None,
    defender_type: Optional[str] = None,
) -> None:
    if defender_type and not defender_supports_api(defender_type):
        raise ValueError(
            f"Defender type '{defender_type}' is not marked as API-compatible."
        )

    allowed = set(allowed_classes or DEFAULT_API_ALLOWED_DEFENDER_CLASSES)
    unsupported = []
    for defender in defenders or []:
        cls_name = defender.__class__.__name__
        if cls_name not in allowed:
            unsupported.append(cls_name)
    if unsupported:
        allowed_text = ", ".join(sorted(allowed))
        got_text = ", ".join(sorted(set(unsupported)))
        raise ValueError(
            "API backend only supports defender classes: "
            f"{allowed_text}. Got unsupported: {got_text}"
        )
