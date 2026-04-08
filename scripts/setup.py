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
from pathlib import Path
import argparse
import shutil
import sys
import textwrap

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install pyyaml")

BRAINDEX_ROOT = Path(__file__).parent.parent

# Structural domains always present regardless of user config
STRUCTURAL_DOMAINS = ["knowledge-work", "inspiration"]

# Inspiration subdirectories
INSPIRATION_SUBDIRS = ["design", "nature", "brand", "concept"]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    config_path = BRAINDEX_ROOT / "vault.config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"vault.config.yaml not found at {config_path}. "
            "Edit vault.config.yaml before running setup."
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


def fill_placeholders(text: str, config: dict) -> str:
    vault   = config.get("vault", {})
    names   = domain_names(config)

    replacements = {
        "{{VAULT_NAME}}":             vault.get("name", "My Vault"),
        "{{OWNER}}":                  vault.get("owner", "You"),
        "{{VAULT_PATH}}":             vault.get("path", "/path/to/your/vault"),
        "{{DOMAIN_LIST}}":            make_domain_list(names),
        "{{DOMAIN_MOC_LIST}}":        make_domain_moc_list(names),
        "{{DOMAIN_CONTEXT}}":         make_domain_context(config),
        "{{DOMAIN_RAW_SUGGESTIONS}}": make_domain_raw_suggestions(names),
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
    for d in ["_mocs", "_concepts", "_index"]:
        dirs.append(vault / "wiki" / d)

    # Asset and tooling dirs
    for d in ["assets/images", "assets/pdfs", "lint", "templates"]:
        dirs.append(vault / d)

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
*(Agent writes after first compile — 2-3 sentences on the shape and central tension of this domain)*

## Core Articles
*(Agent populates — 3-5 foundational articles, one clause each on why foundational)*

## Topic Clusters
*(Agent populates — articles grouped by sub-theme, each cluster with 1-sentence description)*

## Cross-Domain Connections
*(Agent populates — links to other MOCs with explicit rationale for the connection)*

## Synthesis Claims
*(Agent populates — claims only visible at MOC level, not within individual articles)*

## Open Territory
*(Agent populates — genuine gaps: what should exist here but does not yet?)*
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


def seed_gitignore() -> str:
    return """raw/
outputs/
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
    vault     = Path(vault_cfg["path"]).expanduser()
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

    # 2. Copy and fill prompt/config files from Braindex template
    print("\n[2] Writing prompt and config files...")
    template_files = {
        BRAINDEX_ROOT / "CLAUDE.md":                   vault / "CLAUDE.md",
        BRAINDEX_ROOT / "Vault" / "COMPILATION_PROMPT.md": vault / "Vault" / "COMPILATION_PROMPT.md",
        BRAINDEX_ROOT / "Vault" / "SESSION_OPENER.md": vault / "Vault" / "SESSION_OPENER.md",
    }
    for src, dst in template_files.items():
        if src.exists():
            content = fill_placeholders(src.read_text(encoding="utf-8"), config)
            write_file(dst, content, dry_run)

    # Copy scripts unchanged
    for script in (BRAINDEX_ROOT / "scripts").iterdir():
        if script.suffix == ".py":
            write_file(vault / "scripts" / script.name,
                       script.read_text(encoding="utf-8"), dry_run)

    # Copy templates unchanged
    for tmpl in (BRAINDEX_ROOT / "templates").iterdir():
        write_file(vault / "templates" / tmpl.name,
                   tmpl.read_text(encoding="utf-8"), dry_run)

    # Copy lint scripts unchanged
    for ls in (BRAINDEX_ROOT / "lint").iterdir():
        if ls.suffix == ".py":
            write_file(vault / "lint" / ls.name,
                       ls.read_text(encoding="utf-8"), dry_run)

    # Copy vault.config.yaml
    write_file(vault / "vault.config.yaml",
               (BRAINDEX_ROOT / "vault.config.yaml").read_text(encoding="utf-8"),
               dry_run)

    # Copy requirements.txt
    write_file(vault / "requirements.txt",
               (BRAINDEX_ROOT / "requirements.txt").read_text(encoding="utf-8"),
               dry_run)

    # 3. Seed wiki content
    print("\n[3] Writing seed articles and MOCs...")

    # MOC stubs for all domains
    for name in names:
        write_file(vault / "wiki" / "_mocs" / f"{name}-moc.md",
                   seed_moc(name, today), dry_run)

    # Domain overview stubs (user domains only)
    for domain in config.get("domains", []):
        name = domain["name"]
        desc = domain.get("description", f"{name} domain.").strip()
        write_file(vault / "wiki" / name / f"{name}-overview.md",
                   seed_overview(name, desc, today), dry_run)

    # Index files
    write_file(vault / "wiki" / "_index" / "INDEX.md",
               seed_index(names, today), dry_run)
    write_file(vault / "wiki" / "_index" / "MOC-INDEX.md",
               seed_moc_index(names, today), dry_run)
    write_file(vault / "wiki" / "_index" / "INSPIRATION.md",
               seed_inspiration(today), dry_run)

    # 4. .gitignore
    print("\n[4] Writing .gitignore...")
    write_file(vault / ".gitignore", seed_gitignore(), dry_run)

    # 5. GitHub Actions workflow
    print("\n[5] Writing GitHub Actions workflow...")
    gha_src = BRAINDEX_ROOT / ".github" / "workflows" / "weekly-lint.yml"
    if gha_src.exists():
        write_file(
            vault / ".github" / "workflows" / "weekly-lint.yml",
            gha_src.read_text(encoding="utf-8"),
            dry_run,
        )

    print(f"""
Setup complete.

Next steps:
  1. cd {vault}
  2. git init && git add -A && git commit -m "init: vault"
  3. Drop your first raw sources into raw/[domain]/
  4. Run: python3 scripts/compile.py  (or paste Vault/COMPILATION_PROMPT.md into Claude Code)
  5. Open the vault in Obsidian → Graph View (Ctrl+G) to see your knowledge topology
""")


if __name__ == "__main__":
    main()
