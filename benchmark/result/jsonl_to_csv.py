#!/usr/bin/env python3
"""Convert benchmark JSONL results to CSV with Chinese headers.

Supports:
1) single file conversion
2) recursive bulk conversion under a directory
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


DEFAULT_HEADERS = ["id", "题目", "回答", "答案"]
CODE_HEADERS = ["语言", "类型", "考察点", "提问", "模型回答"]


def convert_default(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", encoding="utf-8") as src, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        writer = csv.DictWriter(dst, fieldnames=DEFAULT_HEADERS)
        writer.writeheader()

        for line_no, raw_line in enumerate(src, 1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_no}: {exc}") from exc

            writer.writerow(
                {
                    "id": row.get("id", ""),
                    "题目": row.get("question", ""),
                    "回答": row.get("response", ""),
                    "答案": row.get("answer", ""),
                }
            )


def load_code_lookup(dataset_path: Path) -> dict[str, dict[str, str]]:
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Code dataset file not found: {dataset_path}")
    lookup: dict[str, dict[str, str]] = {}
    with dataset_path.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        required = ["语言", "类型", "考察点", "提问"]
        if reader.fieldnames is None:
            raise ValueError(f"Code dataset is empty: {dataset_path}")
        missing = [name for name in required if name not in reader.fieldnames]
        if missing:
            raise ValueError(
                f"Code dataset missing required columns: {', '.join(missing)}"
            )
        for row in reader:
            prompt = row.get("提问", "")
            if not prompt:
                continue
            lookup[prompt] = {
                "语言": row.get("语言", ""),
                "类型": row.get("类型", ""),
                "考察点": row.get("考察点", ""),
                "提问": prompt,
            }
    return lookup


def convert_code(input_path: Path, output_path: Path, dataset_path: Path) -> None:
    lookup = load_code_lookup(dataset_path)
    with input_path.open("r", encoding="utf-8") as src, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        writer = csv.DictWriter(dst, fieldnames=CODE_HEADERS)
        writer.writeheader()

        for line_no, raw_line in enumerate(src, 1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_no}: {exc}") from exc

            prompt = row.get("question", "")
            meta = lookup.get(prompt, {"语言": "", "类型": "", "考察点": "", "提问": prompt})
            writer.writerow(
                {
                    "语言": meta.get("语言", ""),
                    "类型": meta.get("类型", ""),
                    "考察点": meta.get("考察点", ""),
                    "提问": meta.get("提问", prompt),
                    "模型回答": row.get("response", ""),
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert benchmark_results.jsonl to CSV (id,题目,回答,答案). "
            "Can convert one file or all matching files under a directory."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="Path to input JSONL file (or directory when --all is used)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Path to output CSV file (default: same directory and stem as input)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Recursively convert all benchmark_results.jsonl under input directory",
    )
    parser.add_argument(
        "--format",
        choices=["default", "code"],
        default="default",
        help="Output format. 'code' outputs: 语言,类型,考察点,提问,模型回答",
    )
    parser.add_argument(
        "--code-dataset",
        type=Path,
        default=Path("benchmark/data/code/merged.csv"),
        help="Code dataset CSV used to recover 语言/类型/考察点 columns when --format code.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input or Path(__file__).resolve().parent

    if args.all:
        if not input_path.exists() or not input_path.is_dir():
            raise FileNotFoundError(f"Input directory not found: {input_path}")
        if args.output:
            raise ValueError("--output cannot be used with --all")

        files = sorted(input_path.rglob("benchmark_results.jsonl"))
        if not files:
            print(f"No benchmark_results.jsonl found under: {input_path}")
            return

        for file_path in files:
            output_path = file_path.with_suffix(".csv")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if args.format == "code":
                convert_code(file_path, output_path, args.code_dataset)
            else:
                convert_default(file_path, output_path)
            print(f"Converted: {file_path} -> {output_path}")
        print(f"Done. Converted {len(files)} file(s).")
        return

    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path = args.output or input_path.with_suffix(".csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "code":
        convert_code(input_path, output_path, args.code_dataset)
    else:
        convert_default(input_path, output_path)
    print(f"Converted: {input_path} -> {output_path}")


if __name__ == "__main__":
    main()
