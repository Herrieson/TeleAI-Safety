from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


RunMode = Literal["attack_only", "benchmark_only", "eval_only", "full_pipeline"]
RunStatus = Literal["pending", "running", "succeeded", "failed", "canceled"]
StageName = Literal["attack", "benchmark", "evaluate"]
StageStatus = Literal["pending", "running", "succeeded", "failed", "canceled"]


class RunCreate(BaseModel):
    name: str = Field(default="", max_length=128)
    mode: RunMode = "full_pipeline"
    attack_config_dir: str = "configs/gpt-5.4"
    benchmark_config_path: str = ""
    eval_profile: str = "full"
    results_root: str = "data/attack_results"
    result_manifest: str = ""
    quick_attack_enabled: bool = False
    quick_target_model_name: str = "gpt-4o-mini"
    quick_openai_base_url: str = ""
    quick_openai_api_key: str = ""
    quick_attack_methods: List[str] = Field(default_factory=lambda: ["pair", "cipher", "rene"])
    quick_dataset_key: str = "teleai_samples_500_500"

    @model_validator(mode="after")
    def _validate_eval_only_inputs(self):
        if self.mode == "eval_only" and not self.result_manifest.strip():
            raise ValueError("eval_only mode requires non-empty result_manifest")
        return self


class RunStageRecord(BaseModel):
    stage: StageName
    status: StageStatus = "pending"
    command: str = ""
    log_path: str = ""
    started_at: Optional[datetime] = None
    updated_at: datetime
    ended_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    error: str = ""


class ArtifactRecord(BaseModel):
    artifact_id: str
    stage: StageName
    type: str
    path: str
    size_bytes: int = 0
    created_at: datetime


class RunRecord(BaseModel):
    run_id: str
    name: str
    mode: RunMode
    status: RunStatus
    attack_config_dir: str
    benchmark_config_path: str
    eval_profile: str
    results_root: str
    result_manifest: str = ""
    quick_attack_enabled: bool = False
    quick_target_model_name: str = "gpt-4o-mini"
    quick_openai_base_url: str = ""
    quick_attack_methods: List[str] = Field(default_factory=list)
    quick_dataset_key: str = "teleai_samples_500_500"
    created_at: datetime
    updated_at: datetime
    ended_at: Optional[datetime] = None
    error: str = ""
    stages: List[RunStageRecord] = Field(default_factory=list)
    artifacts: List[ArtifactRecord] = Field(default_factory=list)
    metric_summary: dict = Field(default_factory=dict)


def stages_for_mode(mode: RunMode) -> List[StageName]:
    if mode == "attack_only":
        return ["attack"]
    if mode == "benchmark_only":
        return ["benchmark"]
    if mode == "eval_only":
        return ["evaluate"]
    return ["attack", "benchmark", "evaluate"]


def new_run_record(payload: RunCreate) -> RunRecord:
    now = datetime.utcnow()
    run_name = payload.name.strip() or f"run-{now.strftime('%Y%m%d-%H%M%S')}"
    stage_names = stages_for_mode(payload.mode)
    stages = [
        RunStageRecord(
            stage=stage_name,
            status="pending",
            updated_at=now,
        )
        for stage_name in stage_names
    ]
    return RunRecord(
        run_id=str(uuid4()),
        name=run_name,
        mode=payload.mode,
        status="pending",
        attack_config_dir=payload.attack_config_dir,
        benchmark_config_path=payload.benchmark_config_path,
        eval_profile=payload.eval_profile,
        results_root=payload.results_root,
        result_manifest=payload.result_manifest,
        quick_attack_enabled=payload.quick_attack_enabled,
        quick_target_model_name=payload.quick_target_model_name,
        quick_openai_base_url=payload.quick_openai_base_url,
        quick_attack_methods=payload.quick_attack_methods,
        quick_dataset_key=payload.quick_dataset_key,
        created_at=now,
        updated_at=now,
        stages=stages,
    )


def default_attack_run_id(run_id: str) -> str:
    compact = run_id.replace("-", "")
    return compact[:16]


def default_manifest_path(results_root: str, attack_config_dir: str, run_id: str) -> str:
    cfg_tag = Path(attack_config_dir).name
    return str(Path(results_root) / "manifests" / f"{cfg_tag}_{default_attack_run_id(run_id)}.txt")


def new_artifact(stage: StageName, type_name: str, path: str, size_bytes: int = 0) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=str(uuid4()),
        stage=stage,
        type=type_name,
        path=path,
        size_bytes=size_bytes,
        created_at=datetime.utcnow(),
    )
