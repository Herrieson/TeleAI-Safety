import csv
import os
import shlex
import subprocess
import copy
import shutil
from pathlib import Path
from threading import Lock, Thread
from typing import Dict, List, Optional, Tuple

import yaml

from .config import settings
from .dataset_catalog import resolve_quick_dataset_path
from .models import RunRecord, default_attack_run_id, new_artifact
from .secret_store import secret_store
from .store import run_store


_active_processes: Dict[str, subprocess.Popen] = {}
_active_lock = Lock()


def list_quick_supported_methods() -> List[str]:
    template_root = settings.repo_root / "attack" / "configs" / "gpt-4o"
    methods_dir = settings.repo_root / "attack" / "methods"
    supported: List[str] = []
    if not template_root.exists():
        return supported
    for template in sorted(template_root.glob("*.yaml")):
        method_name = template.stem
        script_path = methods_dir / f"{method_name}.py"
        if script_path.exists():
            supported.append(method_name)
    return supported


def start_run_execution(run_id: str) -> None:
    worker = Thread(target=_execute_run, args=(run_id,), daemon=True)
    worker.start()


def cancel_run_execution(run_id: str) -> bool:
    proc = _get_active_process(run_id)
    if proc is None:
        return False
    if proc.poll() is not None:
        return False
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
    return True


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return settings.repo_root / path


def _run_dir(run_id: str) -> Path:
    return settings.run_log_root / run_id


def _run_attack_results_root(run_id: str) -> Path:
    return settings.repo_root / "data" / "attack_results" / "runs" / run_id


def _run_attack_manifest_path(run_id: str) -> Path:
    return _run_dir(run_id) / "attack" / "manifest.txt"


def _run_benchmark_output_root(run_id: str) -> Path:
    return settings.repo_root / "benchmark" / "result" / "runs" / run_id


def _run_evaluate_report_root(run_id: str) -> Path:
    return settings.repo_root / "evaluate" / "evaluation_report" / "runs" / run_id


def run_scoped_paths(run_id: str) -> List[Path]:
    return [
        _run_dir(run_id),
        _run_attack_results_root(run_id),
        _run_benchmark_output_root(run_id),
        _run_evaluate_report_root(run_id),
    ]


def delete_run_artifacts(run_id: str) -> Dict[str, object]:
    removed: List[str] = []
    failed: List[str] = []
    for path in run_scoped_paths(run_id):
        if not path.exists():
            continue
        try:
            shutil.rmtree(path)
            removed.append(str(path))
        except OSError:
            failed.append(str(path))
    return {
        "removed_paths": removed,
        "failed_paths": failed,
        "removed_count": len(removed),
        "failed_count": len(failed),
    }


def _execute_run(run_id: str) -> None:
    try:
        run = run_store.get(run_id)
        if run is None:
            return
        run_store.update_status(run_id, "running", error="")

        for stage in run.stages:
            current = run_store.get(run_id)
            if current is None:
                return
            if current.status == "canceled":
                return
            if stage.stage == "attack":
                ok, message = _run_attack_stage(current)
            elif stage.stage == "benchmark":
                ok, message = _run_benchmark_stage(current)
            elif stage.stage == "evaluate":
                ok, message = _run_evaluate_stage(current)
            else:
                run_store.update_stage(run_id, stage.stage, "failed", error=f"unknown stage: {stage.stage}")
                run_store.update_status(run_id, "failed", error=f"unknown stage: {stage.stage}")
                return

            if not ok:
                if message == "canceled":
                    return
                run_store.update_status(run_id, "failed", error=message)
                return

        run_store.update_status(run_id, "succeeded", error="")
    finally:
        secret_store.pop(run_id)


def _run_attack_stage(run: RunRecord) -> Tuple[bool, str]:
    run_id = run.run_id
    stage = "attack"
    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "attack.log"
    results_root_abs = _run_attack_results_root(run_id)
    results_root_abs.mkdir(parents=True, exist_ok=True)
    run_store.update_results_root(run_id, str(results_root_abs))
    manifest_path = _run_attack_manifest_path(run_id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    attack_config_dir, generated_config_dir, err = _prepare_attack_configs_for_run(run)
    if err:
        _write_log_lines(log_path, [f"[executor] attack config generation failed: {err}"])
        run_store.update_stage(
            run_id,
            stage,
            "failed",
            command="(auto-generate attack configs)",
            log_path=str(log_path),
            exit_code=1,
            error=err,
        )
        run_store.add_artifacts(run_id, [new_artifact(stage, "stage_log", str(log_path), log_path.stat().st_size)])
        return False, err
    run_store.update_attack_config_dir(run_id, str(attack_config_dir))

    attack_script = settings.repo_root / "attack" / "run_attack_parallel.sh"
    cmd = ["bash", str(attack_script)]
    cmd_str = " ".join(shlex.quote(part) for part in cmd)
    env = os.environ.copy()
    env.update(
        {
            "RUN_ID": default_attack_run_id(run_id),
            "CONFIG_DIR": str(attack_config_dir),
            "RESULTS_ROOT": str(results_root_abs),
            "MANIFEST_PATH": str(manifest_path),
        }
    )

    run_store.update_stage(
        run_id,
        stage,
        "running",
        command=cmd_str,
        log_path=str(log_path),
        error="",
    )

    rc = _run_cmd(
        run_id=run_id,
        stage=stage,
        cmd=cmd,
        env=env,
        log_path=log_path,
        preface_lines=[
            f"[executor] run_id={run_id}",
            "[executor] stage=attack",
            f"[executor] command={cmd_str}",
            f"[executor] cwd={settings.repo_root}",
            f"[executor] CONFIG_DIR={attack_config_dir}",
            f"[executor] RESULTS_ROOT={results_root_abs}",
            f"[executor] MANIFEST_PATH={manifest_path}",
            f"[executor] quick_attack_enabled={run.quick_attack_enabled}",
        ],
    )
    if _is_run_canceled(run_id):
        run_store.update_stage(
            run_id,
            stage,
            "canceled",
            exit_code=rc,
            error="canceled by user",
        )
        artifacts = _collect_attack_artifacts(log_path=log_path, manifest_path=manifest_path)
        if artifacts:
            run_store.add_artifacts(run_id, artifacts)
        return False, "canceled"

    artifacts = _collect_attack_artifacts(log_path=log_path, manifest_path=manifest_path)
    if generated_config_dir:
        artifacts.extend(_collect_generated_config_artifacts(generated_config_dir))
    if artifacts:
        run_store.add_artifacts(run_id, artifacts)
    if manifest_path.exists():
        run_store.set_result_manifest(run_id, str(manifest_path))

    if rc != 0:
        run_store.update_stage(
            run_id,
            stage,
            "failed",
            exit_code=rc,
            error=f"attack stage exited with code {rc}",
        )
        return False, f"attack stage exited with code {rc}"

    run_store.update_stage(
        run_id,
        stage,
        "succeeded",
        exit_code=rc,
        error="",
    )
    return True, ""


def _run_benchmark_stage(run: RunRecord) -> Tuple[bool, str]:
    run_id = run.run_id
    stage = "benchmark"
    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "benchmark.log"

    cfg_raw = run.benchmark_config_path.strip()
    if not cfg_raw:
        _write_log_lines(log_path, ["[executor] benchmark skipped: benchmark_config_path is empty"])
        run_store.update_stage(
            run_id,
            stage,
            "succeeded",
            command="(skipped: benchmark_config_path is empty)",
            log_path=str(log_path),
            exit_code=0,
        )
        run_store.add_artifacts(run_id, [new_artifact(stage, "stage_log", str(log_path), log_path.stat().st_size)])
        return True, ""

    config_path = _resolve_path(cfg_raw)
    if not config_path.exists():
        _write_log_lines(log_path, [f"[executor] benchmark config not found: {config_path}"])
        run_store.update_stage(
            run_id,
            stage,
            "failed",
            command=f"uv run python benchmark/cli.py --config {config_path}",
            log_path=str(log_path),
            exit_code=1,
            error=f"benchmark config not found: {config_path}",
        )
        run_store.add_artifacts(run_id, [new_artifact(stage, "stage_log", str(log_path), log_path.stat().st_size)])
        return False, f"benchmark config not found: {config_path}"

    runtime_config_path, benchmark_output_root, patch_err = _prepare_benchmark_config_for_run(run, config_path)
    if patch_err:
        _write_log_lines(log_path, [f"[executor] benchmark config patch failed: {patch_err}"])
        run_store.update_stage(
            run_id,
            stage,
            "failed",
            command=f"uv run python benchmark/cli.py --config {config_path}",
            log_path=str(log_path),
            exit_code=1,
            error=patch_err,
        )
        run_store.add_artifacts(run_id, [new_artifact(stage, "stage_log", str(log_path), log_path.stat().st_size)])
        return False, patch_err

    cmd = ["uv", "run", "python", "benchmark/cli.py", "--config", str(runtime_config_path)]
    cmd_str = " ".join(shlex.quote(part) for part in cmd)
    env = os.environ.copy()

    run_store.update_stage(
        run_id,
        stage,
        "running",
        command=cmd_str,
        log_path=str(log_path),
        error="",
    )
    rc = _run_cmd(
        run_id=run_id,
        stage=stage,
        cmd=cmd,
        env=env,
        log_path=log_path,
        preface_lines=[
            f"[executor] run_id={run_id}",
            "[executor] stage=benchmark",
            f"[executor] command={cmd_str}",
            f"[executor] source_config={config_path}",
            f"[executor] runtime_config={runtime_config_path}",
            f"[executor] BENCHMARK_OUTPUT_ROOT={benchmark_output_root}",
        ],
    )

    artifacts = [new_artifact(stage, "stage_log", str(log_path), size_bytes=log_path.stat().st_size)]
    artifacts.append(
        new_artifact(
            stage,
            "generated_config",
            str(runtime_config_path),
            size_bytes=runtime_config_path.stat().st_size,
        )
    )
    artifacts.extend(_collect_benchmark_artifacts(runtime_config_path))
    run_store.add_artifacts(run_id, artifacts)

    if _is_run_canceled(run_id):
        run_store.update_stage(run_id, stage, "canceled", exit_code=rc, error="canceled by user")
        return False, "canceled"
    if rc != 0:
        run_store.update_stage(run_id, stage, "failed", exit_code=rc, error=f"benchmark stage exited with code {rc}")
        return False, f"benchmark stage exited with code {rc}"

    run_store.update_stage(run_id, stage, "succeeded", exit_code=rc, error="")
    return True, ""


def _run_evaluate_stage(run: RunRecord) -> Tuple[bool, str]:
    run_id = run.run_id
    stage = "evaluate"
    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "evaluate.log"

    results_root_abs = _run_attack_results_root(run_id)
    if not results_root_abs.exists():
        results_root_abs = _resolve_path(run.results_root)
    manifest_path = _resolve_manifest(run)
    eval_report_root = _run_evaluate_report_root(run_id)
    eval_report_root.mkdir(parents=True, exist_ok=True)

    eval_profile = (run.eval_profile or "full").strip().lower() or "full"
    if settings.strict_cred_isolation and eval_profile != "smoke":
        if not settings.use_internal_llm_for_evaluate:
            err = "strict credential isolation enabled: TELEAI_USE_INTERNAL_LLM_FOR_EVALUATE must be true"
            _write_log_lines(log_path, [f"[executor] {err}"])
            run_store.update_stage(
                run_id,
                stage,
                "failed",
                command="(evaluate precheck)",
                log_path=str(log_path),
                exit_code=1,
                error=err,
            )
            run_store.add_artifacts(run_id, [new_artifact(stage, "stage_log", str(log_path), log_path.stat().st_size)])
            return False, err
        if not settings.internal_llm_api_key or not settings.internal_llm_base_url:
            err = (
                "strict credential isolation enabled: missing TELEAI_INTERNAL_LLM_API_KEY "
                "or TELEAI_INTERNAL_LLM_BASE_URL for evaluate stage"
            )
            _write_log_lines(log_path, [f"[executor] {err}"])
            run_store.update_stage(
                run_id,
                stage,
                "failed",
                command="(evaluate precheck)",
                log_path=str(log_path),
                exit_code=1,
                error=err,
            )
            run_store.add_artifacts(run_id, [new_artifact(stage, "stage_log", str(log_path), log_path.stat().st_size)])
            return False, err

    eval_script = settings.repo_root / "evaluate" / "eval_demo.sh"
    cmd = ["bash", str(eval_script)]
    cmd_str = " ".join(shlex.quote(part) for part in cmd)

    env = os.environ.copy()
    env.update(
        {
            "RESULTS_DIR": str(results_root_abs),
            "EVAL_PROFILE": eval_profile,
            "EVAL_REPORT_ROOT": str(eval_report_root),
            "OUTPUT_ROOT": str(eval_report_root / "asr"),
            "FRR_OUTPUT_ROOT": str(eval_report_root / "frr"),
            "ASR_LABEL_ROOT": str(eval_report_root / "asr_labels"),
            "FRR_LABEL_ROOT": str(eval_report_root / "frr_labels"),
            "TERNARY_LABEL_ROOT": str(eval_report_root / "ternary_labels"),
        }
    )
    if settings.use_internal_llm_for_evaluate:
        if settings.internal_llm_api_key:
            env["OPENAI_API_KEY"] = settings.internal_llm_api_key
        if settings.internal_llm_base_url:
            env["OPENAI_BASE_URL"] = settings.internal_llm_base_url
        if settings.internal_llm_model:
            env["TELEAI_INTERNAL_EVAL_MODEL"] = settings.internal_llm_model
    if manifest_path and manifest_path.exists():
        env["RESULT_MANIFEST"] = str(manifest_path)

    run_store.update_stage(
        run_id,
        stage,
        "running",
        command=cmd_str,
        log_path=str(log_path),
        error="",
    )

    rc = _run_cmd(
        run_id=run_id,
        stage=stage,
        cmd=cmd,
        env=env,
        log_path=log_path,
        preface_lines=[
            f"[executor] run_id={run_id}",
            "[executor] stage=evaluate",
            f"[executor] command={cmd_str}",
            f"[executor] RESULTS_DIR={results_root_abs}",
            f"[executor] RESULT_MANIFEST={manifest_path if manifest_path else ''}",
            f"[executor] EVAL_PROFILE={eval_profile}",
            f"[executor] EVAL_REPORT_ROOT={eval_report_root}",
        ],
    )

    artifacts = _collect_evaluate_artifacts(log_path, eval_report_root)
    if artifacts:
        run_store.add_artifacts(run_id, artifacts)

    summary = _load_metric_summary(eval_report_root)
    if summary:
        run_store.update_metric_summary(run_id, summary)

    if _is_run_canceled(run_id):
        run_store.update_stage(run_id, stage, "canceled", exit_code=rc, error="canceled by user")
        return False, "canceled"
    if rc != 0:
        run_store.update_stage(run_id, stage, "failed", exit_code=rc, error=f"evaluate stage exited with code {rc}")
        return False, f"evaluate stage exited with code {rc}"

    run_store.update_stage(run_id, stage, "succeeded", exit_code=rc, error="")
    return True, ""


def _collect_attack_artifacts(log_path: Path, manifest_path: Path) -> List:
    artifacts = []
    if log_path.exists():
        artifacts.append(new_artifact("attack", "stage_log", str(log_path), size_bytes=log_path.stat().st_size))

    if not manifest_path.exists():
        return artifacts

    artifacts.append(
        new_artifact(
            "attack",
            "manifest",
            str(manifest_path),
            size_bytes=manifest_path.stat().st_size,
        )
    )

    for line in manifest_path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        result_path = Path(raw)
        if not result_path.is_absolute():
            result_path = settings.repo_root / result_path
        if not result_path.exists():
            continue
        artifacts.append(
            new_artifact(
                "attack",
                "attack_result",
                str(result_path),
                size_bytes=result_path.stat().st_size,
            )
        )
        timing_path = result_path.with_suffix(".timing.json")
        if timing_path.exists():
            artifacts.append(
                new_artifact(
                    "attack",
                    "timing_json",
                    str(timing_path),
                    size_bytes=timing_path.stat().st_size,
                )
            )
    return artifacts


def _collect_generated_config_artifacts(config_dir: Path) -> List:
    artifacts = []
    if not config_dir.exists():
        return artifacts
    for path in sorted(config_dir.glob("*.yaml")):
        artifacts.append(new_artifact("attack", "generated_config", str(path), size_bytes=path.stat().st_size))
    return artifacts


def _resolve_attack_config_dir(config_dir: str) -> Path:
    raw = Path(config_dir)
    if raw.is_absolute():
        return raw
    candidate_attack = settings.repo_root / "attack" / config_dir
    if candidate_attack.exists():
        return candidate_attack
    return settings.repo_root / config_dir


def _prepare_attack_configs_for_run(run: RunRecord) -> Tuple[Optional[Path], Optional[Path], str]:
    if run.quick_attack_enabled:
        config_dir, err = _prepare_quick_attack_configs(run)
        return config_dir, config_dir, err

    source_path = _resolve_attack_config_dir(run.attack_config_dir)
    if not source_path.exists():
        return None, None, f"attack config path not found: {source_path}"

    target_dir = _run_dir(run.run_id) / "generated_attack_configs"
    target_dir.mkdir(parents=True, exist_ok=True)
    result_root = _run_attack_results_root(run.run_id)
    result_root.mkdir(parents=True, exist_ok=True)

    yaml_files: List[Path] = []
    if source_path.is_dir():
        yaml_files.extend(sorted(source_path.glob("*.yaml")))
        yaml_files.extend(sorted(source_path.glob("*.yml")))
    elif source_path.is_file():
        if source_path.suffix.lower() not in {".yaml", ".yml"}:
            return None, None, f"attack config file must be .yaml or .yml: {source_path}"
        yaml_files.append(source_path)
    else:
        return None, None, f"unsupported attack config path type: {source_path}"

    if not yaml_files:
        return None, None, f"no *.yaml/*.yml found in attack config path: {source_path}"

    for cfg_path in yaml_files:
        cfg = _load_yaml(cfg_path)
        if not isinstance(cfg, dict):
            return None, None, f"invalid yaml object in attack config: {cfg_path}"
        method = cfg_path.stem
        patched = _patch_attack_config_output_for_run(cfg=cfg, result_root=result_root, method=method)
        out_path = target_dir / cfg_path.name
        with out_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(patched, f, sort_keys=False, allow_unicode=False)
    return target_dir, target_dir, ""


def _patch_attack_config_output_for_run(*, cfg: dict, result_root: Path, method: str) -> dict:
    out = copy.deepcopy(cfg)
    out["res_save_path"] = str(result_root / f"{method}.jsonl")
    return out


def _prepare_quick_attack_configs(run: RunRecord) -> Tuple[Optional[Path], str]:
    run_id = run.run_id
    quick_secret = secret_store.get(run_id) or {}
    target_api_key = (quick_secret.get("quick_openai_api_key") or "").strip()
    target_base_url = (run.quick_openai_base_url or "").strip()
    internal_api_key = settings.internal_llm_api_key if settings.use_internal_llm_for_attack else ""
    internal_base_url = settings.internal_llm_base_url if settings.use_internal_llm_for_attack else ""
    internal_model_name = settings.internal_llm_model.strip()

    strict_isolation = settings.strict_cred_isolation
    if strict_isolation:
        if not settings.use_internal_llm_for_attack:
            return None, "strict credential isolation enabled: TELEAI_USE_INTERNAL_LLM_FOR_ATTACK must be true"
        if not internal_api_key or not internal_base_url:
            return None, (
                "strict credential isolation enabled: missing TELEAI_INTERNAL_LLM_API_KEY "
                "or TELEAI_INTERNAL_LLM_BASE_URL for quick attack internal models"
            )
        if not target_api_key or not target_base_url:
            return None, (
                "strict credential isolation enabled: quick_openai_api_key and quick_openai_base_url "
                "are required for target model"
            )
        use_internal_for_non_target = True
    else:
        use_internal_for_non_target = bool(internal_api_key and internal_base_url)

    if use_internal_for_non_target:
        attack_api_key = internal_api_key
        attack_base_url = internal_base_url
    else:
        attack_api_key = target_api_key
        attack_base_url = target_base_url

    if not attack_api_key or not attack_base_url:
        return None, (
            "quick attack requires credentials: provide quick_openai_base_url/quick_openai_api_key "
            "or set TELEAI_INTERNAL_LLM_BASE_URL/TELEAI_INTERNAL_LLM_API_KEY"
        )

    if not strict_isolation and not target_api_key:
        target_api_key = attack_api_key
    if not strict_isolation and not target_base_url:
        target_base_url = attack_base_url

    raw_methods = run.quick_attack_methods or []
    methods = []
    seen = set()
    for method in raw_methods:
        name = method.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        methods.append(name)
    if not methods:
        return None, "quick_attack_methods cannot be empty when quick_attack_enabled=true"

    supported_methods = list_quick_supported_methods()
    unsupported = [name for name in methods if name not in supported_methods]
    if unsupported:
        return None, f"unsupported quick methods: {', '.join(unsupported)}"

    template_root = settings.repo_root / "attack" / "configs" / "gpt-4o"
    config_dir = settings.run_log_root / run_id / "generated_attack_configs"
    config_dir.mkdir(parents=True, exist_ok=True)

    model_name = (run.quick_target_model_name or "").strip()
    if not model_name:
        model_name = "gpt-4o-mini"

    data_path, dataset_err = resolve_quick_dataset_path(run.quick_dataset_key)
    if dataset_err:
        return None, dataset_err
    if not data_path:
        return None, "resolved dataset path is empty"
    result_root = _run_attack_results_root(run_id)
    result_root.mkdir(parents=True, exist_ok=True)

    for method in methods:
        template_path = template_root / f"{method}.yaml"
        if not template_path.exists():
            return None, f"template not found for method: {method}"
        cfg = _load_yaml(template_path)
        if not isinstance(cfg, dict):
            return None, f"invalid yaml object for method: {method}"

        patched = _patch_attack_config_for_quick_mode(
            cfg=cfg,
            target_model_name=model_name,
            internal_model_name=internal_model_name,
            attack_base_url=attack_base_url,
            attack_api_key=attack_api_key,
            target_base_url=target_base_url,
            target_api_key=target_api_key,
            use_internal_for_non_target=use_internal_for_non_target,
            data_path=data_path,
            method=method,
            result_root=result_root,
        )
        out_path = config_dir / f"{method}.yaml"
        with out_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(patched, f, sort_keys=False, allow_unicode=False)
    return config_dir, ""


def _patch_attack_config_for_quick_mode(
    *,
    cfg: dict,
    target_model_name: str,
    internal_model_name: str,
    attack_base_url: str,
    attack_api_key: str,
    target_base_url: str,
    target_api_key: str,
    use_internal_for_non_target: bool,
    data_path: str,
    method: str,
    result_root: Path,
) -> dict:
    out = dict(cfg)
    out["api_key"] = attack_api_key
    out["base_url"] = attack_base_url
    if "azure_key" in out:
        out["azure_key"] = target_api_key
    if "azure_url" in out:
        out["azure_url"] = target_base_url
    if "grok_key" in out:
        out["grok_key"] = None
    if "grok_url" in out:
        out["grok_url"] = None

    if "data_path" in out:
        out["data_path"] = data_path
    if "attack_data_path" in out:
        out["attack_data_path"] = data_path

    internal_model_prefixes = (
        "attack_",
        "attacker_",
        "eval_",
        "judge_",
        "rewrite_",
        "prompter_",
    )

    for key in list(out.keys()):
        if key == "target_model_type" or key == "model_type":
            out[key] = "openai_target" if use_internal_for_non_target else "openai"
            continue
        if key.endswith("_model_type"):
            if use_internal_for_non_target and key.startswith(internal_model_prefixes):
                out[key] = "openai"
            else:
                out[key] = "openai_target" if use_internal_for_non_target else "openai"
            continue

        if key == "target_model_name":
            out[key] = target_model_name
            continue
        if key.endswith("_model_name"):
            if use_internal_for_non_target and key.startswith(internal_model_prefixes):
                out[key] = internal_model_name or target_model_name
            else:
                out[key] = target_model_name

    out["res_save_path"] = str(result_root / f"{method}.jsonl")
    return out


def _prepare_benchmark_config_for_run(run: RunRecord, source_config_path: Path) -> Tuple[Path, Path, str]:
    run_id = run.run_id
    cfg = _load_yaml(source_config_path)
    if not isinstance(cfg, dict):
        return source_config_path, _run_benchmark_output_root(run_id), f"invalid yaml object: {source_config_path}"

    benchmark_output_root = _run_benchmark_output_root(run_id)
    benchmark_output_root.mkdir(parents=True, exist_ok=True)

    patched = copy.deepcopy(cfg)
    patched_model_err = _patch_benchmark_target_model_for_run(run=run, cfg=patched)
    if patched_model_err:
        return source_config_path, benchmark_output_root, patched_model_err
    patched["output_path"] = str(benchmark_output_root / "benchmark_results.jsonl")
    patched["summary_path"] = str(benchmark_output_root / "benchmark_summary.json")

    runtime_config_path = _run_dir(run_id) / "benchmark.runtime.yaml"
    with runtime_config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(patched, f, sort_keys=False, allow_unicode=False)
    return runtime_config_path, benchmark_output_root, ""


def _patch_benchmark_target_model_for_run(*, run: RunRecord, cfg: dict) -> str:
    model_cfg = cfg.get("model")
    if not isinstance(model_cfg, dict):
        return ""

    model_type = str(model_cfg.get("type") or "").strip().lower()
    if model_type == "local":
        return ""
    if model_type not in {"openai", "azure_openai"}:
        return ""

    quick_secret = secret_store.get(run.run_id) or {}
    target_api_key = (quick_secret.get("quick_openai_api_key") or "").strip()
    target_base_url = (run.quick_openai_base_url or "").strip()
    target_model_name = (run.quick_target_model_name or "").strip() or "gpt-4o-mini"

    if not target_api_key or not target_base_url:
        return (
            "benchmark target model credentials are required: please provide target OpenAI base_url/api_key "
            "(quick_openai_base_url + quick_openai_api_key)"
        )

    patched_model = copy.deepcopy(model_cfg)
    patched_model["type"] = "openai"
    patched_model["name"] = target_model_name
    patched_model["api_key"] = target_api_key
    patched_model["base_url"] = target_base_url

    # Normalize to OpenAI-compatible fields; judge config stays untouched.
    patched_model.pop("deployment", None)
    patched_model.pop("azure_endpoint", None)
    patched_model.pop("api_version", None)

    cfg["model"] = patched_model
    return ""


def _collect_benchmark_artifacts(config_path: Path) -> List:
    artifacts = []
    cfg = _load_yaml(config_path)
    for key, type_name in (("output_path", "benchmark_output"), ("summary_path", "benchmark_summary")):
        value = cfg.get(key) if isinstance(cfg, dict) else None
        if not value:
            continue
        path = _resolve_path(os.path.expandvars(str(value)))
        if not path.exists():
            continue
        artifacts.append(new_artifact("benchmark", type_name, str(path), size_bytes=path.stat().st_size))
    return artifacts


def _collect_evaluate_artifacts(log_path: Path, eval_root: Path) -> List:
    artifacts = []
    if log_path.exists():
        artifacts.append(new_artifact("evaluate", "stage_log", str(log_path), size_bytes=log_path.stat().st_size))

    if not eval_root.exists():
        return artifacts
    for path in sorted(eval_root.rglob("*")):
        if not path.is_file():
            continue
        artifacts.append(new_artifact("evaluate", "evaluate_report", str(path), size_bytes=path.stat().st_size))
    return artifacts


def _load_metric_summary(eval_root: Path) -> dict:
    summary_long = eval_root / "asr" / "summary_long.csv"
    if not summary_long.exists():
        return {}

    asr_vals = []
    asr_effective_vals = []
    frr_vals = []
    scorers = set()
    attack_runs = set()
    rows = 0
    with summary_long.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows += 1
            attack_run = (row.get("attack_run") or "").strip()
            scorer = (row.get("scorer") or "").strip()
            if attack_run:
                attack_runs.add(attack_run)
            if scorer:
                scorers.add(scorer)
            try:
                asr_vals.append(float(row.get("asr", "")))
            except (TypeError, ValueError):
                pass
            try:
                asr_effective_vals.append(float(row.get("asr_effective", "")))
            except (TypeError, ValueError):
                pass
            try:
                frr_vals.append(float(row.get("frr", "")))
            except (TypeError, ValueError):
                pass

    def _avg(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return sum(values) / len(values)

    return {
        "rows": rows,
        "attack_run_count": len(attack_runs),
        "scorer_count": len(scorers),
        "asr_avg": _avg(asr_vals),
        "asr_effective_avg": _avg(asr_effective_vals),
        "frr_avg": _avg(frr_vals),
        "scorers": sorted(scorers),
    }


def _resolve_manifest(run: RunRecord) -> Optional[Path]:
    if run.result_manifest.strip():
        path = _resolve_path(run.result_manifest.strip())
        if path.exists():
            return path

    for artifact in reversed(run.artifacts):
        if artifact.type == "manifest":
            path = Path(artifact.path)
            if path.exists():
                return path

    run_local_manifest = _run_attack_manifest_path(run.run_id)
    if run_local_manifest.exists():
        return run_local_manifest

    fallback_global = _resolve_path(run.results_root) / "manifests"
    if fallback_global.exists():
        candidates = sorted(fallback_global.glob("*.txt"))
        if candidates:
            return candidates[-1]
    return None


def _load_yaml(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except OSError:
        return {}


def _write_log_lines(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def _run_cmd(
    *,
    run_id: str,
    stage: str,
    cmd: List[str],
    env: Dict[str, str],
    log_path: Path,
    preface_lines: List[str],
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as logf:
        for line in preface_lines:
            logf.write(line + "\n")
        logf.write("\n")
        logf.flush()

        proc = subprocess.Popen(
            cmd,
            cwd=str(settings.repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _set_active_process(run_id, proc)
        try:
            if proc.stdout is not None:
                for line in proc.stdout:
                    logf.write(line)
            return proc.wait()
        finally:
            _clear_active_process(run_id)


def _is_run_canceled(run_id: str) -> bool:
    current = run_store.get(run_id)
    return bool(current and current.status == "canceled")


def _set_active_process(run_id: str, proc: subprocess.Popen) -> None:
    with _active_lock:
        _active_processes[run_id] = proc


def _clear_active_process(run_id: str) -> None:
    with _active_lock:
        _active_processes.pop(run_id, None)


def _get_active_process(run_id: str) -> Optional[subprocess.Popen]:
    with _active_lock:
        return _active_processes.get(run_id)
