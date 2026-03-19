#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTO_YES=0
DRY_RUN=0

usage() {
  cat <<USAGE
Usage: bash scripts/dev_clean.sh [--yes] [--dry-run]

Clean run-scoped dev artifacts created by web backend workflow.

Options:
  --yes       Skip interactive confirmation.
  --dry-run   Show what would be removed without deleting.
  -h, --help  Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes)
      AUTO_YES=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[dev_clean] unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

TARGETS=(
  "$ROOT_DIR/.dev-runtime"
  "$ROOT_DIR/data/service_runs"
  "$ROOT_DIR/data/attack_results/runs"
  "$ROOT_DIR/benchmark/result/runs"
  "$ROOT_DIR/evaluate/evaluation_report/runs"
)

# Ensure services are stopped first so files are not rewritten during cleanup.
if [[ -x "$ROOT_DIR/scripts/dev_down.sh" ]]; then
  bash "$ROOT_DIR/scripts/dev_down.sh" >/dev/null 2>&1 || true
fi

echo "[dev_clean] target directories:"
for p in "${TARGETS[@]}"; do
  if [[ -d "$p" ]]; then
    size="$(du -sh "$p" 2>/dev/null | awk '{print $1}')"
    files="$(find "$p" -type f 2>/dev/null | wc -l | tr -d ' ')"
    echo "  - $p (size=$size, files=$files)"
  else
    echo "  - $p (missing)"
  fi
done

if [[ "$AUTO_YES" -ne 1 && "$DRY_RUN" -ne 1 ]]; then
  read -r -p "[dev_clean] remove these directories now? [y/N] " ans
  if [[ ! "$ans" =~ ^[Yy]$ ]]; then
    echo "[dev_clean] canceled"
    exit 0
  fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dev_clean] dry-run finished. no files removed."
  exit 0
fi

for p in "${TARGETS[@]}"; do
  if [[ -e "$p" ]]; then
    rm -rf "$p"
    echo "[dev_clean] removed: $p"
  fi
done

# Recreate expected run-scoped roots for next run.
mkdir -p \
  "$ROOT_DIR/data/service_runs" \
  "$ROOT_DIR/data/attack_results/runs" \
  "$ROOT_DIR/benchmark/result/runs" \
  "$ROOT_DIR/evaluate/evaluation_report/runs"

echo "[dev_clean] done"
