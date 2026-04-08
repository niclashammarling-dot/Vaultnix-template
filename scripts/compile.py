"""
compile.py — Vault nightly compilation driver.

Reads the COMPILATION_PROMPT, gathers raw/ inputs and current wiki/ state,
calls the configured LLM, and writes the response to
raw/general/nightly-compile-YYYY-MM-DD.md for agent review next session.

This is the local replacement for a remote trigger. The output lands in
raw/ (gitignored, ephemeral) so the next compile session can process it.

Usage:
    python3 scripts/compile.py [--dry-run]

Options:
    --dry-run   Print what would be sent to the LLM without calling it.
"""
from datetime import date
from pathlib import Path
import argparse
import os
import sys

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install pyyaml")

import llm as llmlib

VAULT_ROOT  = Path(__file__).parent.parent
WIKI_DIR    = VAULT_ROOT / "wiki"
RAW_DIR     = VAULT_ROOT / "raw"
PROMPT_FILE = VAULT_ROOT / "Vault" / "COMPILATION_PROMPT.md"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    config_path = VAULT_ROOT / "vault.config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"vault.config.yaml not found at {config_path}. "
            "Run the setup wizard or create the config manually."
        )
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env_file(config: dict) -> None:
    env_file = config.get("env_file", "").strip()
    if not env_file:
        return
    env_path = VAULT_ROOT / env_file
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


# ---------------------------------------------------------------------------
# Vault content gathering
# ---------------------------------------------------------------------------

def gather_raw() -> str:
    """Collect all unprocessed raw/ files."""
    parts = []
    for path in sorted(RAW_DIR.rglob("*.md")):
        rel = path.relative_to(VAULT_ROOT)
        parts.append(f"=== RAW: {rel} ===\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts) if parts else "(no raw files)"


def gather_wiki() -> str:
    """Collect current wiki/ state for spreading activation context."""
    parts = []
    for path in sorted(WIKI_DIR.rglob("*.md")):
        rel = path.relative_to(VAULT_ROOT)
        parts.append(f"=== WIKI: {rel} ===\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts) if parts else "(no wiki articles yet)"


def build_prompt(compilation_prompt: str, raw_content: str, wiki_content: str) -> str:
    return f"""{compilation_prompt}

---

## CURRENT VAULT STATE (for spreading activation context)

{wiki_content}

---

## NEW RAW INPUTS (compile these)

{raw_content}
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Vault nightly compilation driver")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print prompt size without calling the LLM")
    args = parser.parse_args()

    config = load_config()
    load_env_file(config)

    if not PROMPT_FILE.exists():
        print(f"ERROR: COMPILATION_PROMPT.md not found at {PROMPT_FILE}")
        sys.exit(1)

    compilation_prompt = PROMPT_FILE.read_text(encoding="utf-8")
    raw_content  = gather_raw()
    wiki_content = gather_wiki()
    full_prompt  = build_prompt(compilation_prompt, raw_content, wiki_content)

    print(f"Prompt size: {len(full_prompt):,} chars")
    print(f"Raw files:   {raw_content.count('=== RAW:'):,}")
    print(f"Wiki files:  {wiki_content.count('=== WIKI:'):,}")

    if args.dry_run:
        print("Dry run — LLM not called.")
        return

    lc = llmlib.resolve(config)
    response = llmlib.call(lc, full_prompt, max_tokens=8192)

    # Write output to raw/general/ for agent review next session
    output_dir = RAW_DIR / "general"
    output_dir.mkdir(parents=True, exist_ok=True)
    today  = date.today().isoformat()
    output = output_dir / f"nightly-compile-{today}.md"
    output.write_text(response, encoding="utf-8")
    print(f"Written: {output}")
    print("Review this file at the start of your next session or run compile.")


if __name__ == "__main__":
    main()
