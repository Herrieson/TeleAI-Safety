import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from mechanism_modules.common import batch_judge_queries_is_jailbreak, read_jsonl


ATTACK_METHOD_FILES: Dict[str, str] = {
    "jailbroken": "jailbroken.jsonl",
    "deep_inception": "deep_inception.jsonl",
    "rene": "rene.jsonl",
    "cipher": "cipher.jsonl",
    "pair": "pair.jsonl",
    "artprompt": "artprompt.jsonl",
    "dra": "dra.jsonl",
    "morpheus_gapfill": "morpheus_gapfill.jsonl",
}


def get_query_text(row: dict) -> str:
    final_query = row.get("final_query")
    if isinstance(final_query, str) and final_query.strip():
        return final_query
    query = row.get("query")
    return str(query) if isinstance(query, str) else ""


def get_response_text(row: dict) -> str:
    response = row.get("response")
    return str(response) if isinstance(response, str) else ""


def make_bar(done: int, total: int, width: int = 28) -> str:
    if total <= 0:
        return "-" * width
    ratio = max(0.0, min(1.0, done / total))
    filled = int(ratio * width)
    return "#" * filled + "-" * (width - filled)


def collect_rows(path: Path) -> List[dict]:
    return list(read_jsonl(path))


def run_model(
    root: Path,
    model_id: str,
    endpoint: str,
    deployment: str,
    api_key: str,
    max_workers: int,
    timeout_sec: Optional[float],
    chunk_size: int,
    methods: List[str],
    limit_per_method: int,
) -> None:
    attack_dir = root / "attack" / model_id
    output_dir = root / "mechanism_outputs" / "jailbreak_api" / model_id
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{model_id}] start run -> {output_dir}", flush=True)
    summary: Dict[str, dict] = {"model_id": model_id, "methods": {}, "total_queries": 0, "total_jailbreak": 0}
    method_names = methods
    all_methods = len(method_names)
    for method_index, method in enumerate(method_names, start=1):
        filename = ATTACK_METHOD_FILES[method]
        data_path = attack_dir / filename
        rows = collect_rows(data_path)
        queries = []
        for idx, row in enumerate(rows):
            qid = str(row.get("id") or f"{method}-{idx + 1}")
            queries.append({"id": qid, "query": get_query_text(row), "response": get_response_text(row)})
        if limit_per_method > 0:
            queries = queries[:limit_per_method]
        total = len(queries)
        print(f"[{model_id}] start method {method_index}/{all_methods} {method} total={total}", flush=True)
        method_output_path = output_dir / f"{method}.jsonl"
        method_results: List[dict] = []
        start_time = time.time()
        done = 0
        for start in range(0, total, chunk_size):
            chunk = queries[start : start + chunk_size]
            chunk_end = min(total, start + len(chunk))
            print(f"[{model_id}] request {method} chunk {start + 1}-{chunk_end}/{total}", flush=True)
            chunk_results = batch_judge_queries_is_jailbreak(
                queries=chunk,
                endpoint=endpoint,
                api_key=api_key,
                deployment=deployment,
                max_workers=max_workers,
                timeout_sec=timeout_sec,
            )
            method_results.extend(chunk_results)
            done = min(total, done + len(chunk))
            bar = make_bar(done, total)
            pct = 0.0 if total == 0 else (done / total) * 100.0
            print(
                f"[{model_id}] method {method_index}/{all_methods} {method:<16} {done:>5}/{total:<5} {pct:6.2f}% {bar}",
                flush=True,
            )
        jailbreak_count = sum(1 for x in method_results if x.get("is_jailbreak") is True)
        valid_count = sum(1 for x in method_results if isinstance(x.get("is_jailbreak"), bool))
        method_asr = None if valid_count == 0 else jailbreak_count / valid_count
        elapsed = round(time.time() - start_time, 2)
        with method_output_path.open("w", encoding="utf-8") as f:
            for item in method_results:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        summary["methods"][method] = {
            "input_file": str(data_path),
            "output_file": str(method_output_path),
            "total": total,
            "valid": valid_count,
            "jailbreak_count": jailbreak_count,
            "jailbreak_rate": method_asr,
            "elapsed_sec": elapsed,
        }
        summary["total_queries"] += total
        summary["total_jailbreak"] += jailbreak_count
        print(
            f"[{model_id}] done {method:<16} valid={valid_count} jailbreak={jailbreak_count} rate={method_asr} elapsed={elapsed}s",
            flush=True,
        )
    valid_total = sum(v["valid"] for v in summary["methods"].values())
    summary["valid_total"] = valid_total
    summary["overall_jailbreak_rate"] = None if valid_total == 0 else summary["total_jailbreak"] / valid_total
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{model_id}] summary saved -> {summary_path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).parent))
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--endpoint", default="https://ai-fcs0515ai378871354499.services.ai.azure.com/openai/v1/")
    parser.add_argument("--deployment", default="grok-4-1-fast-reasoning")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--max-workers", type=int, default=5)
    parser.add_argument("--timeout-sec", type=float, default=0.0)
    parser.add_argument("--chunk-size", type=int, default=100)
    parser.add_argument("--methods", default="")
    parser.add_argument("--limit-per-method", type=int, default=0)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    api_key = str(args.api_key or os.getenv("JAILBREAK_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("missing api key")
    selected_methods = [x.strip() for x in str(args.methods).split(",") if x.strip()]
    if not selected_methods:
        selected_methods = list(ATTACK_METHOD_FILES.keys())
    else:
        selected_methods = [m for m in selected_methods if m in ATTACK_METHOD_FILES]
    if not selected_methods:
        raise RuntimeError("no valid methods selected")
    run_model(
        root=root,
        model_id=args.model_id,
        endpoint=args.endpoint,
        deployment=args.deployment,
        api_key=api_key,
        max_workers=max(1, int(args.max_workers)),
        timeout_sec=None if float(args.timeout_sec) <= 0 else float(args.timeout_sec),
        chunk_size=max(1, int(args.chunk_size)),
        methods=selected_methods,
        limit_per_method=max(0, int(args.limit_per_method)),
    )


if __name__ == "__main__":
    main()
