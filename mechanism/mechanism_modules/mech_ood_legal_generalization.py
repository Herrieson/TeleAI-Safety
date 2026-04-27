from pathlib import Path
from typing import Dict, Tuple

from .common import JUDGE_FILES, eval_judge_file


MECHANISM_ID = "H1_H2_H3"
MECHANISM_NAME = "OOD与泛化脆弱性"
SCORE_DIRECTION = "higher_better"
METRIC_DIRECTIONS = {"法律综合可靠性": "higher_better"}


def _candidate_model_ids(model_id: str) -> Tuple[str, ...]:
    base = [model_id]
    if model_id == "minmax-m2.5":
        base.append("minimax-m2.5")
    if model_id == "qwen3.5-397b":
        base.append("qwen-3.5")
    return tuple(base)


def _resolve_model_dir(judge_root: Path, model_id: str) -> Path:
    for candidate in _candidate_model_ids(model_id):
        p = judge_root / candidate
        if p.exists():
            return p
    return judge_root / model_id


def _resolve_judge_file(model_dir: Path, default_relative: str) -> Path:
    direct = model_dir / default_relative
    if direct.exists():
        return direct
    parts = Path(default_relative).parts
    if len(parts) >= 2:
        prefix = parts[0]
        suffix = parts[-1]
        for sub in model_dir.glob(f"{prefix}*"):
            candidate = sub / suffix
            if candidate.exists():
                return candidate
    return direct


def compute(model_id: str, data_paths: Dict[str, Path]) -> dict:
    judge_root = _resolve_model_dir(data_paths["judge_root"], model_id)
    h1_path, h1_scale = JUDGE_FILES["H1"]
    h2_path, h2_scale = JUDGE_FILES["H2"]
    h3_path, h3_scale = JUDGE_FILES["H3"]
    h1 = eval_judge_file(_resolve_judge_file(judge_root, h1_path), h1_scale)
    h2 = eval_judge_file(_resolve_judge_file(judge_root, h2_path), h2_scale)
    h3 = eval_judge_file(_resolve_judge_file(judge_root, h3_path), h3_scale)
    values = [h1["mean_norm"], h2["mean_norm"], h3["mean_norm"]]
    valid_values = [v for v in values if isinstance(v, (int, float))]
    law_composite = None if not valid_values else sum(valid_values) / len(valid_values)
    return {
        "mechanism_id": MECHANISM_ID,
        "mechanism_name": MECHANISM_NAME,
        "score_direction": SCORE_DIRECTION,
        "metric_directions": METRIC_DIRECTIONS,
        "metrics": {"法律综合可靠性": law_composite},
        "mechanism_explanation": "法条依据可靠性不足，OOD法律泛化弱",
        "vulnerability_mechanism": "训练分布外法律问题上语义映射失真，导致依据错配与推理迁移失败",
        "missing_capability": "OOD鲁棒性、风险外推能力、新任务安全迁移能力",
        "improvement": "构建极端/组合/反直觉法律安全评测集；引入风险不确定性估计与保守生成；迁移阶段同步安全再对齐",
    }
