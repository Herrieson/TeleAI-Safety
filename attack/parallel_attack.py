#!/usr/bin/env python3
import argparse
from collections import Counter
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, wait
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


def _record_key(record):
    if isinstance(record, dict):
        for key_name in ("id", "example_id", "sample_id", "uid"):
            if key_name in record and record[key_name] is not None:
                return ("id", str(record[key_name]))
        if "query" in record and record["query"] is not None:
            return ("query", str(record["query"]))
    try:
        return ("raw", json.dumps(record, ensure_ascii=False, sort_keys=True))
    except Exception:
        return ("raw", str(record))


def _load_result_counts(path: Path):
    counts = Counter()
    if not path or not path.exists():
        return counts

    if path.suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                counts[_record_key(rec)] += 1
        return counts

    if path.suffix == ".json":
        try:
            with path.open("r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            return counts
        if isinstance(obj, list):
            for rec in obj:
                counts[_record_key(rec)] += 1
        elif isinstance(obj, dict):
            counts[_record_key(obj)] += 1
        return counts

    return counts


def _filter_pending_records(records, completed_counts: Counter):
    if not completed_counts:
        return records, 0
    rest = completed_counts.copy()
    pending = []
    skipped = 0
    for rec in records:
        key = _record_key(rec)
        if rest.get(key, 0) > 0:
            rest[key] -= 1
            skipped += 1
            continue
        pending.append(rec)
    return pending, skipped


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


def _read_new_jsonl_records(path: Path, offset: int, carry: str):
    if not path.exists():
        return [], offset, carry
    with path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(offset)
        chunk = f.read()
        new_offset = f.tell()

    if not chunk:
        return [], new_offset, carry

    data = carry + chunk
    lines = data.split("\n")
    if data.endswith("\n"):
        complete_lines = lines[:-1]
        new_carry = ""
    else:
        complete_lines = lines[:-1]
        new_carry = lines[-1]

    out = []
    for line in complete_lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out, new_offset, new_carry


def _sync_partial_results(tmp_results, res_save_path, sync_state):
    if not res_save_path or res_save_path.suffix != ".jsonl":
        return 0

    new_records = []
    for idx, shard_res in enumerate(tmp_results):
        recs, new_offset, new_carry = _read_new_jsonl_records(
            shard_res,
            sync_state["offsets"][idx],
            sync_state["carry"][idx],
        )
        sync_state["offsets"][idx] = new_offset
        sync_state["carry"][idx] = new_carry

        for rec in recs:
            key = _record_key(rec)
            cap = sync_state["caps"].get(key)
            seen = sync_state["seen"].get(key, 0)
            if cap is not None and seen >= cap:
                continue
            new_records.append(rec)
            sync_state["seen"][key] += 1

    if not new_records:
        return 0

    res_save_path.parent.mkdir(parents=True, exist_ok=True)
    with res_save_path.open("a", encoding="utf-8") as out_f:
        for rec in new_records:
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out_f.flush()
        os.fsync(out_f.fileno())
    return len(new_records)


def main():
    parser = argparse.ArgumentParser(description="Run attack method in parallel by sharding data.")
    parser.add_argument("--method", required=True, help="Path to attack method script (e.g., methods/pair.py).")
    parser.add_argument("--config", required=True, help="Path to YAML config file.")
    parser.add_argument("--shards", type=int, required=True, help="Number of data shards.")
    parser.add_argument("--max-workers", type=int, default=None, help="Max parallel workers (default: shards).")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary shard files.")
    parser.add_argument("--progress-interval", type=int, default=15, help="Progress report interval in seconds (0 to disable).")
    parser.add_argument("--save-interval", type=int, default=60, help="Incremental result flush interval in seconds (0 to disable).")
    args = parser.parse_args()

    root = Path.cwd()
    method_path = _resolve_path(args.method, root)
    config_path = _resolve_path(args.config, root)

    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    data_key = None
    for key in ("attack_data_path", "data_path", "dataset_path"):
        if key in cfg and cfg[key]:
            data_key = key
            break
    if data_key is None:
        raise KeyError(
            "Missing dataset path in config. Expected one of: "
            "'data_path', 'attack_data_path', 'dataset_path'."
        )

    data_path = _resolve_path(cfg[data_key], root)
    data_offset = int(cfg.get("data_offset", 0))
    res_save_path = cfg.get("res_save_path")
    res_save_path = _resolve_path(res_save_path, root) if res_save_path else None

    records = _load_records(data_path)
    if data_offset:
        records = records[data_offset:]

    existing_result_counts = Counter()
    if res_save_path:
        existing_result_counts = _load_result_counts(res_save_path)
        records, skipped_count = _filter_pending_records(records, existing_result_counts)
        if skipped_count > 0:
            print(f"[resume] skipped {skipped_count} completed records from {res_save_path}", flush=True)
        if not records:
            print("[resume] no pending records to run.", flush=True)
            return

    shards = max(1, int(args.shards))
    split = _split_records(records, shards)
    pending_counts = Counter(_record_key(rec) for rec in records)

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
        for key in ("attack_data_path", "data_path", "dataset_path"):
            if key in shard_cfg:
                shard_cfg[key] = str(shard_data)
        if data_key not in shard_cfg:
            shard_cfg[data_key] = str(shard_data)
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
    sync_state = None
    if res_save_path and res_save_path.suffix == ".jsonl":
        sync_state = {
            "offsets": [0 for _ in tmp_results],
            "carry": ["" for _ in tmp_results],
            "seen": existing_result_counts.copy(),
            "caps": existing_result_counts + pending_counts,
        }

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = []
        for idx, (cfg_path, log_path) in enumerate(zip(tmp_configs, tmp_logs)):
            futures.append(pool.submit(_run_one, idx, method_path, cfg_path, log_path, root))

        pending = set(futures)
        results = {}
        start_ts = time.time()
        progress_interval = max(0, int(args.progress_interval))
        save_interval = max(0, int(args.save_interval))
        last_progress_ts = start_ts
        last_save_ts = start_ts
        while pending:
            wait_timeout = 1
            if progress_interval > 0:
                wait_timeout = min(wait_timeout, progress_interval)
            if save_interval > 0:
                wait_timeout = min(wait_timeout, save_interval)
            done, pending = wait(pending, timeout=wait_timeout)
            for fut in done:
                results[fut] = fut.result()
            now = time.time()
            if pending and progress_interval > 0 and (now - last_progress_ts) >= progress_interval:
                _print_progress(shards, len(results), tmp_results, tmp_logs, start_ts)
                last_progress_ts = now
            if sync_state and save_interval > 0 and (now - last_save_ts) >= save_interval:
                written = _sync_partial_results(tmp_results, res_save_path, sync_state)
                if written > 0:
                    print(f"[save] flushed {written} records to {res_save_path}", flush=True)
                last_save_ts = now

        for shard_idx, rc, elapsed in results.values():
            shard_timings[shard_idx] = elapsed
            if rc != 0:
                failures.append(rc)

    if sync_state:
        written = _sync_partial_results(tmp_results, res_save_path, sync_state)
        if written > 0:
            print(f"[save] final flush {written} records to {res_save_path}", flush=True)

    if failures:
        print(f"One or more shards failed. Logs in: {tmp_root}", file=sys.stderr)
        sys.exit(1)

    if res_save_path:
        if res_save_path.suffix == ".jsonl":
            pass
        else:
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
