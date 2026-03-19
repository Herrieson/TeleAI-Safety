import os


class Settings:
    app_name: str = "teleai-bff"
    app_version: str = "0.1.0"
    orchestrator_base_url: str = os.getenv("ORCHESTRATOR_BASE_URL", "http://127.0.0.1:9001")
    timeout_seconds: int = int(os.getenv("BFF_HTTP_TIMEOUT", "20"))
    cors_allow_origins_raw: str = os.getenv(
        "BFF_CORS_ALLOW_ORIGINS",
        "http://127.0.0.1:3000,http://localhost:3000",
    )

    @property
    def cors_allow_origins(self) -> list[str]:
        origins = [item.strip() for item in self.cors_allow_origins_raw.split(",")]
        return [item for item in origins if item]


settings = Settings()
