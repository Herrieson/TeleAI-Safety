import argparse
import json
import os
import time
from pathlib import Path

from openai import OpenAI


def clean_endpoint(endpoint: str) -> str:
    return endpoint.strip().strip("`").strip().strip('"').strip("'")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="https://ai-fcs0515ai378871354499.services.ai.azure.com/openai/v1/")
    parser.add_argument("--deployment", default="grok-4-1-fast-reasoning")
    parser.add_argument("--api-key", default="")
    args = parser.parse_args()

    endpoint = clean_endpoint(str(args.endpoint))
    deployment_name = str(args.deployment).strip()
    api_key = str(args.api_key or os.getenv("JAILBREAK_API_KEY") or "").strip()
    out_path = Path(__file__).parent / "api_smoke_test_result.json"

    if not api_key:
        out_path.write_text(json.dumps({"ok": False, "error": "missing JAILBREAK_API_KEY"}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("missing JAILBREAK_API_KEY")
        return

    client = OpenAI(base_url=endpoint, api_key=api_key, timeout=60, max_retries=0)
    started = time.time()
    try:
        completion = client.chat.completions.create(
            model=deployment_name,
            messages=[{"role": "user", "content": "What is the capital of France?"}],
            temperature=0,
        )
        elapsed = round(time.time() - started, 2)
        content = ""
        if completion.choices:
            content = completion.choices[0].message.content or ""
        result = {
            "ok": True,
            "elapsed_sec": elapsed,
            "response": content,
        }
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        elapsed = round(time.time() - started, 2)
        result = {
            "ok": False,
            "elapsed_sec": elapsed,
            "error_type": type(e).__name__,
            "error": str(e),
        }
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
