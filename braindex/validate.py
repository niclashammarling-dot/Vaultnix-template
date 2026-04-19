"""
validate.py — Mechanical hook validation for Braindex wiki articles.

Runs structural and graph hook checks on markdown files before they are
committed to the wiki. This is the mechanical enforcement layer — it does
not rely on LLM judgment.

Used by compile.py to validate LLM output before writing to disk.
Can also be run standalone:
    python3 scripts/validate.py wiki/domain/article.md
    python3 scripts/validate.py wiki/          # validate all files
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

WIKILINK_RE = re.compile(r'\[\[([^\]|#]+)')
FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

REQUIRED_SECTIONS = [
    "## Summary",
    "## Key Concepts",
    "## Details",
    "## Connections",
    "## Open Questions",
]

MIN_OUTBOUND_LINKS = 3


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    hook_type: str   # "structural" | "graph" | "quality"
    severity:  str   # "fail" | "warn"
    file:      str
    message:   str
    fix:       str


@dataclass
class ValidationResult:
    path:       Path
    violations: list[Violation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(v.severity == "fail" for v in self.violations)

    @property
    def hard_fails(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == "fail"]

    @property
    def warnings(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == "warn"]

    def report(self) -> str:
        if not self.violations:
            return f"  PASS  {self.path.name}"
        lines = [f"  {'FAIL' if not self.passed else 'WARN'}  {self.path.name}"]
        for v in self.violations:
            tag = "FAIL" if v.severity == "fail" else "WARN"
            lines.append(f"    HOOK {tag} [{v.hook_type}]: {v.message}")
            lines.append(f"      Fix: {v.fix}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_frontmatter(text: str, path: Path) -> list[Violation]:
    violations = []
    name = path.name
    m = FRONTMATTER_RE.match(text)
    if not m:
        violations.append(Violation(
            hook_type="structural", severity="fail", file=name,
            message="Missing or malformed frontmatter block",
            fix="Add --- frontmatter --- block at top of file",
        ))
        return violations

    fm_text = m.group(1)
    for field in ("title", "project", "date", "status"):
        if not re.search(rf'^{field}\s*:', fm_text, re.MULTILINE):
            violations.append(Violation(
                hook_type="structural", severity="fail", file=name,
                message=f"Frontmatter missing required field: {field}",
                fix=f"Add '{field}:' to frontmatter",
            ))
    if not re.search(r'^moc\s*:', fm_text, re.MULTILINE):
        violations.append(Violation(
            hook_type="structural", severity="fail", file=name,
            message="Frontmatter missing 'moc:' field",
            fix="Add 'moc: [domain-moc]' to frontmatter",
        ))
    return violations


MOC_REQUIRED_SECTIONS = [
    "## The Argument",
    "## Core Articles",
    "## Synthesis Claims",
    "## Open Territory",
]
MOC_ARGUMENT_MIN_CHARS = 80  # The Argument must be substantive, not a placeholder


def _check_sections(text: str, path: Path) -> list[Violation]:
    violations = []
    if path.parent.name == "_index":
        return violations  # index files have no fixed structure
    if path.parent.name == "_mocs":
        return _check_moc_sections(text, path)
    for section in REQUIRED_SECTIONS:
        if section not in text:
            violations.append(Violation(
                hook_type="structural", severity="fail", file=path.name,
                message=f"Missing required section: {section}",
                fix=f"Add '{section}' section with content",
            ))
    return violations


def _check_moc_sections(text: str, path: Path) -> list[Violation]:
    """MOC-specific structural checks — enforce argument, not just presence."""
    violations = []

    for section in MOC_REQUIRED_SECTIONS:
        if section not in text:
            violations.append(Violation(
                hook_type="structural", severity="fail", file=path.name,
                message=f"MOC missing required section: {section}",
                fix=f"Add '{section}' section — a MOC without this is structurally incomplete",
            ))

    # The Argument must be substantive — not a placeholder or empty
    arg_m = re.search(r'## The Argument[ \t]*\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if arg_m:
        arg_text = arg_m.group(1).strip()
        if len(arg_text) < MOC_ARGUMENT_MIN_CHARS or arg_text.startswith("*("):
            violations.append(Violation(
                hook_type="structural", severity="fail", file=path.name,
                message=(
                    f"MOC Argument is a placeholder or too short ({len(arg_text)} chars) — "
                    "a MOC that does not argue has failed"
                ),
                fix=(
                    "Write 2-3 sentences that state what this domain is about AND its "
                    "central tension or design question. Not a description — a claim."
                ),
            ))

    # Synthesis Claims must not be empty (warn, not fail — may be legitimately sparse early on)
    # Use [ \t]* not \s* to avoid consuming the blank line after the header
    sc_m = re.search(r'## Synthesis Claims[ \t]*\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if sc_m and len(sc_m.group(1).strip()) < 20:
        violations.append(Violation(
            hook_type="quality", severity="warn", file=path.name,
            message="MOC Synthesis Claims is empty — claims only visible at domain level are missing",
            fix="Add 2-4 claims that only emerge from reading the domain together, not from individual articles",
        ))

    # Open Territory must not be empty
    ot_m = re.search(r'## Open Territory[ \t]*\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if ot_m and len(ot_m.group(1).strip()) < 20:
        violations.append(Violation(
            hook_type="quality", severity="warn", file=path.name,
            message="MOC Open Territory is empty — the domain claims it has no gaps",
            fix="Add genuine gaps: what should exist here but does not yet?",
        ))

    return violations


def _check_wikilinks(text: str, path: Path) -> list[Violation]:
    violations = []
    links = WIKILINK_RE.findall(text)

    # Check link format: must be lowercase-hyphenated
    bad_format = [
        lnk for lnk in links
        if lnk != lnk.lower() or " " in lnk
    ]
    for lnk in bad_format:
        violations.append(Violation(
            hook_type="structural", severity="fail", file=path.name,
            message=f"Wikilink not lowercase-hyphenated: [[{lnk}]]",
            fix=f"Rename to [[{lnk.lower().replace(' ', '-')}]]",
        ))

    # Check minimum outbound links (skip index files)
    if path.parent.name not in ("_index",):
        unique_links = len(set(links))
        if unique_links < MIN_OUTBOUND_LINKS:
            violations.append(Violation(
                hook_type="graph", severity="fail", file=path.name,
                message=f"Only {unique_links} outbound wikilink(s) — minimum is {MIN_OUTBOUND_LINKS}",
                fix="Add more [[wikilinks]] with explanatory clauses in Connections section",
            ))

    return violations


def _check_quality(text: str, path: Path) -> list[Violation]:
    """Soft checks — warnings only, not hard fails."""
    violations = []
    if path.parent.name in ("_mocs", "_index"):
        return violations

    # Summary should not be empty
    summary_m = re.search(r'## Summary[ \t]*\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if summary_m and len(summary_m.group(1).strip()) < 50:
        violations.append(Violation(
            hook_type="quality", severity="warn", file=path.name,
            message="Summary is very short — may not make an argument",
            fix="Expand summary to 3-5 sentences that capture the argument",
        ))

    # Open Questions should not be empty
    oq_m = re.search(r'## Open Questions[ \t]*\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if oq_m and len(oq_m.group(1).strip()) < 20:
        violations.append(Violation(
            hook_type="quality", severity="warn", file=path.name,
            message="Open Questions section is empty or minimal",
            fix="Add 2-3 genuine gaps this article raises",
        ))

    return violations


# ---------------------------------------------------------------------------
# Main validation entry point
# ---------------------------------------------------------------------------

def validate_file(path: Path, effective_path: Path | None = None) -> ValidationResult:
    """
    Validate a file on disk.
    effective_path overrides path for all structural checks — use when the file
    is a temp copy but the slug determines which checks apply (e.g. _mocs/ vs _concepts/).
    """
    ep = effective_path or path
    result = ValidationResult(path=ep)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        result.violations.append(Violation(
            hook_type="structural", severity="fail", file=ep.name,
            message=f"Cannot read file: {e}",
            fix="Check file permissions",
        ))
        return result

    result.violations.extend(_check_frontmatter(text, ep))
    result.violations.extend(_check_sections(text, ep))
    result.violations.extend(_check_wikilinks(text, ep))
    result.violations.extend(_check_quality(text, ep))
    return result


def validate_content(content: str, slug: str) -> ValidationResult:
    """
    Validate in-memory content before writing to disk.
    slug is used as the effective path for all structural checks so that
    MOC files (slug contains _mocs/) get MOC-specific validation even though
    the content lives in a temp file with an unrelated parent directory.
    """
    import tempfile
    effective_path = Path(slug)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False,
        encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    result = validate_file(tmp_path, effective_path=effective_path)
    tmp_path.unlink(missing_ok=True)
    return result


def validate_directory(directory: Path) -> list[ValidationResult]:
    results = []
    for path in sorted(directory.rglob("*.md")):
        results.append(validate_file(path))
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    targets = sys.argv[1:]
    if not targets:
        print(f"Usage: python3 {sys.argv[0]} <file.md|directory> ...")
        return 1

    all_results: list[ValidationResult] = []
    for target in targets:
        p = Path(target)
        if p.is_file():
            all_results.append(validate_file(p))
        elif p.is_dir():
            all_results.extend(validate_directory(p))
        else:
            print(f"ERROR: not found: {target}")
            return 1

    fail_count = 0
    warn_count = 0
    for r in all_results:
        print(r.report())
        fail_count += len(r.hard_fails)
        warn_count += len(r.warnings)

    print(f"\n{len(all_results)} files — {fail_count} hard fails, {warn_count} warnings")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
