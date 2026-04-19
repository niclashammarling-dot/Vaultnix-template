"""
vault.py — Vault discovery and data file resolution.

Two independent concerns:
  1. VAULT_ROOT — the user's vault directory (found from cwd by walking upward)
  2. DATA_DIR   — the bundled template data (inside the installed package)
"""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path


# ---------------------------------------------------------------------------
# Package data — bundled template files
# ---------------------------------------------------------------------------

DATA_DIR: Path = Path(str(files("braindex").joinpath("data")))


def data_file(relative: str) -> Path:
    """Return the path to a bundled data file. Raises if missing."""
    p = DATA_DIR / relative
    if not p.exists():
        raise FileNotFoundError(
            f"Bundled data file not found: {relative}\n"
            f"Expected at: {p}\n"
            "This is a packaging error — reinstall Braindex."
        )
    return p


# ---------------------------------------------------------------------------
# Vault discovery — find vault.config.yaml walking upward from cwd
# ---------------------------------------------------------------------------

def find_vault(start: Path | None = None) -> Path | None:
    """
    Walk upward from start (default: cwd) looking for vault.config.yaml.
    Returns the directory containing it, or None if not found.
    """
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "vault.config.yaml").exists():
            return candidate
    return None


def require_vault(start: Path | None = None) -> Path:
    """
    Like find_vault(), but raises with a helpful message if not found.
    All commands that need an initialised vault use this.
    """
    vault = find_vault(start)
    if vault is None:
        raise SystemExit(
            "No vault found. Run 'braindex init' to create one,\n"
            "or navigate into an existing vault directory."
        )
    return vault
