#!/usr/bin/env python3
"""Merge code-eval CSV shards by language and blank out model responses."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


EXPECTED_HEADERS = ["语言", "类型", "考察点", "提问", "模型回答"]


def list_language_dirs(input_dir: Path) -> list[Path]:
    return sorted([p for p in input_dir.iterdir() if p.is_dir()], key=lambda p: p.name.lower())


def list_csv_files(language_dir: Path) -> list[Path]:
    return sorted([p for p in language_dir.iterdir() if p.is_file() and p.suffix.lower() == ".csv"])


def merge_language(language_dir: Path, output_dir: Path) -> tuple[int, Path]:
    csv_files = list_csv_files(language_dir)
    if not csv_files:
        return 0, output_dir / f"{language_dir.name}.csv"

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{language_dir.name}.csv"
    row_count = 0

    with output_path.open("w", encoding="utf-8", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=EXPECTED_HEADERS)
        writer.writeheader()

        for file_path in csv_files:
            with file_path.open("r", encoding="utf-8-sig", newline="") as in_f:
                reader = csv.DictReader(in_f)
                if reader.fieldnames is None:
                    continue
                missing = [h for h in EXPECTED_HEADERS if h not in reader.fieldnames]
                if missing:
                    raise ValueError(f"{file_path} missing required columns: {', '.join(missing)}")

                for row in reader:
                    writer.writerow(
                        {
                            "语言": row.get("语言", "").strip(),
                            "类型": row.get("类型", "").strip(),
                            "考察点": row.get("考察点", "").strip(),
                            "提问": row.get("提问", ""),
                            "模型回答": "",
                        }
                    )
                    row_count += 1

    return row_count, output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge each language folder's CSV files into one CSV and clear the "
            "'模型回答' column."
        )
    )
    parser.add_argument(
        "--input-dir",
        default="data/code/代码生成检测结果_deepseek-v3.2",
        help="Root directory containing language subfolders.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/code/代码生成检测结果_deepseek-v3.2/merged",
        help="Directory to write merged per-language CSV files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {input_dir}")

    language_dirs = list_language_dirs(input_dir)
    if not language_dirs:
        raise SystemExit(f"No language subdirectories found under: {input_dir}")

    total_rows = 0
    merged_files = 0
    for language_dir in language_dirs:
        rows, output_path = merge_language(language_dir, output_dir)
        if rows == 0:
            continue
        merged_files += 1
        total_rows += rows
        print(f"Merged {rows:4d} rows -> {output_path}")

    print(f"Done. files={merged_files}, rows={total_rows}")


if __name__ == "__main__":
    main()
