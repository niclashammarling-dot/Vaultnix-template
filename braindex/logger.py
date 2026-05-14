"""
logger.py — Structured run logging for Braindex scripts.

Writes one JSON line per run to logs/runs.jsonl.
All scripts import this module to record their runs.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _logs_dir() -> Path:
    from braindex.vault import require_vault
    return require_vault() / "logs"


class RunLogger:
    """
    Context manager that records a script run to logs/runs.jsonl.

    Usage:
        with RunLogger("compile") as log:
            log.set("files_written", 3)
            log.warn("selective context mode activated")
            # on exit: status="success" unless an exception was raised
    """

    def __init__(self, run_type: str) -> None:
        self.run_type  = run_type
        self.run_id    = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + \
                         "-" + uuid.uuid4().hex[:4]
        self.started   = time.monotonic()
        self._data: dict[str, Any] = {}
        self._warnings: list[str]  = []

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def warn(self, message: str) -> None:
        print(f"WARNING: {message}")
        self._warnings.append(message)

    def __enter__(self) -> "RunLogger":
        self._logs = _logs_dir()
        self._logs.mkdir(exist_ok=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        duration = round(time.monotonic() - self.started, 1)
        status   = "error" if exc_type else "success"
        error    = f"{exc_type.__name__}: {exc_val}" if exc_type else None

        record = {
            "run_id":    self.run_id,
            "type":      self.run_type,
            "status":    status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_s": duration,
            "warnings":  self._warnings,
            **self._data,
        }
        if error:
            record["error"] = error

        log_file = self._logs / "runs.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        if exc_type:
            print(f"\nRun {self.run_id} failed after {duration}s: {error}", file=sys.stderr)
        else:
            print(f"\nRun {self.run_id} completed in {duration}s.", file=sys.stderr)

        return False  # do not suppress exceptions


def load_runs(run_type: str | None = None, limit: int = 20) -> list[dict]:
    """Return the most recent runs from logs/runs.jsonl."""
    log_file = _logs_dir() / "runs.jsonl"
    if not log_file.exists():
        return []
    runs = []
    for line in log_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            if run_type is None or r.get("type") == run_type:
                runs.append(r)
        except json.JSONDecodeError:
            continue
    return runs[-limit:]
