"""
cli.py — Braindex command-line interface.

Usage:
    braindex init        Run the setup wizard and initialise a vault
    braindex scan        Scan a folder and generate a vault bootstrap prompt
    braindex setup       Re-run vault initialisation (after editing vault.config.yaml)
    braindex compile     Compile raw/ files into wiki/ articles
    braindex orient      Surface highest-value stub gaps (what to add next)
    braindex query <q>   Ask the vault a question via graph-walk
    braindex benchmark   Run the weekly vault quality benchmark
    braindex lint        Run vault health check (mechanical + LLM)
    braindex validate    Run mechanical hook validation on wiki/
    braindex status      Show recent run history
    braindex schedule    Start the local cron scheduler
    braindex version     Print version and exit
"""
from __future__ import annotations

import sys


def _help() -> None:
    print(__doc__)


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        _help()
        return

    command = args[0]
    rest = args[1:]

    if command == "version":
        from braindex import __version__
        print(f"Braindex {__version__}")
        return

    if command == "init":
        from braindex.wizard import main as _run
        sys.argv = ["braindex init"] + rest
        _run()

    elif command == "scan":
        from braindex.scanner import main as _run
        sys.argv = ["braindex scan"] + rest
        _run()

    elif command == "orient":
        from braindex.orient import main as _run
        sys.argv = ["braindex orient"] + rest
        sys.exit(_run())

    elif command == "query":
        from braindex.query import main as _run
        sys.argv = ["braindex query"] + rest
        sys.exit(_run())

    elif command == "benchmark":
        from braindex.benchmark import main as _run
        sys.argv = ["braindex benchmark"] + rest
        sys.exit(_run())

    elif command == "setup":
        from braindex.setup import main as _run
        sys.argv = ["braindex setup"] + rest
        _run()

    elif command == "compile":
        from braindex.compile import main as _run
        sys.argv = ["braindex compile"] + rest
        sys.exit(_run())

    elif command == "lint":
        from braindex.run_lint import main as _run
        sys.argv = ["braindex lint"] + rest
        _run()

    elif command == "validate":
        from braindex.validate import main as _run
        sys.argv = ["braindex validate"] + rest
        sys.exit(_run())

    elif command == "status":
        from braindex.status import main as _run
        sys.argv = ["braindex status"] + rest
        sys.exit(_run())

    elif command == "schedule":
        from braindex.schedule import main as _run
        sys.argv = ["braindex schedule"] + rest
        _run()

    else:
        print(f"Unknown command: {command}")
        _help()
        sys.exit(1)


if __name__ == "__main__":
    main()
