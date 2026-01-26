#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _run_one(method_path, cfg_path, log_path, cwd):
    with log_path.open("w", encoding="utf-8") as logf:
        proc = subprocess.run(
            [sys.executable, str(method_path), "--config_path", str(cfg_path)],
            cwd=str(cwd),
            stdout=logf,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return proc.returncode


def main():
    parser = argparse.ArgumentParser(description="Run attack method in parallel by sharding data.")
    parser.add_argument("--method", required=True, help="Path to attack method script (e.g., methods/pair.py).")
    parser.add_argument("--config", required=True, help="Path to YAML config file.")
    parser.add_argument("--shards", type=int, required=True, help="Number of data shards.")
    parser.add_argument("--max-workers", type=int, default=None, help="Max parallel workers (default: shards).")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary shard files.")
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
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = []
        for cfg_path, log_path in zip(tmp_configs, tmp_logs):
            futures.append(
                pool.submit(_run_one, method_path, cfg_path, log_path, root)
            )
        for fut in as_completed(futures):
            rc = fut.result()
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

    if args.keep_temp:
        print(f"Kept temporary files in: {tmp_root}")
    else:
        shutil.rmtree(tmp_root)


if __name__ == "__main__":
    main()
