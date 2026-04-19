"""
compile.py — Vault compilation driver.

Reads raw/ inputs, calls the configured LLM with the COMPILATION_PROMPT,
parses the response into discrete wiki articles, validates each one, and
commits to a branch for review (or auto-merges if all checks pass).

Usage:
    python3 scripts/compile.py [--dry-run] [--no-git]

Options:
    --dry-run   Print what would be sent/written without calling the LLM.
    --no-git    Skip branch creation and commit (write files directly to wiki/).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install pyyaml")

from braindex import llm as llmlib
from braindex import logger as loglib
from braindex import validate as validatelib
from braindex.vault import require_vault

VAULT_ROOT: Path = None  # type: ignore[assignment]  # set in main()
WIKI_DIR:   Path = None  # type: ignore[assignment]
RAW_DIR:    Path = None  # type: ignore[assignment]
LOGS_DIR:   Path = None  # type: ignore[assignment]
PROMPT_FILE: Path = None  # type: ignore[assignment]
LOCK_FILE:  Path = None  # type: ignore[assignment]

# Delimiter format the LLM uses to wrap file output
FILE_START_RE = re.compile(r'^<<<\s*FILE:\s*(.+?)\s*>>>', re.MULTILINE)
FILE_END      = "<<< END FILE >>>"

# Injected at the end of every API prompt so the LLM knows the output format
API_OUTPUT_FORMAT = """\
---

## API OUTPUT FORMAT (required — this run is automated)

Wrap every file you create or update in delimiters. No prose outside delimiters.

<<< FILE: wiki/domain/article-slug.md >>>
[full file content]
<<< END FILE >>>

Rules:
- One `<<< FILE: ... >>>` block per file
- Path relative to vault root (e.g. `wiki/apex/engine-design.md`)
- Filename lowercase-hyphenated, `.md` extension
- No explanatory text outside the FILE blocks
- If nothing needs writing, output exactly: `<<< NO OUTPUT >>>`
"""

# Selective context: domains always included regardless of raw input
STRUCTURAL_DIRS = {"_mocs", "_concepts", "_index"}


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
# Lock
# ---------------------------------------------------------------------------

def acquire_lock() -> bool:
    """Return True if lock was acquired. False if already running."""
    LOGS_DIR.mkdir(exist_ok=True)
    if LOCK_FILE.exists():
        age = time.time() - LOCK_FILE.stat().st_mtime
        if age < 3600:  # stale after 1 hour
            return False
        LOCK_FILE.unlink()  # remove stale lock
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Content gathering — selective context
# ---------------------------------------------------------------------------

def compiled_marker(raw_path: Path) -> Path:
    """Sidecar file that marks a raw file as successfully compiled."""
    return raw_path.with_suffix(".compiled")


def raw_files(force: bool = False) -> list[Path]:
    """
    Return uncompiled .md files in raw/ sorted by modification time (oldest first).
    A file is considered compiled if a .compiled sidecar exists AND is newer than
    the raw file (re-processes if the raw file was edited after last compile).
    Pass force=True to return all files regardless of compiled state.
    """
    all_files = sorted(RAW_DIR.rglob("*.md"), key=lambda p: p.stat().st_mtime)
    if force:
        return all_files
    pending = []
    for p in all_files:
        marker = compiled_marker(p)
        if marker.exists() and marker.stat().st_mtime >= p.stat().st_mtime:
            continue  # already compiled and not modified since
        pending.append(p)
    return pending


def mark_compiled(raw_path: Path) -> None:
    """Write a .compiled sidecar to record successful compilation."""
    compiled_marker(raw_path).write_text("ok")


def selective_wiki_context(raw_path: Path) -> str:
    """
    Return wiki content relevant to a given raw file.
    Always includes: _mocs/, _concepts/, _index/
    Also includes: articles in the same domain as the raw file.
    """
    domain = raw_path.parent.name  # e.g. "apex" from raw/apex/article.md
    parts = []

    for wiki_file in sorted(WIKI_DIR.rglob("*.md")):
        # Always include structural directories (check ALL ancestors, not just parent,
        # to handle subdirectories like wiki/inspiration/design/)
        rel_parts = wiki_file.relative_to(WIKI_DIR).parts
        in_structural = bool(STRUCTURAL_DIRS.intersection(rel_parts))

        # Domain match: first path component under wiki/ must equal domain
        # (rel_parts[0] = "apex", "knowledge-work", "inspiration", etc.)
        in_domain = len(rel_parts) >= 1 and rel_parts[0] == domain

        include = in_structural or in_domain

        if include:
            rel = wiki_file.relative_to(VAULT_ROOT)
            parts.append(
                f"=== WIKI: {rel} ===\n"
                f"{wiki_file.read_text(encoding='utf-8')}"
            )

    return "\n\n".join(parts) if parts else "(no existing wiki articles)"


def full_wiki_context() -> str:
    parts = []
    for wiki_file in sorted(WIKI_DIR.rglob("*.md")):
        rel = wiki_file.relative_to(VAULT_ROOT)
        parts.append(
            f"=== WIKI: {rel} ===\n"
            f"{wiki_file.read_text(encoding='utf-8')}"
        )
    return "\n\n".join(parts) if parts else "(no existing wiki articles)"


def build_prompt(compilation_prompt: str, raw_path: Path, wiki_context: str) -> str:
    raw_content = (
        f"=== RAW: {raw_path.relative_to(VAULT_ROOT)} ===\n"
        f"{raw_path.read_text(encoding='utf-8')}"
    )
    return f"""{compilation_prompt}

---

## CURRENT VAULT STATE (for spreading activation context)

{wiki_context}

---

## NEW RAW INPUT (compile this file)

{raw_content}

{API_OUTPUT_FORMAT}"""


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------

def parse_file_blocks(response: str) -> list[tuple[str, str]]:
    """
    Parse LLM response into (path, content) pairs.
    Expected format:
        <<< FILE: wiki/domain/slug.md >>>
        [content]
        <<< END FILE >>>
    """
    results = []
    matches = list(FILE_START_RE.finditer(response))

    for i, match in enumerate(matches):
        file_path = match.group(1).strip()
        content_start = match.end()
        content_end = response.find(FILE_END, content_start)

        if content_end == -1:
            # No END marker — take until next FILE marker or end of response
            content_end = matches[i + 1].start() if i + 1 < len(matches) else len(response)

        content = response[content_start:content_end].strip()
        if content:
            results.append((file_path, content))

    return results


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------

def git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    # Use as_posix() so git accepts the path on all platforms (incl. Windows)
    return subprocess.run(
        ["git", "-C", VAULT_ROOT.as_posix()] + args,
        capture_output=True, text=True, check=check,
    )


def git_available() -> bool:
    result = git(["status"], check=False)
    return result.returncode == 0


def _git_check(result: subprocess.CompletedProcess, context: str) -> None:
    """Print stderr from a failed git operation so failures are never silent."""
    if result.returncode != 0 and result.stderr.strip():
        print(f"  git {context}: {result.stderr.strip()}")


def create_branch(branch_name: str) -> None:
    git(["checkout", "-b", branch_name])


def commit_files(files: list[Path], message: str) -> None:
    for f in files:
        git(["add", str(f.relative_to(VAULT_ROOT))])
    result = git(["diff", "--cached", "--quiet"], check=False)
    if result.returncode == 0:
        print("  Nothing to commit.")
        return
    git(["commit", "-m", message])


def merge_branch(branch_name: str, target: str = "main") -> bool:
    """Merge branch into target. Return True on success."""
    result = git(["checkout", target], check=False)
    if result.returncode != 0:
        result = git(["checkout", "master"], check=False)
        _git_check(result, "checkout master")
    result = git(["merge", "--no-ff", branch_name,
                  "-m", f"compile: merge {branch_name}"], check=False)
    _git_check(result, f"merge {branch_name}")
    return result.returncode == 0


def delete_branch(branch_name: str) -> None:
    git(["branch", "-d", branch_name], check=False)


def current_branch() -> str:
    result = git(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


# ---------------------------------------------------------------------------
# Main compilation loop
# ---------------------------------------------------------------------------

def compile_one(
    raw_path: Path,
    compilation_prompt: str,
    lc: llmlib.LLMClient,
    dry_run: bool,
    log: loglib.RunLogger,
) -> list[tuple[Path, str]]:
    """
    Compile a single raw file. Returns list of (wiki_path, content) pairs
    that passed validation.
    """
    print(f"\n  Compiling: {raw_path.relative_to(VAULT_ROOT)}")

    wiki_context = selective_wiki_context(raw_path)
    prompt = build_prompt(compilation_prompt, raw_path, wiki_context)

    if not llmlib.fits_in_context(prompt):
        log.warn(f"Prompt for {raw_path.name} exceeds context limit — using selective context only")

    if dry_run:
        print(f"    Prompt: ~{len(prompt)//1000}k chars  (dry run — LLM not called)")
        return []

    response = llmlib.call(lc, prompt, max_tokens=8192)

    if not response.strip() or "<<< NO OUTPUT >>>" in response:
        if "<<< NO OUTPUT >>>" in response:
            print(f"    No output for {raw_path.name} — LLM signalled nothing to write")
        else:
            log.warn(f"Empty response for {raw_path.name}")
        return []

    blocks = parse_file_blocks(response)

    if not blocks:
        # LLM didn't use FILE delimiters — save raw response for manual review
        fallback = VAULT_ROOT / "raw" / "general" / f"compile-output-{raw_path.stem}.md"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(response, encoding="utf-8")
        log.warn(
            f"No FILE blocks found in response for {raw_path.name} — "
            f"raw output saved to {fallback.relative_to(VAULT_ROOT)}"
        )
        return []

    ALLOWED_PREFIXES = ("wiki/", "lint/")

    validated: list[tuple[Path, str]] = []
    for file_path_str, content in blocks:
        # Reject paths outside permitted directories — prevents LLM from writing
        # to Vault/, templates/, raw/, or the vault root.
        normalized = file_path_str.lstrip("/").replace("\\", "/")
        if not any(normalized.startswith(p) for p in ALLOWED_PREFIXES):
            log.warn(
                f"Rejected output path '{file_path_str}' — "
                f"LLM output must be under wiki/ or lint/. Skipped."
            )
            continue

        # Resolve path relative to vault root
        wiki_path = VAULT_ROOT / normalized

        # Validate before accepting
        result = validatelib.validate_content(content, normalized)
        if result.hard_fails:
            log.warn(
                f"Validation failed for {file_path_str} "
                f"({len(result.hard_fails)} hard fail(s)) — skipped"
            )
            for v in result.hard_fails:
                print(f"    HOOK FAIL [{v.hook_type}]: {v.message}")
                print(f"      Fix: {v.fix}")
            continue

        if result.warnings:
            for v in result.warnings:
                log.warn(f"{file_path_str}: {v.message}")

        validated.append((wiki_path, content))
        print(f"    Validated: {file_path_str}")

    return validated


def main() -> int:
    global VAULT_ROOT, WIKI_DIR, RAW_DIR, LOGS_DIR, PROMPT_FILE, LOCK_FILE
    VAULT_ROOT  = require_vault()
    WIKI_DIR    = VAULT_ROOT / "wiki"
    RAW_DIR     = VAULT_ROOT / "raw"
    LOGS_DIR    = VAULT_ROOT / "logs"
    PROMPT_FILE = VAULT_ROOT / "Vault" / "COMPILATION_PROMPT.md"
    LOCK_FILE   = LOGS_DIR / ".compile.lock"

    parser = argparse.ArgumentParser(description="Vault compilation driver")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without calling the LLM")
    parser.add_argument("--no-git", action="store_true",
                        help="Write files directly without branch/merge workflow")
    parser.add_argument("--force", action="store_true",
                        help="Recompile all raw files, ignoring .compiled markers")
    args = parser.parse_args()

    if not acquire_lock():
        print("ERROR: Another compile is already running. "
              f"If this is wrong, delete {LOCK_FILE}")
        return 1

    try:
        return _run(args)
    finally:
        release_lock()


def _run(args: argparse.Namespace) -> int:
    with loglib.RunLogger("compile") as log:
        config = load_config()
        load_env_file(config)

        if not PROMPT_FILE.exists():
            print(f"ERROR: COMPILATION_PROMPT.md not found at {PROMPT_FILE}")
            return 1

        compilation_prompt = PROMPT_FILE.read_text(encoding="utf-8")
        raw_list = raw_files(force=args.force)

        if not raw_list:
            total = len(list(RAW_DIR.rglob("*.md")))
            if total:
                print(f"All {total} raw file(s) already compiled. Use --force to recompile.")
                log.set("raw_files", 0)
                log.set("files_written", 0)
                log.set("files_skipped", 0)
                log.set("already_compiled", total)
            else:
                print("No files in raw/ — nothing to compile.")
                log.set("raw_files", 0)
            return 0

        print(f"Found {len(raw_list)} raw file(s) to compile.")
        log.set("raw_files", len(raw_list))

        if args.dry_run:
            lc = None
        else:
            lc = llmlib.resolve(config)

        use_git = not args.no_git and git_available()
        branch_name = None
        original_branch = current_branch() if use_git else None

        if use_git and not args.dry_run:
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            branch_name = f"braindex/compile-{ts}"
            create_branch(branch_name)
            print(f"Created branch: {branch_name}")

        all_written: list[Path] = []
        files_skipped = 0

        for raw_path in raw_list:
            try:
                validated = compile_one(
                    raw_path, compilation_prompt, lc, args.dry_run, log
                )
            except Exception as e:
                log.warn(f"Failed to compile {raw_path.name}: {e}")
                files_skipped += 1
                continue

            for wiki_path, content in validated:
                if args.dry_run:
                    print(f"    Would write: {wiki_path.relative_to(VAULT_ROOT)}")
                    continue

                wiki_path.parent.mkdir(parents=True, exist_ok=True)
                wiki_path.write_text(content, encoding="utf-8")
                all_written.append(wiki_path)
                print(f"    Written: {wiki_path.relative_to(VAULT_ROOT)}")

            # Mark raw file compiled only if at least one article was written
            if not args.dry_run and validated:
                mark_compiled(raw_path)

        log.set("files_written", len(all_written))
        log.set("files_skipped", files_skipped)

        if not args.dry_run and all_written and use_git:
            commit_files(
                all_written,
                f"compile: {len(all_written)} article(s) from {len(raw_list)} raw file(s)"
            )

            # Validate the full written set before merging
            all_pass = all(
                validatelib.validate_file(p).passed for p in all_written
            )

            if all_pass:
                merged = merge_branch(branch_name, original_branch)
                if merged:
                    delete_branch(branch_name)
                    print(f"\nAuto-merged to {original_branch}.")
                else:
                    print(f"\nMerge conflict — review branch '{branch_name}' manually.")
                    log.warn(f"Auto-merge failed — branch {branch_name} needs manual review")
            else:
                print(
                    f"\nValidation failures detected — branch '{branch_name}' "
                    "left open for review. Fix issues and merge manually."
                )
                log.warn(f"Branch {branch_name} not merged — validation failures present")

        if args.dry_run:
            print("\nDry run complete — nothing written.")
        else:
            print(f"\nCompile complete: {len(all_written)} file(s) written, "
                  f"{files_skipped} skipped.")

        return 0


if __name__ == "__main__":
    sys.exit(main())
