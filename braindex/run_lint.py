"""
run_lint.py — Vault weekly lint check.

Reads all wiki/ markdown files, runs mechanical graph checks, then passes
results + content to an LLM for higher-level analysis.

LLM provider and model are read from vault.config.yaml.
API keys are read from the environment (or an optional env_file in config).
"""
from collections import defaultdict
from datetime import date
from pathlib import Path
import re
import os
import sys

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install pyyaml")

from braindex import llm as llmlib
from braindex import logger as loglib
from braindex.vault import require_vault

VAULT_ROOT: Path = None  # type: ignore[assignment]  # set in main()


# ---------------------------------------------------------------------------
# Config loading
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
    """Load API keys from an optional env_file declared in config."""
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
# Mechanical graph checks — authoritative, not LLM-inferred
# ---------------------------------------------------------------------------

WIKI_DIR: Path = None  # type: ignore[assignment]  # set in main()
LINT_DIR: Path = None  # type: ignore[assignment]

WIKILINK_RE = re.compile(r'\[\[([^\]|#]+)')


def build_graph(wiki_files: list[Path]) -> tuple[dict, dict, dict]:
    """Return (slug_to_file, outbound, inbound) maps."""
    slug_to_file: dict[str, Path] = {}
    for p in wiki_files:
        slug_to_file[p.stem] = p

    outbound: dict[str, list[str]] = defaultdict(list)
    inbound: dict[str, list[str]] = defaultdict(list)

    for p in wiki_files:
        src = p.stem
        text = p.read_text(encoding="utf-8")
        targets = WIKILINK_RE.findall(text)
        for raw in targets:
            tgt = raw.strip()
            if tgt and tgt != src:
                outbound[src].append(tgt)
                inbound[tgt].append(src)

    return slug_to_file, dict(outbound), dict(inbound)


def mechanical_checks(wiki_files: list[Path]) -> str:
    slug_to_file, outbound, inbound = build_graph(wiki_files)
    all_slugs = set(slug_to_file)

    orphans = sorted(
        s for s in all_slugs
        if len(inbound.get(s, [])) == 0
    )

    stubs: dict[str, list[str]] = defaultdict(list)
    for src, targets in outbound.items():
        for tgt in targets:
            if tgt not in all_slugs:
                stubs[tgt].append(src)

    weak = sorted(
        (s, len(outbound.get(s, [])))
        for s in all_slugs
        if len(outbound.get(s, [])) < 3
    )

    hubs = sorted(
        ((s, len(v)) for s, v in inbound.items() if s in all_slugs),
        key=lambda x: -x[1]
    )[:10]

    lines = ["## Mechanical Graph Checks (authoritative — do not re-derive these)\n"]

    lines.append(f"### True Orphans ({len(orphans)} articles with 0 inbound links)")
    if orphans:
        for s in orphans:
            lines.append(f"- `{s}` — inbound: 0")
    else:
        lines.append("- None")

    lines.append(f"\n### Stub Links ({len(stubs)} wikilinks with no target file)")
    if stubs:
        for tgt in sorted(stubs):
            sources = ", ".join(f"`{s}`" for s in sorted(set(stubs[tgt])))
            lines.append(f"- `[[{tgt}]]` — linked from: {sources}")
    else:
        lines.append("- None")

    lines.append(f"\n### Weak Nodes (fewer than 3 outbound links)")
    if weak:
        for s, count in weak:
            lines.append(f"- `{s}` — {count} outbound")
    else:
        lines.append("- None")

    lines.append(f"\n### Top Hubs by Inbound Link Count")
    for s, count in hubs:
        lines.append(f"- `{s}` — {count} inbound")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM lint
# ---------------------------------------------------------------------------

LINT_PROMPT = """\
You are the knowledge compiler for this vault. The mechanical graph checks \
below are authoritative — they were computed by parsing actual wikilinks. \
Do NOT re-derive orphan counts, stub lists, or weak node lists. Use the \
mechanical results as ground truth for the Graph Health section.

Write a structured markdown report covering:

## MOC Argument Health (check this first — it is the highest-leverage failure)
For every file in wiki/_mocs/:
- Read ## The Argument. Is it a claim, or a description? A claim can be contested; a description cannot.
- Flag any MOC where The Argument is absent, a placeholder, or merely describes the domain rather than asserting something about it.
- Flag any MOC where ## Synthesis Claims is empty — a domain with no synthesis claims has not been compiled deeply enough.
- Flag any MOC that is drifting toward a list (Topic Clusters growing without a corresponding Argument update).
Name each failing MOC explicitly. A MOC that does not argue is a structural failure regardless of how many articles it lists.

## Graph Health
- Use the mechanical checks above verbatim for orphans, stubs, and weak nodes
- Suggest specific backlink sources for each true orphan
- Flag any project domains with no MOC

## Topology Health
- Clusters with no cross-domain links (isolated islands) — flag
- Are the top hubs (from mechanical checks) the right conceptual centers?
- If the longest path between any two MOCs exceeds 4 hops, suggest a bridging concept article

## Content Health
- Articles with status: draft — flag
- Open Questions never addressed — surface the best 5
- Contradictions between articles in the same project — flag both

## Contradiction Scan
- Flag any direct conflicts between articles in the same project
- Suggest escalation path: flag in Open Questions of both articles + surface in Pending Review

## Growth Suggestions
- 3 cross-project concept articles the corpus is clearly missing
- 3 Open Questions worth turning into new raw/ sources

Be concrete. Name specific files, specific missing links, specific stub targets.
"""


def gather_wiki(wiki_files: list[Path]) -> str:
    parts = []
    for path in sorted(wiki_files):
        rel = path.relative_to(VAULT_ROOT)
        parts.append(f"=== {rel} ===\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global VAULT_ROOT, WIKI_DIR, LINT_DIR
    VAULT_ROOT = require_vault()
    WIKI_DIR   = VAULT_ROOT / "wiki"
    LINT_DIR   = VAULT_ROOT / "lint"

    with loglib.RunLogger("lint") as log:
        config = load_config()
        load_env_file(config)
        lc = llmlib.resolve(config)

        print("Reading wiki...")
        wiki_files = sorted(WIKI_DIR.rglob("*.md"))
        content = gather_wiki(wiki_files)
        print(f"{len(wiki_files):,} files, {len(content):,} chars")
        log.set("wiki_files", len(wiki_files))
        log.set("wiki_chars", len(content))

        print("Running mechanical checks...")
        mechanical = mechanical_checks(wiki_files)
        print(mechanical)

        print("Running LLM lint...")
        prompt = f"{LINT_PROMPT}\n\n{mechanical}\n\n## Vault Content\n\n{content}"

        if not llmlib.fits_in_context(prompt):
            log.warn("Lint prompt exceeds context limit — vault content will be truncated")

        report = llmlib.call(lc, prompt)

        LINT_DIR.mkdir(exist_ok=True)
        today = date.today().isoformat()
        output = LINT_DIR / f"{today}-lint.md"
        output.write_text(
            f"---\ndate: {today}\ntype: lint\n---\n\n{mechanical}\n\n---\n\n{report}\n",
            encoding="utf-8",
        )
        log.set("output", str(output.relative_to(VAULT_ROOT)))
        print(f"Written: {output}")


if __name__ == "__main__":
    main()
