"""
status.py — Show recent Braindex run history.

Reads logs/runs.jsonl and prints a summary of the last N runs,
grouped by type (compile, lint).

Usage:
    python3 scripts/status.py
    python3 scripts/status.py --limit 10
    python3 scripts/status.py --type compile
"""
from __future__ import annotations

import argparse
import sys

from braindex import logger as loglib


def fmt_duration(s: float) -> str:
    if s < 60:
        return f"{s:.0f}s"
    return f"{s / 60:.1f}m"


def fmt_warnings(warnings: list[str]) -> str:
    if not warnings:
        return ""
    return f"  {len(warnings)} warning(s):\n" + "\n".join(
        f"    - {w}" for w in warnings[:3]
    ) + ("    ..." if len(warnings) > 3 else "")


def print_run(run: dict) -> None:
    status = run.get("status", "?")
    run_type = run.get("type", "?")
    ts = run.get("timestamp", "")[:16].replace("T", " ")  # "2026-04-08 14:23"
    dur = fmt_duration(run.get("duration_s", 0))
    run_id = run.get("run_id", "")

    status_str = "OK" if status == "success" else "ERR"
    print(f"  [{status_str}] {ts}  {run_type:<10}  {dur:<6}  {run_id}")

    if status == "error":
        print(f"    ERROR: {run.get('error', '')}")

    warnings = run.get("warnings", [])
    if warnings:
        print(fmt_warnings(warnings))

    # Type-specific fields
    if run_type == "compile":
        written  = run.get("files_written", "?")
        skipped  = run.get("files_skipped", 0)
        raw      = run.get("raw_files", "?")
        print(f"    raw={raw}  written={written}  skipped={skipped}")
    elif run_type == "lint":
        files = run.get("wiki_files", "?")
        out   = run.get("output", "")
        print(f"    wiki_files={files}  output={out}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show Braindex run history")
    parser.add_argument("--limit", type=int, default=20,
                        help="Max runs to show (default: 20)")
    parser.add_argument("--type", dest="run_type", default=None,
                        help="Filter by run type: compile | lint")
    args = parser.parse_args()

    runs = loglib.load_runs(run_type=args.run_type, limit=args.limit)

    if not runs:
        print("No runs recorded yet. Run scripts/compile.py or scripts/run_lint.py first.")
        return 0

    filter_note = f"  (type={args.run_type})" if args.run_type else ""
    print(f"\nLast {len(runs)} run(s){filter_note}:\n")
    for run in reversed(runs):
        print_run(run)
    print()

    # Summary line
    errors   = sum(1 for r in runs if r.get("status") == "error")
    warnings = sum(len(r.get("warnings", [])) for r in runs)
    print(f"  {len(runs)} total — {errors} error(s), {warnings} warning(s)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
