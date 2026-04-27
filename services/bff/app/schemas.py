from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class AuthUserResponse(BaseModel):
    username: str
    role: Literal["admin", "user"]


class LoginResponse(BaseModel):
    token: str
    session_ttl_seconds: int
    user: AuthUserResponse


class RunCreateRequest(BaseModel):
    name: str = Field(default="", max_length=128)
    mode: Literal["attack_only", "benchmark_only", "eval_only", "full_pipeline"] = "full_pipeline"
    attack_config_dir: str = "configs/gpt-5.4"
    benchmark_config_path: str = ""
    eval_profile: str = "full"
    results_root: str = "data/attack_results"
    result_manifest: str = ""
    quick_attack_enabled: bool = False
    quick_target_model_name: str = "gpt-4o-mini"
    quick_openai_base_url: str = ""
    quick_openai_api_key: str = ""
    quick_attack_methods: list[str] = Field(default_factory=lambda: ["pair", "cipher", "rene"])
    quick_dataset_key: str = "teleai_samples_500_500"
    managed_target_model_id: str = ""
    managed_access_code: str = ""
    requester_ip: str = ""

    @model_validator(mode="after")
    def _validate_eval_only_inputs(self):
        if self.mode == "eval_only" and not self.result_manifest.strip():
            raise ValueError("eval_only mode requires non-empty result_manifest")
        return self
