#!/usr/bin/env python3
import argparse
import csv
import os
import re
from pathlib import Path


RANGE_SUFFIX_RE = re.compile(r"-\d+-\d+$")
# Force certain prefixes into a single merged file.
GROUP_RULES = [
    (re.compile(r"^第一部分-法律基础知识-法律条文问答-.*$"), "第一部分-法律基础知识-法律条文问答"),
    (re.compile(r"^第一部分-法律基础知识-法学基础知识问答-.*$"), "第一部分-法律基础知识-法学基础知识问答"),
]


def _group_key(path: Path) -> str:
    stem = path.stem
    for pattern, replacement in GROUP_RULES:
        if pattern.match(stem):
            return replacement
    # Group files like “第二部分-法律场景推理问答-1-10.csv” with “...-11-20.csv”
    return RANGE_SUFFIX_RE.sub("", stem)


def _sorted_csv_files(input_dir: Path) -> list[Path]:
    files = [p for p in input_dir.iterdir() if p.suffix.lower() == ".csv" and p.is_file()]
    return sorted(files, key=lambda p: p.name)


def _merge_group(files: list[Path], output_path: Path, drop_column: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header: list[str] = []
    rows: list[dict] = []

    for path in files:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                continue
            for col in reader.fieldnames:
                if col == drop_column:
                    continue
                if col not in header:
                    header.append(col)
            for row in reader:
                if drop_column in row:
                    row.pop(drop_column, None)
                rows.append(row)

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            # Ensure missing columns are present
            writer.writerow({k: row.get(k, "") for k in header})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge MiroThinker-v1.5-30B hallucination CSVs and drop a column."
    )
    parser.add_argument(
        "--input-dir",
        default="data/hallucinations/MiroThinker-v1.5-30B",
        help="Directory containing source CSV files",
    )
    parser.add_argument(
        "--output-dir",
        default="data/hallucinations/MiroThinker-v1.5-30B/merged",
        help="Directory to write merged CSV files",
    )
    parser.add_argument(
        "--drop-column",
        default="回答",
        help="Column name to drop from output",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")

    groups: dict[str, list[Path]] = {}
    for path in _sorted_csv_files(input_dir):
        groups.setdefault(_group_key(path), []).append(path)

    for group, files in groups.items():
        output_path = output_dir / f"{group}.csv"
        _merge_group(files, output_path, args.drop_column)


if __name__ == "__main__":
    main()
