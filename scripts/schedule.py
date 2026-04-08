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

VAULT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = VAULT_ROOT / "scripts"

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
    config_path = VAULT_ROOT / "vault.config.yaml"
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
                "script": SCRIPTS_DIR / "compile.py",
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
            "script": SCRIPTS_DIR / "run_lint.py",
        })

    return jobs


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------

def next_run(cron_expr: str) -> datetime:
    return croniter(cron_expr, datetime.now()).get_next(datetime)


def run_job(job: dict) -> None:
    log.info("Running job: %s", job["name"])
    result = subprocess.run(
        [sys.executable, str(job["script"])],
        cwd=str(VAULT_ROOT),
    )
    if result.returncode == 0:
        log.info("Job %s completed successfully.", job["name"])
    else:
        log.error("Job %s exited with code %d.", job["name"], result.returncode)


def main() -> None:
    config = load_config()
    jobs = build_jobs(config)

    if not jobs:
        log.info(
            "No local jobs configured. "
            "Set compile.mode=scheduled with a cron trigger, "
            "or lint.platform=local-cron to schedule jobs here."
        )
        return

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
                    run_job(job)
                    schedule[job["name"]] = next_run(job["cron"])
                    log.info(
                        "Next run for %s: %s",
                        job["name"],
                        schedule[job["name"]].strftime("%Y-%m-%d %H:%M"),
                    )
            time.sleep(30)  # check every 30 seconds
    except KeyboardInterrupt:
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
