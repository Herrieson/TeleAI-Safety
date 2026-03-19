import os
from pathlib import Path


def _as_bool(value: str, default: bool = False) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


class Settings:
    app_name: str = "teleai-orchestrator"
    app_version: str = "0.1.0"
    timezone: str = os.getenv("TELEAI_TZ", "Asia/Shanghai")
    repo_root: Path = Path(__file__).resolve().parents[3]
    run_log_root: Path = repo_root / "data" / "service_runs"
    internal_llm_api_key: str = os.getenv("TELEAI_INTERNAL_LLM_API_KEY", "").strip()
    internal_llm_base_url: str = os.getenv("TELEAI_INTERNAL_LLM_BASE_URL", "").strip()
    internal_llm_model: str = os.getenv("TELEAI_INTERNAL_LLM_MODEL", "").strip()
    use_internal_llm_for_attack: bool = _as_bool(
        os.getenv("TELEAI_USE_INTERNAL_LLM_FOR_ATTACK", "true"),
        default=True,
    )
    use_internal_llm_for_evaluate: bool = _as_bool(
        os.getenv("TELEAI_USE_INTERNAL_LLM_FOR_EVALUATE", "true"),
        default=True,
    )
    strict_cred_isolation: bool = _as_bool(
        os.getenv("TELEAI_STRICT_CRED_ISOLATION", "true"),
        default=True,
    )


settings = Settings()
