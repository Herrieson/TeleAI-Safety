#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from pathlib import Path

import yaml


def _load_records(path: Path):
    if path.suffix == ".json":
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    if path.suffix == ".jsonl":
        records = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        return records
    raise ValueError(f"Unsupported data file type: {path}")


def _write_records(records, path: Path):
    if path.suffix == ".json":
        with path.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)
        return
    if path.suffix == ".jsonl":
        with path.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return
    raise ValueError(f"Unsupported data file type: {path}")


def _split_records(records, shards):
    total = len(records)
    base = total // shards
    rem = total % shards
    out = []
    start = 0
    for i in range(shards):
        size = base + (1 if i < rem else 0)
        out.append(records[start:start + size])
        start += size
    return out


def _resolve_path(path_str, root: Path):
    path = Path(path_str)
    if path.is_absolute():
        return path
    return root / path


def _run_one(shard_idx, method_path, cfg_path, log_path, cwd):
    start = time.monotonic()
    with log_path.open("w", encoding="utf-8") as logf:
        proc = subprocess.run(
            [sys.executable, str(method_path), "--config_path", str(cfg_path)],
            cwd=str(cwd),
            stdout=logf,
            stderr=subprocess.STDOUT,
            check=False,
        )
        elapsed = time.monotonic() - start
        logf.write(f"\n[parallel_attack] shard={shard_idx} elapsed_sec={elapsed:.3f}\n")
    return shard_idx, proc.returncode, elapsed


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
    return count


def _print_progress(total, completed, tmp_results, tmp_logs, start_ts):
    elapsed = int(time.time() - start_ts)
    shards = []
    for i, log_path in enumerate(tmp_logs):
        if tmp_results:
            line_count = _count_lines(tmp_results[i])
            shards.append(f"shard{i}:{line_count} lines")
        else:
            size_kb = log_path.stat().st_size // 1024 if log_path.exists() else 0
            shards.append(f"shard{i}:{size_kb}KB log")
    shard_summary = " | ".join(shards)
    print(f"[progress] done {completed}/{total} | {elapsed}s | {shard_summary}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Run attack method in parallel by sharding data.")
    parser.add_argument("--method", required=True, help="Path to attack method script (e.g., methods/pair.py).")
    parser.add_argument("--config", required=True, help="Path to YAML config file.")
    parser.add_argument("--shards", type=int, required=True, help="Number of data shards.")
    parser.add_argument("--max-workers", type=int, default=None, help="Max parallel workers (default: shards).")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary shard files.")
    parser.add_argument("--progress-interval", type=int, default=15, help="Progress report interval in seconds (0 to disable).")
    args = parser.parse_args()

    root = Path.cwd()
    method_path = _resolve_path(args.method, root)
    config_path = _resolve_path(args.config, root)

    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    data_path = _resolve_path(cfg["data_path"], root)
    data_offset = int(cfg.get("data_offset", 0))
    res_save_path = cfg.get("res_save_path")
    res_save_path = _resolve_path(res_save_path, root) if res_save_path else None

    records = _load_records(data_path)
    if data_offset:
        records = records[data_offset:]

    shards = max(1, int(args.shards))
    split = _split_records(records, shards)

    tmp_root = Path(tempfile.mkdtemp(prefix="parallel_attack_", dir=None))
    tmp_configs = []
    tmp_results = []
    tmp_logs = []

    data_suffix = data_path.suffix
    res_suffix = res_save_path.suffix if res_save_path else ".jsonl"

    for i, shard_records in enumerate(split):
        shard_data = tmp_root / f"data_shard_{i}{data_suffix}"
        _write_records(shard_records, shard_data)

        shard_cfg = dict(cfg)
        shard_cfg["data_path"] = str(shard_data)
        if "data_offset" in cfg:
            shard_cfg["data_offset"] = 0

        if res_save_path:
            shard_res = tmp_root / f"res_shard_{i}{res_suffix}"
            shard_cfg["res_save_path"] = str(shard_res)
            tmp_results.append(shard_res)
        else:
            shard_res = None

        cfg_path = tmp_root / f"config_shard_{i}.yaml"
        with cfg_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(shard_cfg, f, sort_keys=False, allow_unicode=False)

        tmp_configs.append(cfg_path)
        tmp_logs.append(tmp_root / f"shard_{i}.log")

    max_workers = args.max_workers or shards
    failures = []
    shard_timings = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = []
        for idx, (cfg_path, log_path) in enumerate(zip(tmp_configs, tmp_logs)):
            futures.append(pool.submit(_run_one, idx, method_path, cfg_path, log_path, root))

        pending = set(futures)
        results = {}
        start_ts = time.time()
        progress_interval = max(0, int(args.progress_interval))
        while pending:
            if progress_interval == 0:
                done, pending = wait(pending)
            else:
                done, pending = wait(pending, timeout=progress_interval)
            for fut in done:
                results[fut] = fut.result()
            if pending and progress_interval > 0:
                _print_progress(shards, len(results), tmp_results, tmp_logs, start_ts)

        for shard_idx, rc, elapsed in results.values():
            shard_timings[shard_idx] = elapsed
            if rc != 0:
                failures.append(rc)

    if failures:
        print(f"One or more shards failed. Logs in: {tmp_root}", file=sys.stderr)
        sys.exit(1)

    if res_save_path:
        res_save_path.parent.mkdir(parents=True, exist_ok=True)
        with res_save_path.open("a", encoding="utf-8") as out_f:
            for shard_res in tmp_results:
                if not shard_res.exists():
                    continue
                with shard_res.open("r", encoding="utf-8") as in_f:
                    shutil.copyfileobj(in_f, out_f)

    if shard_timings:
        total_elapsed = sum(shard_timings.values())
        per_shard = [
            {"shard": idx, "elapsed_sec": shard_timings[idx]}
            for idx in sorted(shard_timings.keys())
        ]
        timing_summary = {
            "method": method_path.name,
            "shards": shards,
            "total_elapsed_sec": total_elapsed,
            "avg_elapsed_sec": total_elapsed / shards if shards else 0,
            "min_elapsed_sec": min(shard_timings.values()),
            "max_elapsed_sec": max(shard_timings.values()),
            "per_shard": per_shard,
        }
        print(
            "[timing] method={method} shards={shards} total={total:.3f}s "
            "avg={avg:.3f}s min={min:.3f}s max={max:.3f}s".format(
                method=timing_summary["method"],
                shards=timing_summary["shards"],
                total=timing_summary["total_elapsed_sec"],
                avg=timing_summary["avg_elapsed_sec"],
                min=timing_summary["min_elapsed_sec"],
                max=timing_summary["max_elapsed_sec"],
            ),
            flush=True,
        )

        timing_dir = res_save_path.parent if res_save_path else root
        timing_path = timing_dir / f"{method_path.stem}.timing.json"
        with timing_path.open("w", encoding="utf-8") as f:
            json.dump(timing_summary, f, ensure_ascii=False, indent=2)

    if args.keep_temp:
        print(f"Kept temporary files in: {tmp_root}")
    else:
        shutil.rmtree(tmp_root)


if __name__ == "__main__":
    main()
