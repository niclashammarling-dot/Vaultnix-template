"""
schedule.py — Local vault scheduler.

Reads schedule configuration from vault.config.yaml and runs vault
scripts on the configured cron expressions. Replaces remote trigger
infrastructure for users who prefer local execution.

Runs as a persistent background process. Start with:
    python3 scripts/schedule.py

Or add to crontab for system-level scheduling:
    crontab -e
    # Add: @reboot cd /path/to/vault && python3 scripts/schedule.py &

Scheduled jobs (configured in vault.config.yaml):
    compile.mode = scheduled  →  runs scripts/compile.py on compile.trigger schedule
    lint.platform = local-cron →  runs scripts/run_lint.py on lint.schedule

For lint.platform = github-actions, the lint job is handled by GitHub Actions
and is not scheduled here.
"""
from pathlib import Path
import subprocess
import sys
import time
import logging
from datetime import datetime

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install pyyaml")

try:
    from croniter import croniter
except ImportError:
    raise ImportError("croniter required: pip install croniter")

VAULT_ROOT: Path = None  # type: ignore[assignment]  # set in main()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("vault-scheduler")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    from braindex.vault import require_vault
    vault = require_vault()
    config_path = vault / "vault.config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"vault.config.yaml not found at {config_path}."
        )
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Job registry
# ---------------------------------------------------------------------------

def build_jobs(config: dict) -> list[dict]:
    """Return list of {name, cron, script} dicts based on config."""
    jobs = []

    compile_cfg = config.get("compile", {})
    if compile_cfg.get("mode") == "scheduled":
        trigger = str(compile_cfg.get("trigger", "")).strip()
        if trigger and not trigger.startswith("trig_"):
            # Local cron expression (not a remote trigger ID)
            jobs.append({
                "name": "nightly-compile",
                "cron": trigger,
                "cmd": ["braindex", "compile"],
            })
        elif trigger.startswith("trig_"):
            log.warning(
                "compile.trigger looks like a remote trigger ID (%s). "
                "Set a cron expression for local scheduling (e.g. '0 22 * * *').",
                trigger,
            )

    lint_cfg = config.get("lint", {})
    if lint_cfg.get("platform") == "local-cron":
        cron = lint_cfg.get("schedule", "23 8 * * 1")
        jobs.append({
            "name": "weekly-lint",
            "cron": cron,
            "cmd": ["braindex", "lint"],
        })

    benchmark_cfg = config.get("benchmark", {})
    if benchmark_cfg.get("schedule"):
        cron = benchmark_cfg["schedule"]
        jobs.append({
            "name": "weekly-benchmark",
            "cron": cron,
            "cmd": ["braindex", "benchmark"],
        })

    orient_cfg = config.get("orient", {})
    if orient_cfg.get("schedule"):
        cron = orient_cfg["schedule"]
        jobs.append({
            "name": "weekly-orient",
            "cron": cron,
            "cmd": ["braindex", "orient"],
        })

    return jobs


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------

SENTINEL_DIR: Path = None  # type: ignore[assignment]  # set in main()


def next_run(cron_expr: str, after: datetime | None = None) -> datetime:
    base = after or datetime.now()
    return croniter(cron_expr, base).get_next(datetime)


def last_run_time(job_name: str) -> datetime | None:
    """Read the timestamp of the last successful run from a sentinel file."""
    sentinel = SENTINEL_DIR / f"{job_name}.last"
    if not sentinel.exists():
        return None
    try:
        return datetime.fromisoformat(sentinel.read_text().strip())
    except (ValueError, OSError):
        return None


def record_run(job_name: str) -> None:
    SENTINEL_DIR.mkdir(parents=True, exist_ok=True)
    sentinel = SENTINEL_DIR / f"{job_name}.last"
    sentinel.write_text(datetime.now().isoformat())


def is_overdue(job: dict) -> bool:
    """Return True if the job was due since its last recorded run."""
    last = last_run_time(job["name"])
    if last is None:
        return False  # never run — let the normal schedule handle first run
    prev_due = croniter(job["cron"], last).get_next(datetime)
    return datetime.now() >= prev_due


def run_job(job: dict) -> bool:
    """Run a job subprocess. Returns True on success."""
    log.info("Running job: %s", job["name"])
    try:
        result = subprocess.run(
            job["cmd"],
            cwd=str(VAULT_ROOT),
        )
        if result.returncode == 0:
            log.info("Job %s completed successfully.", job["name"])
            record_run(job["name"])
            return True
        else:
            log.error("Job %s exited with code %d.", job["name"], result.returncode)
            return False
    except Exception as e:
        log.error("Job %s raised an exception: %s", job["name"], e)
        return False


def main() -> None:
    global VAULT_ROOT, SENTINEL_DIR
    from braindex.vault import require_vault
    VAULT_ROOT   = require_vault()
    SENTINEL_DIR = VAULT_ROOT / "logs" / "scheduler"

    config = load_config()
    jobs = build_jobs(config)

    if not jobs:
        log.info(
            "No local jobs configured. "
            "Set compile.mode=scheduled with a cron trigger, "
            "or lint.platform=local-cron to schedule jobs here."
        )
        return

    # Startup catch-up: run any job that was due while the scheduler was down.
    # This prevents silent misses when the machine restarts or the process is killed.
    for job in jobs:
        if is_overdue(job):
            log.info(
                "Catch-up: job '%s' was due since last run — running now.",
                job["name"],
            )
            run_job(job)

    # Track next run time per job
    schedule: dict[str, datetime] = {
        job["name"]: next_run(job["cron"]) for job in jobs
    }

    for job in jobs:
        log.info(
            "Scheduled: %s  cron='%s'  next=%s",
            job["name"], job["cron"],
            schedule[job["name"]].strftime("%Y-%m-%d %H:%M"),
        )

    log.info("Scheduler running. Ctrl+C to stop.")

    try:
        while True:
            now = datetime.now()
            for job in jobs:
                if now >= schedule[job["name"]]:
                    run_job(job)  # errors are logged, loop continues
                    schedule[job["name"]] = next_run(job["cron"])
                    log.info(
                        "Next run for %s: %s",
                        job["name"],
                        schedule[job["name"]].strftime("%Y-%m-%d %H:%M"),
                    )
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
