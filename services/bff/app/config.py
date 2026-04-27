import os
from pathlib import Path


def _as_bool(value: str, default: bool = False) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


class Settings:
    repo_root: Path = Path(__file__).resolve().parents[3]
    app_name: str = "teleai-bff"
    app_version: str = "0.1.0"
    orchestrator_base_url: str = os.getenv("ORCHESTRATOR_BASE_URL", "http://127.0.0.1:9001")
    timeout_seconds: int = int(os.getenv("BFF_HTTP_TIMEOUT", "20"))
    auth_users_file: Path = Path(os.getenv("BFF_AUTH_USERS_FILE", str(repo_root / "data" / "service_auth" / "users.json")))
    session_secret: str = os.getenv("BFF_SESSION_SECRET", "teleai-dev-session-secret")
    session_ttl_seconds: int = int(os.getenv("BFF_SESSION_TTL_SECONDS", "43200"))
    password_hash_iterations: int = int(os.getenv("BFF_PASSWORD_HASH_ITERATIONS", "200000"))
    managed_mode_max_active_runs_global: int = int(os.getenv("BFF_MANAGED_MODE_MAX_ACTIVE_RUNS_GLOBAL", "6"))
    managed_mode_max_active_runs_per_ip: int = int(os.getenv("BFF_MANAGED_MODE_MAX_ACTIVE_RUNS_PER_IP", "2"))
    managed_mode_min_interval_seconds: int = int(os.getenv("BFF_MANAGED_MODE_MIN_INTERVAL_SECONDS", "300"))
    managed_mode_access_control_enabled: bool = _as_bool(
        os.getenv("BFF_MANAGED_MODE_ACCESS_CONTROL_ENABLED", "false"),
        default=False,
    )
    managed_mode_ip_whitelist_raw: str = os.getenv(
        "BFF_MANAGED_MODE_IP_WHITELIST",
        "127.0.0.1,::1",
    )
    managed_mode_invite_codes_raw: str = os.getenv("BFF_MANAGED_MODE_INVITE_CODES", "")
    cors_allow_origins_raw: str = os.getenv(
        "BFF_CORS_ALLOW_ORIGINS",
        "http://127.0.0.1:3000,http://localhost:3000",
    )

    @property
    def cors_allow_origins(self) -> list[str]:
        origins = [item.strip() for item in self.cors_allow_origins_raw.split(",")]
        return [item for item in origins if item]

    @property
    def managed_mode_ip_whitelist(self) -> set[str]:
        return {item.strip() for item in self.managed_mode_ip_whitelist_raw.split(",") if item.strip()}

    @property
    def managed_mode_invite_codes(self) -> set[str]:
        return {item.strip() for item in self.managed_mode_invite_codes_raw.split(",") if item.strip()}


settings = Settings()
