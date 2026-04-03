import os
import json
import re
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
    managed_target_models_raw: str = os.getenv("TELEAI_MANAGED_TARGET_MODELS", "").strip()

    @property
    def managed_target_models(self) -> list[dict]:
        rows = self._parse_managed_models_from_env()
        if rows:
            return rows
        return self._build_default_managed_models()

    def _parse_managed_models_from_env(self) -> list[dict]:
        raw = self.managed_target_models_raw.strip()
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []

        out: list[dict] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            model_name = str(item.get("target_model_name") or "").strip()
            base_url = str(item.get("base_url") or "").strip()
            api_key = str(item.get("api_key") or "").strip()
            if not model_name or not base_url or not api_key:
                continue
            model_id = str(item.get("id") or "").strip() or self._slugify_model_id(model_name)
            label = str(item.get("label") or "").strip() or model_name
            description = str(item.get("description") or "").strip()
            out.append(
                {
                    "id": model_id,
                    "label": label,
                    "target_model_name": model_name,
                    "base_url": base_url,
                    "api_key": api_key,
                    "description": description,
                }
            )
        return out

    def _build_default_managed_models(self) -> list[dict]:
        base_url = self.internal_llm_base_url.strip()
        api_key = self.internal_llm_api_key.strip()
        if not base_url or not api_key:
            return []
        default_models = [
            ("gpt-5.4", "GPT-5.4 (Managed)"),
            ("gpt-5.2", "GPT-5.2 (Managed)"),
            ("gpt-4o", "GPT-4o (Managed)"),
            ("gpt-4o-mini", "GPT-4o-mini (Managed)"),
        ]
        out: list[dict] = []
        for model_name, label in default_models:
            out.append(
                {
                    "id": self._slugify_model_id(model_name),
                    "label": label,
                    "target_model_name": model_name,
                    "base_url": base_url,
                    "api_key": api_key,
                    "description": "平台托管模型，无需手动填写 Base URL / API Key",
                }
            )
        return out

    @staticmethod
    def _slugify_model_id(raw: str) -> str:
        return re.sub(r"[^a-z0-9._-]+", "-", raw.lower()).strip("-") or "managed-model"


settings = Settings()
