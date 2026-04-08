#!/usr/bin/env python3
"""
audit_benchmark_scores.py
--------------------------
Reads a benchmark report, extracts scores, counts vault changes since the
previous benchmark run, and flags suspicious score improvements.

Usage:
    python3 lint/audit_benchmark_scores.py lint/benchmark-YYYY-MM-DD.md

What it does:
    1. Parses the report for date, mode, total, per-query, and per-dimension scores
    2. Loads lint/benchmark-trend.json for historical context
    3. Runs git log to count new/modified wiki/ articles since last benchmark
    4. Applies flagging rules (see AUDIT RULES below)
    5. Prints a structured audit result
    6. Appends the current run to benchmark-trend.json ONLY if clean or first run
       (flagged and git-failed runs are not persisted — they must not become the baseline)

AUDIT RULES:
    FLAG_A  Delta > 20 points with 0 new wiki articles
    FLAG_B  Any single query improves by >= 8 points with 0 new wiki articles
    FLAG_D  Mode unchanged, delta > 30 points, fewer than 3 new wiki articles
    NOTE_M  Mode changed (abbreviated↔full) — score scale not comparable; run
            persists to trend but delta is not evaluated

Exit codes:
    0 — clean run
    1 — one or more FLAG conditions triggered
    2 — parse error
"""

import json
import re
import subprocess
import sys

from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
TREND_FILE = VAULT_ROOT / "lint" / "benchmark-trend.json"

QUERIES = ["N1", "N2", "S1", "S2", "G1", "G2", "F1", "F2", "A1", "A2"]
DIMENSIONS = ["Traversal", "Synthesis", "Gap Honesty", "Surprise", "Consistency"]

# Flagging thresholds
DELTA_ZERO_CHANGE_THRESHOLD = 20    # FLAG_A
QUERY_JUMP_THRESHOLD = 8            # FLAG_B
DELTA_FEW_CHANGE_THRESHOLD = 30     # FLAG_D
FEW_CHANGE_ARTICLE_COUNT = 3        # FLAG_D


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_report(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    # Date from filename: benchmark-YYYY-MM-DD.md
    date_match = re.search(r"benchmark-(\d{4}-\d{2}-\d{2})", path.name)
    if not date_match:
        raise ValueError(f"Cannot extract date from filename: {path.name}")
    run_date = date_match.group(1)

    # Mode
    mode_match = re.search(r"Mode:\s*(full|abbreviated)", text, re.IGNORECASE)
    if not mode_match:
        raise ValueError("Cannot find Mode line in report. Add 'Mode: full' or 'Mode: abbreviated' to the report header.")
    mode = mode_match.group(1).lower()

    # Total score from "**Total: NNN/250**" or "**Total: NNN/400**"
    total_match = re.search(r"\*\*Total:\s*(\d+)/\d+\*\*", text)
    if not total_match:
        raise ValueError("Cannot find Total score in report.")
    total = int(total_match.group(1))

    # Per-query scores from the scores table
    # Row format (full):       | N1 | td | sq | gh | su | cs | total/25 | ± |
    # Row format (abbreviated): | N1 | td | sq | gh | su | total/20 | ± |
    # Use the explicit total column (authoritative). Accept 4 or 5 dimension
    # columns and any denominator (/20, /25) to handle both modes.
    query_scores = {}
    for q in QUERIES:
        pattern = rf"\|\s*{q}\s*\|(?:[^|]+\|){{4,5}}\s*(\d+)/\d+"
        m = re.search(pattern, text)
        query_scores[q] = int(m.group(1)) if m else None

    # Per-dimension totals from the "By Dimension" table
    dimension_scores = {}
    for dim in DIMENSIONS:
        pattern = rf"\|\s*{re.escape(dim)}\s*\|\s*(\d+)/\d+"
        m = re.search(pattern, text)
        dimension_scores[dim] = int(m.group(1)) if m else None

    return {
        "date": run_date,
        "mode": mode,
        "total": total,
        "by_query": query_scores,
        "by_dimension": dimension_scores,
    }


# ---------------------------------------------------------------------------
# Vault change count
# ---------------------------------------------------------------------------

def count_vault_changes(since_date: str) -> int:
    """Count distinct wiki/ files added or modified since since_date."""
    try:
        result = subprocess.run(
            [
                "git", "-C", str(VAULT_ROOT),
                "log", f"--since={since_date}",
                "--name-only", "--pretty=format:",
                "--", "wiki/"
            ],
            capture_output=True, text=True, check=True
        )
        files = {f.strip() for f in result.stdout.splitlines() if f.strip()}
        return len(files)
    except subprocess.CalledProcessError as e:
        print(f"WARNING: git log failed: {e.stderr.strip()}")
        return -1  # unknown


# ---------------------------------------------------------------------------
# Audit logic
# ---------------------------------------------------------------------------

def audit(current: dict, previous: dict | None, vault_changes: int) -> list[str]:
    flags = []

    if previous is None:
        flags.append("INFO: first benchmark run — no delta available.")
        return flags

    delta = current["total"] - previous["total"]
    prev_mode = previous.get("mode", "unknown")
    curr_mode = current.get("mode", "unknown")

    # NOTE_M: mode change affects score scale
    if prev_mode == "abbreviated" and curr_mode == "full":
        flags.append(
            "NOTE_M: mode changed abbreviated→full. Score scale includes CS "
            "dimension — delta is not directly comparable to previous run."
        )
        return flags  # mode change makes other flags unreliable

    if prev_mode == "full" and curr_mode == "abbreviated":
        flags.append(
            "NOTE_M: mode changed full→abbreviated. CS omitted this run — "
            "delta is not directly comparable."
        )
        return flags

    # Bail out if git failed — don't grant a clean pass on unknown data
    if vault_changes == -1:
        flags.append(
            "WARNING: git log failed — vault change count unknown. "
            "FLAG_A and FLAG_D cannot be evaluated. Investigate git before trusting this run."
        )
        return flags

    # FLAG_A: big overall jump with no vault changes
    if delta > DELTA_ZERO_CHANGE_THRESHOLD and vault_changes == 0:
        flags.append(
            f"FLAG_A: total score +{delta} but 0 new/modified wiki articles "
            f"since last run ({previous['date']}). Suspicious."
        )

    # FLAG_B: single query jump with no vault changes
    if vault_changes == 0:
        for q in QUERIES:
            curr_q = current["by_query"].get(q)
            prev_q = previous["by_query"].get(q)
            if curr_q is not None and prev_q is not None:
                q_delta = curr_q - prev_q
                if q_delta >= QUERY_JUMP_THRESHOLD:
                    flags.append(
                        f"FLAG_B: {q} score +{q_delta} with 0 vault changes. "
                        f"Suspicious single-query jump."
                    )

    # FLAG_D: large jump with very few vault changes
    if (delta > DELTA_FEW_CHANGE_THRESHOLD
            and 0 < vault_changes < FEW_CHANGE_ARTICLE_COUNT):
        flags.append(
            f"FLAG_D: total score +{delta} but only {vault_changes} "
            f"wiki article(s) changed — improvement rate unusually high."
        )

    if not flags:
        sign = "+" if delta >= 0 else ""
        flags.append(
            f"CLEAN: delta {sign}{delta}, vault changes {vault_changes} — "
            f"no suspicious patterns detected."
        )

    return flags


# ---------------------------------------------------------------------------
# Trend persistence
# ---------------------------------------------------------------------------

def load_trend() -> list:
    if not TREND_FILE.exists():
        return []
    try:
        return json.loads(TREND_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"benchmark-trend.json is corrupted: {e}") from e


def save_trend(trend: list, entry: dict) -> None:
    # Replace if same date already exists, otherwise append
    trend = [r for r in trend if r["date"] != entry["date"]]
    trend.append(entry)
    trend.sort(key=lambda r: r["date"])
    TREND_FILE.write_text(json.dumps(trend, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <benchmark-report.md>")
        return 2

    report_path = Path(sys.argv[1])
    if not report_path.exists():
        print(f"ERROR: file not found: {report_path}")
        return 2

    try:
        current = parse_report(report_path)
    except ValueError as e:
        print(f"PARSE ERROR: {e}")
        return 2

    try:
        trend = load_trend()
    except ValueError as e:
        print(f"PARSE ERROR: {e}")
        return 2
    previous = trend[-1] if trend else None

    since_date = previous["date"] if previous else current["date"]
    vault_changes = count_vault_changes(since_date)

    flags = audit(current, previous, vault_changes)

    # Output
    print(f"\nBENCHMARK SCORE AUDIT — {current['date']}")
    print(f"  Mode:          {current['mode']}")
    print(f"  Total:         {current['total']}")
    if previous:
        delta = current["total"] - previous["total"]
        sign = "+" if delta >= 0 else ""
        print(f"  vs last run:   {sign}{delta} (last: {previous['total']} on {previous['date']})")
    vault_str = str(vault_changes) if vault_changes >= 0 else "unknown (git error)"
    print(f"  Vault changes: {vault_str} wiki file(s) since {since_date}\n")

    for f in flags:
        print(f"  {f}")

    has_flag = any(f.startswith("FLAG") for f in flags)
    has_warning = any(f.startswith("WARNING") for f in flags)

    # Only persist clean or first-run results. A flagged or git-failed run must
    # not update the baseline — that is the core loophole it would enable.
    if not has_flag and not has_warning:
        entry = {**current, "vault_changes": vault_changes}
        save_trend(trend, entry)
        print(f"\n  Trend updated: {TREND_FILE}")
    else:
        print(f"\n  Trend NOT updated — run must be clean before it becomes the baseline.")

    if has_flag or has_warning:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
