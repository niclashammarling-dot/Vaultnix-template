"""
setup.py — Vault initialisation script.

Reads vault.config.yaml, creates the full directory structure at vault.path,
fills all {{PLACEHOLDERS}} in prompt/config files, and writes seed articles
and MOC stubs for every declared domain.

Usage:
    python3 scripts/setup.py [--dry-run]

Options:
    --dry-run   Print what would be created without writing anything.

Run once after editing vault.config.yaml. Safe to re-run — existing files
are never overwritten (new domains and directories are added, nothing removed).
"""
from __future__ import annotations

from pathlib import Path
import argparse
import sys
import textwrap

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install pyyaml")

from braindex.vault import DATA_DIR

# Structural domains always present regardless of user config
STRUCTURAL_DOMAINS = ["knowledge-work", "inspiration"]

# Inspiration subdirectories
INSPIRATION_SUBDIRS = ["design", "nature", "brand", "concept"]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(config_path: Path | None = None) -> dict:
    if config_path is None:
        config_path = Path.cwd() / "vault.config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"vault.config.yaml not found at {config_path}. "
            "Run 'braindex init' to create one."
        )
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_config(config: dict) -> None:
    vault = config.get("vault", {})
    required = ["name", "owner", "path"]
    missing = [k for k in required if not vault.get(k, "").strip()]
    if missing:
        raise ValueError(
            f"vault.config.yaml is missing required vault fields: {missing}. "
            "Fill these in before running setup."
        )
    domains = config.get("domains", [])
    if not domains:
        raise ValueError(
            "vault.config.yaml has no domains defined. "
            "Add at least one domain before running setup."
        )


# ---------------------------------------------------------------------------
# Placeholder generation
# ---------------------------------------------------------------------------

def domain_names(config: dict) -> list[str]:
    """All user domains + structural domains."""
    user = [d["name"] for d in config.get("domains", [])]
    return user + [s for s in STRUCTURAL_DOMAINS if s not in user]


def make_domain_list(names: list[str]) -> str:
    """Folder tree lines for ARCHITECTURE OVERVIEW."""
    lines = []
    for name in names:
        if name == "inspiration":
            continue  # rendered separately in template
        lines.append(f"│   ├── {name}/")
    return "\n".join(lines)


def make_domain_moc_list(names: list[str]) -> str:
    lines = []
    for name in names:
        lines.append(f"- wiki/_mocs/{name}-moc.md")
    return "\n".join(lines)


def make_domain_context(config: dict) -> str:
    """Per-domain description block for the CONTEXT section."""
    blocks = []
    for domain in config.get("domains", []):
        name = domain["name"]
        desc = domain.get("description", "No description provided.").strip()
        # Wrap description cleanly
        wrapped = textwrap.fill(desc, width=80, subsequent_indent="  ")
        blocks.append(f"**{name}** — {wrapped}")
    return "\n\n".join(blocks)


def make_domain_raw_suggestions(names: list[str]) -> str:
    lines = []
    for name in names:
        lines.append(f"  {name}:     [suggestion]")
    return "\n".join(lines)


def fill_placeholders(text: str, config: dict, today: str = "") -> str:
    from datetime import date as _date
    vault   = config.get("vault", {})
    names   = domain_names(config)
    today   = today or _date.today().isoformat()

    # USER_DOMAIN_MOC_LIST: user domains only — used in index files where
    # knowledge-work is already hardcoded, to avoid duplication.
    user_names = [d["name"] for d in config.get("domains", [])]
    user_moc_lines = "\n".join(
        f"- [[{name}-moc]] — *(Agent writes argument after first compile)*"
        for name in user_names
    ) if user_names else "*(No additional domains configured)*"

    replacements = {
        "{{VAULT_NAME}}":              vault.get("name", "My Vault"),
        "{{OWNER}}":                   vault.get("owner", "You"),
        "{{VAULT_PATH}}":              vault.get("path", "/path/to/your/vault"),
        "{{DOMAIN_LIST}}":             make_domain_list(names),
        "{{DOMAIN_MOC_LIST}}":         make_domain_moc_list(names),
        "{{USER_DOMAIN_MOC_LIST}}":    user_moc_lines,
        "{{DOMAIN_CONTEXT}}":          make_domain_context(config),
        "{{DOMAIN_RAW_SUGGESTIONS}}":  make_domain_raw_suggestions(names),
        "{{TODAY}}":                   today,
    }
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------

def create_dirs(vault: Path, names: list[str], dry_run: bool) -> None:
    dirs = []

    for name in names:
        dirs.append(vault / "raw" / name)
        dirs.append(vault / "wiki" / name)
        dirs.append(vault / "outputs" / name)

    # Inspiration subdirs
    for sub in INSPIRATION_SUBDIRS:
        dirs.append(vault / "raw" / "inspiration" / sub)
        dirs.append(vault / "wiki" / "inspiration" / sub)

    # Structural wiki dirs
    for d in ["_mocs", "_concepts", "_index", "_skills"]:
        dirs.append(vault / "wiki" / d)

    # Asset and tooling dirs
    for d in ["assets/images", "assets/pdfs", "lint", "templates"]:
        dirs.append(vault / d)

    # Runtime data dir (query nominations, future queue files)
    dirs.append(vault / "data")

    for d in dirs:
        if dry_run:
            print(f"  mkdir  {d.relative_to(vault)}")
        else:
            d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# File writing (skip if exists)
# ---------------------------------------------------------------------------

def write_file(path: Path, content: str, dry_run: bool) -> None:
    if path.exists():
        return  # never overwrite
    if dry_run:
        print(f"  write  {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Seed content generators
# ---------------------------------------------------------------------------

def seed_moc(domain: str, date_str: str) -> str:
    return f"""---
title: {domain} — Map of Content
type: moc
project: {domain}
date: {date_str}
status: seed
---

## The Argument

*(REQUIRED — write 2-3 sentences that make a claim about this domain, not describe it. A claim can be contested; a description cannot. Answer: what is this domain about, and what is the central tension or design question? A MOC without a defensible Argument has failed structurally.)*

## Core Articles

*(3-5 articles that must be read to understand this domain — one clause each on why they are foundational, not what they cover)*

## Topic Clusters

*(Articles grouped by sub-theme. Each cluster has a 1-sentence description of what holds it together. If a cluster exceeds 8 articles, split it and document the split in Synthesis Claims.)*

## Cross-Domain Connections

*(Links to articles or MOCs in other domains — explicit about why an agent navigating this domain would also need to visit that one)*

## Synthesis Claims

*(2-4 claims that only emerge from reading this domain together — things visible at MOC level but not within any individual article. Empty Synthesis Claims means the domain has not been compiled deeply enough.)*

## Open Territory

*(Genuine gaps: what does this domain not yet contain that it should? What would an agent wish existed here?)*
"""


def seed_overview(domain: str, description: str, date_str: str) -> str:
    return f"""---
title: {domain} — Overview
project: {domain}
tags: [{domain}, overview]
date: {date_str}
status: seed
moc: [{domain}-moc]
---

## Summary

{description.strip()}

## Key Concepts


## Details


## Connections


## Open Questions

"""


def seed_index(names: list[str], date_str: str) -> str:
    moc_lines = "\n".join(
        f"- [[{name}-moc]] — *(Agent writes argument summary after first compile)*"
        for name in names
    )
    return f"""---
title: Master Index
type: index
date: {date_str}
---

## Pending Review
*(Nightly drafts awaiting review — remove entry once reviewed or promoted to active)*

## Projects
*(Start here → read the MOC for a domain before drilling into articles)*

{moc_lines}

## All MOCs
See [[MOC-INDEX]] for the full domain orientation map and cross-domain connections.

## Cross-Project Concepts
*(Agent populates — concepts appearing across 2+ projects)*

## Inspiration
See [[INSPIRATION]] for the full visual catalog.

## Recent Additions
*(Agent updates on each compilation run)*

## Suggested Next
*(Agent populates — stub links that would most improve graph connectivity)*
"""


def seed_moc_index(names: list[str], date_str: str) -> str:
    moc_lines = "\n".join(
        f"- [[{name}-moc]] — *(Agent writes argument summary after first compile)*"
        for name in names
    )
    return f"""---
title: MOC Index — Domain Orientation Map
type: index
date: {date_str}
---

## Domain Maps
*(Agent entry point: read a MOC before drilling into project articles)*

{moc_lines}

## Cross-Domain Connection Map
*(Agent populates after first full compile — which MOCs link to which, and why)*
"""


def seed_inspiration(date_str: str) -> str:
    return f"""---
title: Inspiration Catalog
type: index
date: {date_str}
---

## Design
*(Agent populates — visual assets tagged #inspiration/design)*

## Nature
*(Agent populates — visual assets tagged #inspiration/nature)*

## Brand
*(Agent populates — visual assets tagged #inspiration/brand)*

## Typography
*(Agent populates — visual assets tagged #inspiration/typography)*

## Concept
*(Agent populates — visual assets tagged #inspiration/concept)*
"""


def write_obsidian_exclusions(vault: Path, dry_run: bool) -> None:
    """
    Write Obsidian config files so the graph shows only wiki/ articles.

    app.json — userIgnoreFilters: excludes operational dirs from search.
    graph.json — search:path:wiki + hideUnresolved + no orphans.

    write_file() skips both if the user already has these files.
    .obsidian/ is gitignored so neither file is committed.
    """
    import json

    # app.json: exclude operational/tooling dirs from search and file switcher
    excluded = [
        "Vault", "templates", "raw", "outputs", "logs", "lint",
        "CLAUDE.md", "BENCHMARK.md",
    ]
    write_file(
        vault / ".obsidian" / "app.json",
        json.dumps({"userIgnoreFilters": excluded}, indent=2) + "\n",
        dry_run,
    )

    # graph.json: show only wiki/ files; hide unresolved stubs and orphans
    write_file(
        vault / ".obsidian" / "graph.json",
        json.dumps({
            "collapse-filter": False,
            "search": "path:wiki",
            "hideUnresolved": True,
            "showOrphans": False,
        }, indent=2) + "\n",
        dry_run,
    )


def seed_gitignore() -> str:
    return """raw/
outputs/
logs/
*.compiled
.env
__pycache__/
*.pyc
*.Zone.Identifier
.obsidian/
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Vault initialisation script")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be created without writing")
    args = parser.parse_args()
    dry_run = args.dry_run

    config = load_config()
    validate_config(config)

    vault_cfg = config["vault"]
    path_str  = vault_cfg["path"].strip()
    vault     = Path(path_str).expanduser().resolve()
    names     = domain_names(config)

    from datetime import date
    today = date.today().isoformat()

    print(f"\nBraindex setup — vault: {vault}")
    print(f"Owner:   {vault_cfg['owner']}")
    print(f"Domains: {', '.join(names)}")
    if dry_run:
        print("(dry run — nothing will be written)\n")

    # 1. Directories
    print("\n[1] Creating directories...")
    create_dirs(vault, names, dry_run)

    # 2. Copy and fill prompt/config files from bundled package data
    print("\n[2] Writing prompt and config files...")
    data_template_files = [
        ("CLAUDE.md",                        vault / "CLAUDE.md"),
        ("Vault/SESSION_OPENER.md",          vault / "Vault" / "SESSION_OPENER.md"),
    ]
    for rel, dst in data_template_files:
        src = DATA_DIR / rel
        if src.exists():
            content = fill_placeholders(src.read_text(encoding="utf-8"), config, today)
            write_file(dst, content, dry_run)

    # Copy vault.config.yaml — use the live config (already written by wizard)
    config_src = Path.cwd() / "vault.config.yaml"
    if not config_src.exists():
        config_src = DATA_DIR / "vault.config.yaml"
    write_file(vault / "vault.config.yaml",
               config_src.read_text(encoding="utf-8"),
               dry_run)

    # Copy templates from bundled data
    templates_src = DATA_DIR / "templates"
    if templates_src.is_dir():
        for tmpl in templates_src.iterdir():
            if tmpl.is_file():
                write_file(vault / "templates" / tmpl.name,
                           tmpl.read_text(encoding="utf-8"), dry_run)

    # Copy .gitignore from bundled data
    gitignore_src = DATA_DIR / ".gitignore"
    if gitignore_src.exists():
        write_file(vault / ".gitignore",
                   gitignore_src.read_text(encoding="utf-8"), dry_run)

    # 3. Seed wiki content
    print("\n[3] Writing seed articles and MOCs...")

    # Copy pre-written structural wiki articles from bundled package data.
    # Index files use fill_placeholders() so user domains appear correctly.
    # write_file() skips existing files — safe to re-run.
    template_wiki_dirs = ["_concepts", "knowledge-work", "_mocs", "_index", "_skills"]
    for wiki_subdir in template_wiki_dirs:
        src_dir = DATA_DIR / "wiki" / wiki_subdir
        if src_dir.is_dir():
            for src_file in sorted(src_dir.iterdir()):
                if src_file.suffix == ".md" and src_file.is_file():
                    content = src_file.read_text(encoding="utf-8")
                    content = fill_placeholders(content, config, today)
                    dst = vault / "wiki" / wiki_subdir / src_file.name
                    write_file(dst, content, dry_run)


    # MOC stubs for user domains (knowledge-work-moc is already copied above)
    for name in names:
        if name == "knowledge-work":
            continue  # pre-written version already copied
        write_file(vault / "wiki" / "_mocs" / f"{name}-moc.md",
                   seed_moc(name, today), dry_run)

    # Domain overview stubs (user domains only)
    for domain in config.get("domains", []):
        name = domain["name"]
        desc = domain.get("description", f"{name} domain.").strip()
        write_file(vault / "wiki" / name / f"{name}-overview.md",
                   seed_overview(name, desc, today), dry_run)

    # Index files are copied from the template above (with placeholders filled).
    # The seed_index/seed_moc_index/seed_inspiration functions are kept as
    # fallback if the template files are missing.

    # 4. .gitignore
    print("\n[4] Writing .gitignore...")
    write_file(vault / ".gitignore", seed_gitignore(), dry_run)

    # 4b. Obsidian graph exclusions — keep operational/tooling dirs out of the graph
    # .obsidian/ is gitignored so this won't be committed; write_file skips if exists.
    print("\n[4b] Writing Obsidian graph exclusions...")
    write_obsidian_exclusions(vault, dry_run)

    # 5. GitHub Actions workflow (only if platform=github-actions)
    lint_platform = config.get("lint", {}).get("platform", "")
    if lint_platform == "github-actions":
        print("\n[5] Writing GitHub Actions workflow...")
        gha_src = DATA_DIR / "github" / "workflows" / "weekly-lint.yml"
        if gha_src.exists():
            write_file(
                vault / ".github" / "workflows" / "weekly-lint.yml",
                gha_src.read_text(encoding="utf-8"),
                dry_run,
            )
    else:
        print("\n[5] Skipping GitHub Actions (platform is not github-actions).")

    print(f"""
Setup complete.

Next steps:
  1. cd {vault}
  2. git init && git add -A && git commit -m "init: vault"
  3. Drop your first raw sources into raw/[domain]/
  4. Open Claude Code in the vault directory and say "compile"
  5. Open the vault in Obsidian → Graph View (Ctrl+G) to see your knowledge topology
""")


if __name__ == "__main__":
    main()
