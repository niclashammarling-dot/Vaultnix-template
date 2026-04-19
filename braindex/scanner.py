#!/usr/bin/env python3
"""
scanner.py — Vault Bootstrap Scanner
Scans a folder, classifies content into domain candidates,
applies a privacy filter, samples representative files,
and generates a bootstrap prompt for LLM schema proposal.

Usage:
  python scanner.py --path ~/Documents/ClientWork
  python scanner.py --path ~/Documents --depth 3 --output ./vault-bootstrap
  python scanner.py --path ~/Documents --dry-run
"""

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import track
    from rich.prompt import Confirm, Prompt
    from rich.panel import Panel
    from rich.tree import Tree
    RICH = True
except ImportError:
    RICH = False

console = Console() if RICH else None

def log(msg, style=None):
    if RICH:
        console.print(msg, style=style)
    else:
        print(msg)

# ============================================================
# CONFIGURATION
# ============================================================

# File types that carry knowledge
INCLUDE_EXTENSIONS = {
    '.md', '.txt', '.rst',           # text
    '.pdf',                           # documents
    '.docx', '.doc',                  # word
    '.pptx', '.ppt',                  # slides
    '.csv',                           # data
    '.json', '.yaml', '.yml',         # structured
    '.py', '.js', '.ts',              # code (README + docs only handled separately)
    '.html', '.htm',                  # web
    '.epub',                          # books
}

# Never include these regardless of extension
EXCLUDE_PATTERNS = [
    r'node_modules', r'\.git', r'\.next', r'__pycache__',
    r'\.cache', r'\.venv', r'venv', r'env',
    r'dist', r'build', r'\.build',
    r'site-packages', r'\.npm',
    r'Thumbs\.db', r'\.DS_Store',
    r'\.pytest_cache', r'\.mypy_cache',
]

# Privacy — never ingest, no prompt
PRIVACY_NEVER = [
    r'password', r'passwd', r'credentials', r'secrets?',
    r'\.env$', r'\.env\.', r'id_rsa', r'id_ed25519',
    r'\.pem$', r'\.key$', r'\.p12$', r'\.pfx$',
    r'keystore', r'wallet',
]

# Privacy — always prompt before ingesting
PRIVACY_PROMPT = [
    r'\bhr\b', r'human.?resources?', r'payroll', r'salary', r'performance.?review',
    r'personal', r'private', r'\bnda\b', r'confidential',
    r'legal', r'contract', r'invoice', r'financial',
    r'medical', r'health', r'therapy',
    r'icloud', r'dropbox.*private',
]

# Folder names that strongly signal domain identity
DOMAIN_SIGNAL_FOLDERS = {
    'clients': 'clients', 'client': 'clients',
    'projects': 'projects', 'project': 'projects',
    'work': 'work', 'job': 'work',
    'research': 'research',
    'notes': 'notes',
    'docs': 'documentation', 'documentation': 'documentation',
    'finance': 'finance', 'financial': 'finance',
    'legal': 'legal',
    'hr': 'people', 'people': 'people', 'team': 'people',
    'marketing': 'marketing', 'content': 'content',
    'engineering': 'engineering', 'tech': 'engineering',
    'product': 'product',
    'design': 'design',
    'sales': 'sales', 'crm': 'sales',
    'ops': 'operations', 'operations': 'operations',
    'personal': 'personal',
    'learning': 'learning', 'courses': 'learning', 'books': 'learning',
}

# Recency thresholds
ACTIVE_DAYS = 90       # modified within 90 days = active
ARCHIVED_DAYS = 365    # not modified in 365 days = archived

# Sampling config
MAX_SAMPLE_FILES = 8        # per domain candidate
MAX_SAMPLE_CHARS = 2000     # per file in sample
MAX_BOOTSTRAP_CHARS = 80000 # total for bootstrap prompt

# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class ScannedFile:
    path: str
    extension: str
    size_bytes: int
    modified_days_ago: float
    privacy_status: str   # 'clear' | 'never' | 'prompt'
    privacy_reason: str
    domain_hint: str
    content_preview: str
    pii_flagged: bool = False
    pii_reasons: list = field(default_factory=list)

@dataclass
class DomainCandidate:
    name: str
    folder_paths: list = field(default_factory=list)
    files: list = field(default_factory=list)
    file_count: int = 0
    active_count: int = 0
    archived_count: int = 0
    total_size_bytes: int = 0
    sample_content: str = ''

@dataclass
class ScanResult:
    scan_path: str
    scan_date: str
    total_files_found: int
    total_files_included: int
    privacy_never_count: int
    privacy_prompt_count: int
    pii_flagged_count: int
    domain_candidates: list
    raw_file_list: list
    privacy_prompt_list: list = field(default_factory=list)  # for UI review

# ============================================================
# PRIVACY FILTER
# ============================================================

def check_privacy(path: Path) -> tuple[str, str]:
    """
    Returns ('never'|'prompt'|'clear', reason).
    Runs on path only — no file content read for privacy check.
    """
    path_str = str(path).lower()
    name = path.name.lower()

    for pattern in PRIVACY_NEVER:
        if re.search(pattern, path_str, re.IGNORECASE):
            return 'never', f"matches privacy-never pattern: {pattern}"

    for pattern in PRIVACY_PROMPT:
        if re.search(pattern, path_str, re.IGNORECASE):
            return 'prompt', f"matches privacy-prompt pattern: {pattern}"

    # Check for credential-like content signals in filename
    credential_signals = ['token', 'apikey', 'api_key', 'secret', 'auth']
    for signal in credential_signals:
        if signal in name:
            return 'never', f"filename contains credential signal: {signal}"

    return 'clear', ''


def check_credential_content(content: str) -> bool:
    """
    Quick scan of file content for credential patterns.
    Returns True if credentials detected.
    """
    patterns = [
        r'(?i)(api[_\-]?key|apikey)\s*[=:]\s*["\']?[a-zA-Z0-9\-_]{20,}',
        r'(?i)(secret|token|password|passwd)\s*[=:]\s*["\']?\S{8,}',
        r'sk-[a-zA-Z0-9]{32,}',         # OpenAI-style keys
        r'ghp_[a-zA-Z0-9]{36}',          # GitHub tokens
        r'-----BEGIN [A-Z ]+ KEY-----',  # PEM keys
        r'(?i)bearer\s+[a-zA-Z0-9\-_.]{20,}',
    ]
    for p in patterns:
        if re.search(p, content[:5000]):  # Only scan first 5k chars
            return True
    return False

# ============================================================
# PII DETECTION AND REDACTION
# ============================================================

# Structured PII patterns — replaced in bootstrap prompt samples
PII_PATTERNS = [
    (r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b', '[EMAIL]', 0),
    (r'\b(?:\+?1[\s.\-]?)?\(?[2-9]\d{2}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b', '[PHONE]', 0),
    (r'\+[1-9]\d{0,2}[\s.\-]\d{3,5}[\s.\-]\d{3,9}\b', '[PHONE_INTL]', 0),
    (r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', '[ID]', 0),
    (r'\b(?:DOB|born|birthday|date of birth)[:\s]+\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b',
     '[DOB]', re.IGNORECASE),
    (r'\b\d{1,5}\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|'
     r'Drive|Dr|Lane|Ln|Court|Ct|Place|Pl|Way|Circle|Cir)\b', '[ADDRESS]', 0),
    (r'\b(?:\d{4}[\s\-]?){3}\d{4}\b', '[CARD]', 0),
    (r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:[A-Z0-9]?){0,16}\b', '[IBAN]', 0),
]

PROPER_NOUN_THRESHOLD = 0.14  # >14% non-sentence-start capitalised words = flag


def check_pii_content(content: str) -> tuple[bool, list[str]]:
    """
    Detect likely PII. Returns (has_pii, reasons).
    Does not redact — caller decides what to do.
    """
    reasons = []
    for pattern, label, flags in PII_PATTERNS:
        if re.search(pattern, content, flags):
            reasons.append(f"structured PII detected: {label}")

    words = content.split()
    if len(words) > 60:
        sentences = re.split(r'[.!?]\s+', content)
        starters = {s.strip().split()[0] for s in sentences if s.strip()}
        caps = [
            w for w in words
            if w and w[0].isupper() and w not in starters
            and len(w) > 1 and not w.isupper()
        ]
        density = len(caps) / len(words)
        if density > PROPER_NOUN_THRESHOLD:
            reasons.append(
                f"high proper noun density ({density:.0%}) — may contain personal names"
            )
    return bool(reasons), reasons


def redact_pii_from_sample(content: str) -> tuple[str, int]:
    """
    Replace structured PII in sample content before LLM sees it.
    Returns (redacted_content, replacement_count).
    Proper nouns NOT redacted — too aggressive, breaks domain signals.
    """
    redacted = content
    count = 0
    for pattern, replacement, flags in PII_PATTERNS:
        new, n = re.subn(pattern, replacement, redacted, flags)
        redacted = new
        count += n
    return redacted, count


# ============================================================
# FILE DISCOVERY
# ============================================================

def should_exclude_path(path: Path) -> bool:
    """True if path matches any exclude pattern."""
    path_str = str(path)
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, path_str):
            return True
    return False


def extract_domain_hint(path: Path, root: Path) -> str:
    """Infer domain hint from folder structure."""
    try:
        relative = path.relative_to(root)
        parts = relative.parts[:-1]  # exclude filename
    except ValueError:
        return 'general'

    for part in parts:
        hint = DOMAIN_SIGNAL_FOLDERS.get(part.lower())
        if hint:
            return hint

    # Use first meaningful folder name as hint
    for part in parts:
        if len(part) > 2 and not part.startswith('.'):
            return part.lower().replace(' ', '-').replace('_', '-')

    return 'general'


def read_text_preview(path: Path, max_chars: int = MAX_SAMPLE_CHARS) -> tuple[str, bool, list[str]]:
    """
    Safely read first N chars of a text file.
    Returns (content_or_redacted, pii_flagged, pii_reasons).
    """
    try:
        try:
            content = path.read_text(encoding='utf-8', errors='strict')
        except UnicodeDecodeError:
            content = path.read_text(encoding='latin-1', errors='replace')

        if check_credential_content(content):
            return '[REDACTED: credential pattern detected in content]', False, []

        preview = content[:max_chars]

        # PII check on preview — flag but don't block; redaction happens at sample time
        has_pii, pii_reasons = check_pii_content(preview)
        return preview, has_pii, pii_reasons

    except Exception:
        return '', False, []


def scan_folder(
    root: Path,
    max_depth: int = 4,
    include_code: bool = False,
) -> ScanResult:
    """
    Traverse root, discover and classify knowledge-bearing files.
    Returns a ScanResult with all findings.
    """
    log(f"\n[bold]Scanning:[/bold] {root}", style=None)
    log(f"Max depth: {max_depth} | Code files: {'yes' if include_code else 'no'}\n")

    all_files = []
    skipped_exclude = 0
    skipped_extension = 0
    privacy_never = []
    privacy_prompt = []
    pii_flagged_files = []  # files with PII in content (included but flagged)

    now = datetime.now()

    # Walk the tree
    file_iter = list(root.rglob('*'))
    iterable = track(file_iter, description="Discovering files...") if RICH else file_iter

    for path in iterable:
        if not path.is_file():
            continue

        # Depth check
        try:
            depth = len(path.relative_to(root).parts) - 1
            if depth > max_depth:
                continue
        except ValueError:
            continue

        # Exclude pattern check
        if should_exclude_path(path):
            skipped_exclude += 1
            continue

        # Extension check
        ext = path.suffix.lower()
        if ext not in INCLUDE_EXTENSIONS:
            skipped_extension += 1
            continue

        # Code files — only include if flag set or if in docs/README context
        if ext in {'.py', '.js', '.ts', '.html', '.htm'} and not include_code:
            name_lower = path.name.lower()
            if not any(x in name_lower for x in ['readme', 'doc', 'guide', 'spec']):
                skipped_extension += 1
                continue

        # Privacy check
        privacy_status, privacy_reason = check_privacy(path)

        # File metadata
        try:
            stat = path.stat()
            size_bytes = stat.st_size
            modified = datetime.fromtimestamp(stat.st_mtime)
            modified_days_ago = (now - modified).days
        except Exception:
            continue

        # Skip empty files
        if size_bytes == 0:
            continue

        # Read preview for clear files only
        content_preview = ''
        pii_flagged = False
        pii_reasons = []
        if privacy_status == 'clear':
            content_preview, pii_flagged, pii_reasons = read_text_preview(path)
            # Re-check after content read — credentials → hard block
            if '[REDACTED' in content_preview:
                privacy_status = 'never'
                privacy_reason = 'credential pattern in content'
                pii_flagged = False
                pii_reasons = []

        domain_hint = extract_domain_hint(path, root)

        scanned = ScannedFile(
            path=str(path),
            extension=ext,
            size_bytes=size_bytes,
            modified_days_ago=modified_days_ago,
            privacy_status=privacy_status,
            privacy_reason=privacy_reason,
            domain_hint=domain_hint,
            content_preview=content_preview,
            pii_flagged=pii_flagged,
            pii_reasons=pii_reasons,
        )

        if privacy_status == 'never':
            privacy_never.append(scanned)
        elif privacy_status == 'prompt':
            privacy_prompt.append(scanned)
        else:
            all_files.append(scanned)
            if pii_flagged:
                pii_flagged_files.append(scanned)

    log(f"\n[bold]Discovery complete[/bold]")
    log(f"  Files found:           {len(all_files) + len(privacy_never) + len(privacy_prompt)}")
    log(f"  Knowledge files:       {len(all_files)}", style="green")
    log(f"  Privacy-blocked:       {len(privacy_never)}", style="red")
    log(f"  Privacy-prompt:        {len(privacy_prompt)}", style="yellow")
    log(f"  PII flagged (content): {len(pii_flagged_files)} (samples will be redacted)", style="yellow")
    log(f"  Excluded (patterns):   {skipped_exclude}")
    log(f"  Excluded (extension):  {skipped_extension}")

    # Handle privacy-prompt files interactively
    approved_prompt = []
    if privacy_prompt and not args_dry_run:
        log(f"\n[yellow]⚠ {len(privacy_prompt)} files need your approval:[/yellow]")
        for f in privacy_prompt[:20]:  # Show max 20
            rel = Path(f.path).relative_to(root)
            if RICH:
                include = Confirm.ask(f"  Include [cyan]{rel}[/cyan]? ({f.privacy_reason})")
            else:
                resp = input(f"  Include {rel}? ({f.privacy_reason}) [y/N]: ")
                include = resp.lower() == 'y'
            if include:
                approved_prompt.append(f)
        if len(privacy_prompt) > 20:
            log(f"  [dim]... and {len(privacy_prompt) - 20} more (skipped in dry run)[/dim]")

    all_files.extend(approved_prompt)

    return ScanResult(
        scan_path=str(root),
        scan_date=datetime.now().isoformat(),
        total_files_found=len(all_files) + len(privacy_never) + len(privacy_prompt),
        total_files_included=len(all_files),
        privacy_never_count=len(privacy_never),
        privacy_prompt_count=len(privacy_prompt),
        pii_flagged_count=len(pii_flagged_files),
        domain_candidates=[],
        raw_file_list=all_files,
        privacy_prompt_list=privacy_prompt,
    )

# ============================================================
# DOMAIN CLASSIFICATION
# ============================================================

def classify_domains(scan: ScanResult) -> list[DomainCandidate]:
    """
    Group files into domain candidates based on folder hints,
    file density, and modification recency.
    """
    domain_map: dict[str, DomainCandidate] = {}
    now = datetime.now()

    for f in scan.raw_file_list:
        hint = f.domain_hint
        if hint not in domain_map:
            folder = str(Path(f.path).parent)
            domain_map[hint] = DomainCandidate(
                name=hint,
                folder_paths=[folder],
            )

        d = domain_map[hint]
        d.files.append(f)
        d.file_count += 1
        d.total_size_bytes += f.size_bytes

        if f.modified_days_ago <= ACTIVE_DAYS:
            d.active_count += 1
        elif f.modified_days_ago >= ARCHIVED_DAYS:
            d.archived_count += 1

        folder = str(Path(f.path).parent)
        if folder not in d.folder_paths:
            d.folder_paths.append(folder)

    # Sort domains by active file count descending
    domains = sorted(domain_map.values(), key=lambda d: d.active_count, reverse=True)

    # Generate sample content per domain
    for d in domains:
        d.sample_content = build_domain_sample(d)

    return domains


def build_domain_sample(domain: DomainCandidate) -> str:
    """
    Select representative files and build a sample for the bootstrap prompt.
    Applies PII redaction to all content before it enters the prompt.
    Prioritizes recently modified files.
    """
    sorted_files = sorted(domain.files, key=lambda f: f.modified_days_ago)

    selected = []
    total_chars = 0
    per_file_limit = MAX_SAMPLE_CHARS
    total_redactions = 0

    for f in sorted_files[:MAX_SAMPLE_FILES * 2]:
        if len(selected) >= MAX_SAMPLE_FILES:
            break
        if not f.content_preview or len(f.content_preview) < 50:
            continue
        if f.privacy_status != 'clear':
            continue
        if '[REDACTED' in f.content_preview:
            continue

        # Apply PII redaction to sample content
        preview_raw = f.content_preview[:per_file_limit]
        preview, n_redacted = redact_pii_from_sample(preview_raw)
        total_redactions += n_redacted

        redaction_note = f' [PII redacted: {n_redacted} patterns]' if n_redacted else ''
        entry = f"### {Path(f.path).name}{redaction_note}\n{preview}\n"

        if total_chars + len(entry) > MAX_BOOTSTRAP_CHARS // 8:
            break

        selected.append(entry)
        total_chars += len(entry)

    header = f'[{total_redactions} PII patterns redacted from this domain sample]\n\n' \
             if total_redactions else ''
    return header + '\n'.join(selected)

# ============================================================
# BOOTSTRAP PROMPT GENERATOR
# ============================================================

def generate_bootstrap_prompt(scan: ScanResult, domains: list[DomainCandidate]) -> str:
    """
    Generate the LLM bootstrap prompt for schema proposal.
    """
    domain_summaries = []
    for d in domains:
        summary = f"""
DOMAIN CANDIDATE: {d.name}
Files: {d.file_count} total ({d.active_count} active, {d.archived_count} archived)
Folders: {', '.join(d.folder_paths[:3])}
Sample content:
{d.sample_content[:3000] if d.sample_content else '[no readable content]'}
"""
        domain_summaries.append(summary)

    domains_text = '\n---\n'.join(domain_summaries)

    prompt = f"""# VAULT BOOTSTRAP — SCHEMA PROPOSAL

You are initializing a knowledge vault from a scanned filesystem.
The scanner has discovered {scan.total_files_included} knowledge-bearing files
across {len(domains)} candidate domains.

Your job is to propose a vault schema that will organize this knowledge
for agent traversal. The schema must follow these principles:
- Each domain has a clear argument (what it is and what its central tension is)
- Domains are distinct enough that an agent can determine which domain to enter
  without reading every article
- Cross-domain concepts should be named explicitly
- The schema should reflect the actual content, not an ideal structure

## CANDIDATE DOMAINS FROM FILESYSTEM

{domains_text}

## YOUR OUTPUT

Respond with a JSON object following this exact schema.
Output only the JSON. No preamble. No explanation.

{{
  "proposed_domains": [
    {{
      "id": "lowercase-hyphenated-id",
      "label": "Display Name",
      "argument": "2-3 sentences: what this domain contains and what its central tension or organizing question is",
      "source_folders": ["list of source folders that map to this domain"],
      "active_file_estimate": 0,
      "priority": "high|medium|low"
    }}
  ],
  "cross_domain_concepts": [
    {{
      "name": "concept-name",
      "appears_in": ["domain-id-1", "domain-id-2"],
      "description": "one sentence on what this concept is and why it spans domains"
    }}
  ],
  "suggested_moc_arguments": {{
    "domain-id": "The argument this domain's MOC should make — one paragraph stating what the domain is, what its central tension is, and what an agent should know before navigating into its articles."
  }},
  "schema_notes": "Any observations about the content that would affect how the vault should be structured — gaps, unusual patterns, content that doesn't fit cleanly into any domain.",
  "recommended_first_compile_order": ["domain-id-1", "domain-id-2"],
  "estimated_vault_size": {{
    "articles": 0,
    "concepts": 0,
    "compile_passes_estimated": 0
  }}
}}
"""
    return prompt


# ============================================================
# OUTPUT
# ============================================================

def write_output(
    scan: ScanResult,
    domains: list[DomainCandidate],
    bootstrap_prompt: str,
    output_dir: Path,
):
    """Write all scanner outputs to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Bootstrap prompt (paste into LLM)
    prompt_path = output_dir / 'bootstrap-prompt.md'
    prompt_path.write_text(bootstrap_prompt, encoding='utf-8')
    log(f"\n  [green]✓[/green] Bootstrap prompt → {prompt_path}")

    # 2. Permanent ingest manifest — the contract of what was read
    manifest_files = [
        {
            'path': f.path,
            'domain': f.domain_hint,
            'extension': f.extension,
            'size_bytes': f.size_bytes,
            'modified_days_ago': int(f.modified_days_ago),
            'pii_flagged': f.pii_flagged,
            'pii_reasons': f.pii_reasons,
        }
        for f in scan.raw_file_list
    ]
    manifest = {
        'vault_bootstrap_manifest': True,
        'scan_path': scan.scan_path,
        'scan_date': scan.scan_date,
        'total_files_included': scan.total_files_included,
        'privacy_never_count': scan.privacy_never_count,
        'privacy_prompt_count': scan.privacy_prompt_count,
        'pii_flagged_count': scan.pii_flagged_count,
        'domain_count': len(domains),
        'note': (
            'This manifest is the permanent record of every file read during vault '
            'initialization. Commit it to the vault alongside compiled wiki articles.'
        ),
        'files': manifest_files,
    }
    manifest_path = output_dir / 'ingest-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    log(f"  [green]✓[/green] Ingest manifest → {manifest_path}")
    log(f"           [dim]({scan.total_files_included} files — commit this to vault/[/dim])")

    # 3. File inventory (human-readable)
    inventory_lines = [
        f"# Vault Bootstrap — Ingest Manifest",
        f"",
        f"**Scan path:** {scan.scan_path}",
        f"**Scan date:** {scan.scan_date}",
        f"**Files approved for ingest:** {scan.total_files_included}",
        f"**PII patterns redacted from samples:** see per-file notes",
        f"",
        f"> This file is the permanent record of what entered your vault. "
        f"Commit it alongside your compiled wiki articles.",
        f"",
    ]
    for d in domains:
        inventory_lines.append(
            f"## {d.name} ({d.file_count} files, {d.active_count} active)"
        )
        for f in sorted(d.files, key=lambda x: x.modified_days_ago)[:20]:
            age = f"[{int(f.modified_days_ago)}d ago]"
            pii_note = " ⚠ PII" if f.pii_flagged else ""
            inventory_lines.append(f"  {age} {Path(f.path).name}{pii_note}")
        if d.file_count > 20:
            inventory_lines.append(f"  ... and {d.file_count - 20} more")
        inventory_lines.append("")

    inventory_path = output_dir / 'ingest-manifest.md'
    inventory_path.write_text('\n'.join(inventory_lines), encoding='utf-8')
    log(f"  [green]✓[/green] File inventory  → {inventory_path}")

    # 4. Schema confirmation template
    confirm_template = """# Schema Confirmation

After running the bootstrap prompt through your LLM, paste the proposed
schema below and edit to confirm, revise, or reject each domain.

## Instructions
1. Paste LLM JSON output below
2. Edit domain names, arguments, and folder mappings as needed
3. Remove any domains that don't make sense
4. Add any domains the LLM missed
5. Save this file as schema-confirmed.json
6. Run: python scanner.py --confirm schema-confirmed.json --output ./vault

## LLM Proposed Schema
[PASTE JSON HERE]
"""
    confirm_path = output_dir / 'schema-confirmation.md'
    confirm_path.write_text(confirm_template, encoding='utf-8')
    log(f"  [green]✓[/green] Schema template → {confirm_path}")


def print_summary(scan: ScanResult, domains: list[DomainCandidate]):
    """Print a summary table of discovered domains."""
    if RICH:
        table = Table(title="Discovered Domain Candidates", show_header=True)
        table.add_column("Domain", style="cyan")
        table.add_column("Files", justify="right")
        table.add_column("Active", justify="right", style="green")
        table.add_column("Archived", justify="right", style="dim")
        table.add_column("Size", justify="right")
        table.add_column("Folders")

        for d in domains:
            size_mb = d.total_size_bytes / (1024 * 1024)
            folders = ', '.join(Path(p).name for p in d.folder_paths[:2])
            table.add_row(
                d.name,
                str(d.file_count),
                str(d.active_count),
                str(d.archived_count),
                f"{size_mb:.1f}MB",
                folders,
            )
        console.print(table)
    else:
        print(f"\n{'Domain':<25} {'Files':>6} {'Active':>7} {'Archived':>9}")
        print('-' * 55)
        for d in domains:
            print(f"{d.name:<25} {d.file_count:>6} {d.active_count:>7} {d.archived_count:>9}")


# ============================================================
# SCHEMA CONFIRMATION + VAULT INIT
# ============================================================

def init_vault_from_schema(schema_path: Path, output_dir: Path):
    """
    Read a confirmed schema JSON and generate the vault folder structure.
    This is the second step after the human confirms the LLM's proposal.
    """
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    domains = schema.get('proposed_domains', [])

    vault_dir = output_dir / 'vault'
    log(f"\n[bold]Initializing vault at:[/bold] {vault_dir}")

    # Create folder structure
    folders = [
        vault_dir / 'raw' / '_inbox',
        vault_dir / 'wiki' / '_index',
        vault_dir / 'wiki' / '_mocs',
        vault_dir / 'wiki' / '_concepts',
        vault_dir / 'wiki' / '_skills',
        vault_dir / 'assets' / 'images',
        vault_dir / 'lint',
        vault_dir / 'outputs',
        vault_dir / 'templates',
    ]

    for d in domains:
        domain_id = d['id']
        folders.append(vault_dir / 'raw' / domain_id)
        folders.append(vault_dir / 'wiki' / domain_id)

    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)

    # Write seed MOCs
    for d in domains:
        domain_id = d['id']
        argument = schema.get('suggested_moc_arguments', {}).get(domain_id, '')
        moc_content = f"""---
title: {d['label']} — Map of Content
type: moc
project: {domain_id}
date: {datetime.now().strftime('%Y-%m-%d')}
status: seed
---

## The Argument
{argument if argument else '*(To be written after first compile)*'}

## Core Articles
*(Compiler populates after first compile)*

## Topic Clusters
*(Compiler populates after first compile)*

## Cross-Domain Connections
*(Compiler populates after first compile)*

## Synthesis Claims
*(Compiler populates after first compile)*

## Open Territory
*(Compiler populates after first compile)*
"""
        moc_path = vault_dir / 'wiki' / '_mocs' / f"{domain_id}-moc.md"
        moc_path.write_text(moc_content, encoding='utf-8')

    # Write seed concept articles
    for concept in schema.get('cross_domain_concepts', []):
        concept_content = f"""---
title: {concept['name'].replace('-', ' ').title()}
type: concept
tags: []
projects: {json.dumps(concept.get('appears_in', []))}
date: {datetime.now().strftime('%Y-%m-%d')}
related: []
status: seed
---

## Definition
{concept.get('description', '')}

## Why It Matters


## Appears In
{chr(10).join(f'- [[{d}-overview]]' for d in concept.get('appears_in', []))}

## Further Reading

"""
        safe_name = re.sub(r'[^a-z0-9-]', '-', concept['name'].lower())
        concept_path = vault_dir / 'wiki' / '_concepts' / f"{safe_name}.md"
        concept_path.write_text(concept_content, encoding='utf-8')

    # Write INDEX.md
    domain_lines = '\n'.join(
        f"- [[{d['id']}-moc]] — {d['argument'][:80]}..."
        for d in domains
    )
    index_content = f"""---
title: Master Index
type: index
date: {datetime.now().strftime('%Y-%m-%d')}
---

## Projects
*(Start here → read the MOC for a domain before drilling into articles)*

{domain_lines}

## All MOCs
See [[MOC-INDEX]] for the full domain orientation map.

## Cross-Project Concepts
*(Compiler populates)*

## Recent Additions
*(Compiler updates on each compilation run)*

## Suggested Next
*(Compiler populates — stub links that would most improve graph connectivity)*
"""
    (vault_dir / 'wiki' / '_index' / 'INDEX.md').write_text(index_content, encoding='utf-8')

    # Write MOC-INDEX.md — cross-domain orientation map referenced from INDEX
    moc_index_lines = '\n'.join(
        f"- [[{d['id']}-moc]] — {d.get('argument', '')[:80]}{'...' if len(d.get('argument','')) > 80 else ''}"
        for d in domains
    )
    moc_index_content = f"""---
title: MOC Index — Domain Orientation Map
type: index
date: {datetime.now().strftime('%Y-%m-%d')}
---

## Domain Maps
*(Read a MOC before drilling into domain articles)*

{moc_index_lines}

## Cross-Domain Connection Map
*(Compiler populates after first full compile)*
"""
    (vault_dir / 'wiki' / '_index' / 'MOC-INDEX.md').write_text(moc_index_content, encoding='utf-8')

    # Write schema.json into vault for reference
    schema_dest = vault_dir / 'schema.json'
    schema_dest.write_text(json.dumps(schema, indent=2), encoding='utf-8')

    # Copy ingest manifest into vault as permanent record
    manifest_src = output_dir / 'ingest-manifest.json'
    if manifest_src.exists():
        import shutil
        shutil.copy(manifest_src, vault_dir / 'ingest-manifest.json')
        log(f"  [green]✓[/green] Ingest manifest copied to vault (permanent record)")

    # Write ingestion queue — ordered list of domains to compile
    priority_order = schema.get('recommended_first_compile_order', [])
    # Fall back to domain declaration order if LLM didn't specify
    if not priority_order:
        priority_order = [d['id'] for d in domains]
    queue = priority_order

    queue_path = vault_dir / 'ingestion-queue.json'
    queue_path.write_text(json.dumps({
        'created': datetime.now().isoformat(),
        'domain_order': queue,
        'status': 'pending',
        'note': 'Run compilation chain against raw/ in this domain order'
    }, indent=2), encoding='utf-8')

    log(f"\n[bold green]Vault initialized:[/bold green]")
    log(f"  Domains:   {len(domains)}")
    log(f"  MOCs:      {len(domains)} seed files written")
    log(f"  Concepts:  {len(schema.get('cross_domain_concepts', []))} seed files written")
    log(f"  Location:  {vault_dir}")
    log(f"\n[bold]Next step:[/bold] Run the compilation chain against raw/ in ingestion-queue.json order")


# ============================================================
# CLI
# ============================================================

args_dry_run = False

def main():
    global args_dry_run

    parser = argparse.ArgumentParser(
        description='Vault Bootstrap Scanner — discovers and classifies knowledge from a folder'
    )
    parser.add_argument('--path', type=str, help='Folder to scan')
    parser.add_argument('--depth', type=int, default=4, help='Max folder depth (default: 4)')
    parser.add_argument('--output', type=str, default='./vault-bootstrap',
                        help='Output directory (default: ./vault-bootstrap)')
    parser.add_argument('--include-code', action='store_true',
                        help='Include source code files (default: docs/READMEs only)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Scan and classify without writing output or prompting')
    parser.add_argument('--confirm', type=str,
                        help='Path to confirmed schema JSON — skips scan, initializes vault')
    parser.add_argument('--json', action='store_true',
                        help='Output scan manifest as JSON to stdout')

    args = parser.parse_args()
    args_dry_run = args.dry_run

    # ── Schema confirmation mode ──
    if args.confirm:
        schema_path = Path(args.confirm)
        if not schema_path.exists():
            log(f"[red]Schema file not found: {schema_path}[/red]")
            sys.exit(1)
        output_dir = Path(args.output)
        init_vault_from_schema(schema_path, output_dir)
        return

    # ── Scan mode ──
    if not args.path:
        parser.print_help()
        sys.exit(1)

    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        log(f"[red]Path not found: {root}[/red]")
        sys.exit(1)

    output_dir = Path(args.output).expanduser().resolve()

    if RICH:
        console.print(Panel.fit(
            f"[bold cyan]Vault Bootstrap Scanner[/bold cyan]\n"
            f"Path: {root}\n"
            f"Depth: {args.depth} | Output: {output_dir}",
            border_style="cyan"
        ))

    # Run scan
    scan = scan_folder(root, max_depth=args.depth, include_code=args.include_code)

    # Classify domains
    log("\n[bold]Classifying domains...[/bold]")
    domains = classify_domains(scan)
    scan.domain_candidates = domains

    # Print summary
    print_summary(scan, domains)

    if args.json:
        print(json.dumps({
            'total_files': scan.total_files_included,
            'domains': [{'name': d.name, 'files': d.file_count} for d in domains]
        }))
        return

    if args.dry_run:
        log("\n[yellow]Dry run — no output written.[/yellow]")
        return

    # Generate bootstrap prompt
    log("\n[bold]Generating bootstrap prompt...[/bold]")
    bootstrap_prompt = generate_bootstrap_prompt(scan, domains)

    # Write output
    log("\n[bold]Writing output:[/bold]")
    write_output(scan, domains, bootstrap_prompt, output_dir)

    # Final instructions
    if RICH:
        console.print(Panel(
            "[bold]Next steps:[/bold]\n\n"
            "1. Open [cyan]vault-bootstrap/bootstrap-prompt.md[/cyan]\n"
            "2. Paste into your LLM (Claude, Llama, etc.)\n"
            "3. Copy the JSON output\n"
            "4. Edit [cyan]vault-bootstrap/schema-confirmation.md[/cyan] with the JSON\n"
            "5. Save as [cyan]vault-bootstrap/schema-confirmed.json[/cyan]\n"
            "6. Run: [bold]python scanner.py --confirm vault-bootstrap/schema-confirmed.json[/bold]\n\n"
            "The vault folder structure will be generated automatically.",
            title="Setup Complete",
            border_style="green"
        ))
    else:
        print("\nNext steps:")
        print("1. Open vault-bootstrap/bootstrap-prompt.md")
        print("2. Paste into your LLM")
        print("3. Save confirmed schema as vault-bootstrap/schema-confirmed.json")
        print("4. Run: python scanner.py --confirm vault-bootstrap/schema-confirmed.json")


if __name__ == '__main__':
    main()
