#!/usr/bin/env python3
"""
validate_benchmark_paths.py
----------------------------
Reads a benchmark report and checks that every [[OPEN: path]] reference
points to a file that actually exists on disk.

Usage:
    python3 lint/validate_benchmark_paths.py lint/benchmark-YYYY-MM-DD.md

Exit codes:
    0 — all paths valid
    1 — one or more phantom paths detected (cheating indicator)
"""

import re
import sys
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent

OPEN_PATTERN = re.compile(r"\[\[OPEN:\s*(.+?)\]\]")


def validate(report_path: str) -> int:
    report = Path(report_path)
    if not report.is_file():
        print(f"ERROR: report file not found: {report_path}")
        return 1

    text = report.read_text(encoding="utf-8")
    matches = OPEN_PATTERN.findall(text)

    if not matches:
        print("FAIL — no [[OPEN: ...]] references found. A valid benchmark report must contain traversal logs.")
        return 1

    phantom = []
    for ref in matches:
        target = VAULT_ROOT / ref.strip()
        if not target.is_file():
            phantom.append(ref.strip())

    if phantom:
        print(f"FAIL — {len(phantom)} phantom path(s) detected:")
        for p in phantom:
            print(f"  MISSING: {p}")
        print("\nRun is INVALID — phantom paths are a cheating indicator.")
        return 1

    print(f"PASS — {len(matches)} path(s) checked, all exist.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <benchmark-report.md>")
        sys.exit(1)
    sys.exit(validate(sys.argv[1]))
