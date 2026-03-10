#!/usr/bin/env python3
"""Evaluate all existing benchmark result JSONL files in one command.

This script re-scores previously generated model responses under benchmark/result
without re-generating model outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml

_BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BENCHMARK_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmark.runners import BenchmarkPipeline


_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


@dataclass
class EvalJob:
    input_path: Path
    template_config: Path
    output_path: Path
    summary_path: Path
    task: str


def _expand_env_vars(value):
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(v) for v in value]
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(_replace_env_var, value)
    return value


def _replace_env_var(match: re.Match) -> str:
    var_name = match.group(1)
    if var_name not in os.environ:
        raise ValueError(f"Missing required environment variable: {var_name}")
    return os.environ[var_name]


def _load_config_template(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Invalid YAML object in {path}")
    return cfg


def _task_and_template(path: Path, config_root: Path) -> Optional[tuple[str, Path]]:
    posix_path = path.as_posix()
    if "/code_merged/" in posix_path:
        return "code_security", config_root / "code_security_eval_from_result_jsonl.yaml"
    if "hallucinations_merged_law_text" in posix_path:
        return "hallucinations_law_text", config_root / "hallucinations_law_text_eval.yaml"
    if "hallucinations_merged_legal_basics" in posix_path:
        return "hallucinations_legal_basics", config_root / "hallucinations_legal_basics_eval.yaml"
    if "hallucinations_merged_scenario" in posix_path:
        return "hallucinations_scenario", config_root / "hallucinations_scenario_eval.yaml"
    return None


def discover_jobs(
    result_dir: Path,
    config_root: Path,
    output_root: Path,
    include_existing_eval: bool = False,
) -> List[EvalJob]:
    jobs: List[EvalJob] = []
    for input_path in sorted(result_dir.rglob("benchmark_results.jsonl")):
        rel = input_path.relative_to(result_dir)
        rel_posix = rel.as_posix()
        if not include_existing_eval and (
            rel_posix.startswith("eval_from_result/")
            or rel_posix.startswith("eval_from_result_auto/")
        ):
            continue
        mapping = _task_and_template(input_path, config_root)
        if mapping is None:
            continue
        task, template = mapping
        output_dir = output_root / rel.parent
        output_path = output_dir / "benchmark_results.jsonl"
        summary_path = output_dir / "benchmark_summary.json"
        jobs.append(
            EvalJob(
                input_path=input_path,
                template_config=template,
                output_path=output_path,
                summary_path=summary_path,
                task=task,
            )
        )
    return jobs


def build_runtime_config(
    template_path: Path,
    input_path: Path,
    output_path: Path,
    summary_path: Path,
    num_workers: Optional[int],
    progress_bar: Optional[bool],
) -> Dict:
    cfg = _load_config_template(template_path)
    cfg.setdefault("dataset", {})
    cfg["dataset"]["path"] = str(input_path)
    cfg["output_path"] = str(output_path)
    cfg["summary_path"] = str(summary_path)
    if num_workers is not None:
        cfg["num_workers"] = int(num_workers)
    if progress_bar is not None:
        cfg["progress_bar"] = bool(progress_bar)
    return _expand_env_vars(cfg)


def run_jobs(
    jobs: Iterable[EvalJob],
    num_workers: Optional[int],
    progress_bar: Optional[bool],
    dry_run: bool,
    fail_fast: bool,
) -> List[Dict]:
    reports: List[Dict] = []
    for idx, job in enumerate(jobs, start=1):
        print(
            f"[{idx}] {job.task}: {job.input_path} -> {job.summary_path}",
            flush=True,
        )
        if dry_run:
            reports.append(
                {
                    "status": "dry_run",
                    "task": job.task,
                    "input_path": str(job.input_path),
                    "output_path": str(job.output_path),
                    "summary_path": str(job.summary_path),
                }
            )
            continue
        try:
            job.output_path.parent.mkdir(parents=True, exist_ok=True)
            cfg = build_runtime_config(
                template_path=job.template_config,
                input_path=job.input_path,
                output_path=job.output_path,
                summary_path=job.summary_path,
                num_workers=num_workers,
                progress_bar=progress_bar,
            )
            metric = BenchmarkPipeline(cfg).run()
            reports.append(
                {
                    "status": "ok",
                    "task": job.task,
                    "input_path": str(job.input_path),
                    "output_path": str(job.output_path),
                    "summary_path": str(job.summary_path),
                    "overall": metric.overall,
                }
            )
        except Exception as exc:
            reports.append(
                {
                    "status": "failed",
                    "task": job.task,
                    "input_path": str(job.input_path),
                    "output_path": str(job.output_path),
                    "summary_path": str(job.summary_path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            print(f"    FAILED: {type(exc).__name__}: {exc}", flush=True)
            if fail_fast:
                break
    return reports


def _write_report(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    result_dir = _BENCHMARK_ROOT / "result"
    config_root = _BENCHMARK_ROOT / "configs" / "run" / "eval_from_result"
    output_root = result_dir / "eval_from_result_auto"
    parser = argparse.ArgumentParser(
        description="Evaluate all benchmark/result/*/benchmark_results.jsonl files."
    )
    parser.add_argument(
        "--result-dir",
        type=Path,
        default=result_dir,
        help=f"Input result root (default: {result_dir})",
    )
    parser.add_argument(
        "--config-root",
        type=Path,
        default=config_root,
        help=f"Template config root (default: {config_root})",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=output_root,
        help=f"Output root for evaluated files (default: {output_root})",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=None,
        help="Override num_workers in template configs.",
    )
    parser.add_argument(
        "--progress-bar",
        dest="progress_bar",
        action="store_true",
        help="Force enable progress bar for each job.",
    )
    parser.add_argument(
        "--no-progress-bar",
        dest="progress_bar",
        action="store_false",
        help="Force disable progress bar for each job.",
    )
    parser.set_defaults(progress_bar=None)
    parser.add_argument(
        "--include-existing-eval",
        action="store_true",
        help="Also include result/eval_from_result* inputs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print discovered jobs without executing.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately when a job fails.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Optional report jsonl path. Default: <output_root>/eval_jobs_report.jsonl",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result_dir = args.result_dir.resolve()
    config_root = args.config_root.resolve()
    output_root = args.output_root.resolve()
    report_path = args.report_path or (output_root / "eval_jobs_report.jsonl")

    if not result_dir.exists():
        raise FileNotFoundError(f"Result dir not found: {result_dir}")
    if not config_root.exists():
        raise FileNotFoundError(f"Config root not found: {config_root}")

    jobs = discover_jobs(
        result_dir=result_dir,
        config_root=config_root,
        output_root=output_root,
        include_existing_eval=args.include_existing_eval,
    )
    if not jobs:
        print("No matched benchmark_results.jsonl files found.")
        return

    print(f"Discovered {len(jobs)} jobs.", flush=True)
    reports = run_jobs(
        jobs=jobs,
        num_workers=args.num_workers,
        progress_bar=args.progress_bar,
        dry_run=args.dry_run,
        fail_fast=args.fail_fast,
    )
    _write_report(report_path, reports)

    ok_count = sum(1 for r in reports if r.get("status") == "ok")
    fail_count = sum(1 for r in reports if r.get("status") == "failed")
    dry_count = sum(1 for r in reports if r.get("status") == "dry_run")
    print(
        f"Done. ok={ok_count}, failed={fail_count}, dry_run={dry_count}. "
        f"report={report_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
