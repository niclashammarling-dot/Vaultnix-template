"""
tests/test_validate.py — Unit tests for validate.py mechanical checks.

Run:
    python3 -m pytest tests/
    python3 -m pytest tests/ -v
"""
from pathlib import Path

from braindex import validate as v

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _path(name: str, parent: str = "testdomain") -> Path:
    """Fake path with a controllable parent directory name."""
    return Path(f"/fake/{parent}/{name}.md")


def _moc_path(name: str = "test-moc") -> Path:
    return Path(f"/fake/_mocs/{name}.md")


def _index_path(name: str = "INDEX") -> Path:
    return Path(f"/fake/_index/{name}.md")


GOOD_FRONTMATTER = """\
---
title: Test Article
project: testdomain
tags: [testdomain/topic]
date: 2026-04-09
status: active
moc: [testdomain-moc]
---
"""

GOOD_SECTIONS = """\
## Summary

This is a test article that makes a claim about something important.

## Key Concepts

- [[concept-a]]
- [[concept-b]]

## Details

Detailed content goes here with enough substance to be meaningful.

## Connections

- [[article-one]] — explains how concept-a relates to the main argument
- [[article-two]] — provides the counterpoint that strengthens the claim
- [[article-three]] — the upstream dependency that makes this article possible

## Open Questions

- What happens when the core assumption breaks down?
- Is there a more efficient path to the same outcome?
"""

GOOD_ARTICLE = GOOD_FRONTMATTER + GOOD_SECTIONS


# ---------------------------------------------------------------------------
# Frontmatter checks
# ---------------------------------------------------------------------------

class TestFrontmatter:
    def test_passes_valid(self):
        p = _path("test")
        result = v._check_frontmatter(GOOD_ARTICLE, p)
        assert result == []

    def test_fails_missing_block(self):
        result = v._check_frontmatter("No frontmatter here\n", _path("x"))
        assert any("Missing or malformed" in viol.message for viol in result)
        assert all(viol.severity == "fail" for viol in result)

    def test_fails_missing_title(self):
        fm = GOOD_FRONTMATTER.replace("title: Test Article\n", "")
        result = v._check_frontmatter(fm + GOOD_SECTIONS, _path("x"))
        assert any("title" in viol.message for viol in result)

    def test_fails_missing_moc(self):
        fm = GOOD_FRONTMATTER.replace("moc: [testdomain-moc]\n", "")
        result = v._check_frontmatter(fm + GOOD_SECTIONS, _path("x"))
        assert any("moc" in viol.message for viol in result)

    def test_fails_missing_status(self):
        fm = GOOD_FRONTMATTER.replace("status: active\n", "")
        result = v._check_frontmatter(fm + GOOD_SECTIONS, _path("x"))
        assert any("status" in viol.message for viol in result)


# ---------------------------------------------------------------------------
# Section checks (regular articles)
# ---------------------------------------------------------------------------

class TestSections:
    def test_passes_all_sections(self):
        result = v._check_sections(GOOD_ARTICLE, _path("x"))
        assert result == []

    def test_fails_missing_summary(self):
        text = GOOD_ARTICLE.replace("## Summary\n", "## NotSummary\n")
        result = v._check_sections(text, _path("x"))
        assert any("Summary" in viol.message for viol in result)

    def test_fails_missing_connections(self):
        text = GOOD_ARTICLE.replace("## Connections\n", "")
        result = v._check_sections(text, _path("x"))
        assert any("Connections" in viol.message for viol in result)

    def test_skips_index_files(self):
        result = v._check_sections("anything", _index_path())
        assert result == []


# ---------------------------------------------------------------------------
# MOC section checks
# ---------------------------------------------------------------------------

GOOD_MOC = """\
---
title: Test — Map of Content
type: moc
project: testdomain
date: 2026-04-09
status: active
---

## The Argument

This domain is about building systems that compound over time. The central tension
is between local article quality and global graph topology — a well-written article
that is poorly connected degrades the whole system just as much as a shallow one.

## Core Articles

- [[article-one]] — the foundational article for understanding this domain

## Topic Clusters

### Mechanics
- [[article-two]] — how the core mechanism works

## Cross-Domain Connections

- [[knowledge-work-moc]] — the meta-domain governing all vault operation

## Synthesis Claims

- A domain that grows without topology management becomes a chain, not a network.

## Open Territory

- What happens when the domain exceeds 50 articles?
"""


class TestMocSections:
    def test_passes_good_moc(self):
        result = v._check_moc_sections(GOOD_MOC, _moc_path())
        hard_fails = [r for r in result if r.severity == "fail"]
        assert hard_fails == []

    def test_fails_missing_argument_section(self):
        text = GOOD_MOC.replace("## The Argument\n", "## NotArgument\n")
        result = v._check_moc_sections(text, _moc_path())
        assert any("The Argument" in viol.message for viol in result)
        assert any(viol.severity == "fail" for viol in result)

    def test_fails_placeholder_argument(self):
        text = GOOD_MOC.replace(
            "This domain is about building systems that compound over time. The central tension\n"
            "is between local article quality and global graph topology — a well-written article\n"
            "that is poorly connected degrades the whole system just as much as a shallow one.\n",
            "*(Agent writes after first compile)*\n"
        )
        result = v._check_moc_sections(text, _moc_path())
        assert any("placeholder" in viol.message.lower() or "short" in viol.message.lower()
                   for viol in result)
        assert any(viol.severity == "fail" for viol in result)

    def test_fails_short_argument(self):
        text = GOOD_MOC.replace(
            "This domain is about building systems that compound over time. The central tension\n"
            "is between local article quality and global graph topology — a well-written article\n"
            "that is poorly connected degrades the whole system just as much as a shallow one.\n",
            "Too short.\n"
        )
        result = v._check_moc_sections(text, _moc_path())
        assert any(viol.severity == "fail" for viol in result)

    def test_warns_empty_synthesis_claims(self):
        text = GOOD_MOC.replace(
            "- A domain that grows without topology management becomes a chain, not a network.\n",
            "\n"
        )
        result = v._check_moc_sections(text, _moc_path())
        assert any("Synthesis Claims" in viol.message and viol.severity == "warn"
                   for viol in result)

    def test_warns_empty_open_territory(self):
        text = GOOD_MOC.replace(
            "- What happens when the domain exceeds 50 articles?\n",
            "\n"
        )
        result = v._check_moc_sections(text, _moc_path())
        assert any("Open Territory" in viol.message and viol.severity == "warn"
                   for viol in result)

    def test_fails_missing_synthesis_claims_section(self):
        text = GOOD_MOC.replace("## Synthesis Claims\n", "")
        result = v._check_moc_sections(text, _moc_path())
        assert any("Synthesis Claims" in viol.message and viol.severity == "fail"
                   for viol in result)

    def test_fails_argument_that_is_blank_line_only(self):
        # Regression: \s* regex would eat the blank line and capture next
        # section header as content, falsely passing the length check.
        text = GOOD_MOC.replace(
            "This domain is about building systems that compound over time. The central tension\n"
            "is between local article quality and global graph topology — a well-written article\n"
            "that is poorly connected degrades the whole system just as much as a shallow one.\n",
            "\n"  # blank line only — should still be a hard fail
        )
        result = v._check_moc_sections(text, _moc_path())
        assert any(viol.severity == "fail" and "Argument" in viol.message
                   for viol in result)


# ---------------------------------------------------------------------------
# Wikilink checks
# ---------------------------------------------------------------------------

class TestWikilinks:
    def test_passes_valid_links(self):
        result = v._check_wikilinks(GOOD_ARTICLE, _path("x"))
        assert result == []

    def test_fails_uppercase_link(self):
        text = GOOD_ARTICLE.replace("[[concept-a]]", "[[ConceptA]]")
        result = v._check_wikilinks(text, _path("x"))
        assert any("ConceptA" in viol.message for viol in result)

    def test_fails_space_in_link(self):
        text = GOOD_ARTICLE.replace("[[concept-a]]", "[[concept a]]")
        result = v._check_wikilinks(text, _path("x"))
        assert any("concept a" in viol.message for viol in result)

    def test_fails_too_few_links(self):
        # Strip all but one unique wikilink — must fall below minimum of 3
        text = (GOOD_ARTICLE
                .replace("- [[concept-b]]\n", "")
                .replace("- [[article-one]] — explains how concept-a relates to the main argument\n", "")
                .replace("- [[article-two]] — provides the counterpoint that strengthens the claim\n", "")
                .replace("- [[article-three]] — the upstream dependency that makes this article possible\n", ""))
        result = v._check_wikilinks(text, _path("x"))
        assert any("minimum" in viol.message for viol in result)

    def test_skips_link_count_for_index(self):
        # Index files with few links should not fail the link count check
        result = v._check_wikilinks("[[one-link]]", _index_path())
        link_fail = [r for r in result if "minimum" in r.message]
        assert link_fail == []


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

class TestQuality:
    def test_warns_short_summary(self):
        text = GOOD_ARTICLE.replace(
            "This is a test article that makes a claim about something important.\n",
            "Too short.\n"
        )
        result = v._check_quality(text, _path("x"))
        assert any("Summary" in viol.message and viol.severity == "warn" for viol in result)

    def test_passes_adequate_summary(self):
        result = v._check_quality(GOOD_ARTICLE, _path("x"))
        summary_warns = [r for r in result if "Summary" in r.message]
        assert summary_warns == []

    def test_warns_empty_open_questions(self):
        text = GOOD_ARTICLE.replace(
            "- What happens when the core assumption breaks down?\n"
            "- Is there a more efficient path to the same outcome?\n",
            "\n"
        )
        result = v._check_quality(text, _path("x"))
        assert any("Open Questions" in viol.message and viol.severity == "warn"
                   for viol in result)


# ---------------------------------------------------------------------------
# validate_content — effective_path routing
# ---------------------------------------------------------------------------

class TestValidateContent:
    def test_moc_slug_triggers_moc_checks(self):
        # A MOC with a placeholder Argument must hard-fail even via validate_content
        bad_moc = GOOD_MOC.replace(
            "This domain is about building systems that compound over time. The central tension\n"
            "is between local article quality and global graph topology — a well-written article\n"
            "that is poorly connected degrades the whole system just as much as a shallow one.\n",
            "*(placeholder)*\n"
        )
        result = v.validate_content(bad_moc, "wiki/_mocs/test-moc.md")
        assert any(viol.severity == "fail" and "Argument" in viol.message
                   for viol in result.violations)

    def test_moc_slug_skips_regular_section_checks(self):
        # A valid MOC should not be flagged for missing ## Summary etc.
        result = v.validate_content(GOOD_MOC, "wiki/_mocs/test-moc.md")
        summary_fails = [r for r in result.violations
                         if "Summary" in r.message and r.severity == "fail"]
        assert summary_fails == []

    def test_regular_slug_runs_regular_checks(self):
        result = v.validate_content(GOOD_ARTICLE, "wiki/testdomain/test.md")
        # Should pass all checks for a valid article
        assert result.passed

    def test_result_path_is_slug(self):
        slug = "wiki/_mocs/my-domain-moc.md"
        result = v.validate_content(GOOD_MOC, slug)
        assert str(result.path) == slug


# ---------------------------------------------------------------------------
# ValidationResult helpers
# ---------------------------------------------------------------------------

class TestValidationResult:
    def test_passed_no_violations(self):
        r = v.ValidationResult(path=Path("x.md"))
        assert r.passed is True
        assert r.hard_fails == []
        assert r.warnings == []

    def test_not_passed_with_fail(self):
        r = v.ValidationResult(path=Path("x.md"))
        r.violations.append(v.Violation(
            hook_type="structural", severity="fail",
            file="x.md", message="test", fix="fix it"
        ))
        assert r.passed is False
        assert len(r.hard_fails) == 1

    def test_passed_with_only_warnings(self):
        r = v.ValidationResult(path=Path("x.md"))
        r.violations.append(v.Violation(
            hook_type="quality", severity="warn",
            file="x.md", message="test", fix="fix it"
        ))
        assert r.passed is True
        assert len(r.warnings) == 1
