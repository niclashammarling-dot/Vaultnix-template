#!/usr/bin/env python3
"""
sync_scaffold.py — drift detector and sync tool for Vaultnix1.0.

Compares the dev vault (Vaultnix1.0/ root) against the shipped scaffold
(braindex/data/) using scaffold_manifest.yaml as authority.

Four manifest categories, each with a different check:
  synced          — content compared as render(dev) vs scaffold; drift = error
  adapted         — existence check only; content divergence is expected/noted
  scaffold_native — must exist in scaffold; must NOT exist in dev vault
  dev_only        — must exist in dev vault; must NOT exist in scaffold
  independent     — must exist in BOTH trees; content comparison skipped
                    (scaffold seeds a stub; dev vault is the live evolved copy)

Silence in the manifest means unclassified, not independently managed. A file
present in both trees with no manifest entry is a schema gap.

Transforms invariant: for files in `synced` with a `transforms` entry, the
comparison is render(dev_file) vs the scaffold copy — not the raw dev file.
Post-transform divergence from dev content is expected and correct. Transforms
raise on zero-match and on >1-match so a drifted source heading breaks the sync
run instead of silently shipping un-localized content to users.

Usage:
    python sync_scaffold.py           # report drift, no writes
    python sync_scaffold.py --sync    # copy (rendered) synced files dev → scaffold
    python sync_scaffold.py --links   # also validate wikilinks in both trees
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml required: pip install pyyaml")

REPO_ROOT = Path(__file__).parent
DEV_ROOT  = REPO_ROOT
SCAFFOLD  = REPO_ROOT / "braindex" / "data"
MANIFEST  = REPO_ROOT / "scaffold_manifest.yaml"


def _dev(rel: str) -> Path:
    return DEV_ROOT / rel


def _scaffold(rel: str) -> Path:
    return SCAFFOLD / rel


# ── transforms ────────────────────────────────────────────────────────────────

def apply_transforms(content: str, rules: list[dict], rel: str) -> str:
    """Apply ordered find/replace rules; raise on zero or ambiguous matches."""
    for rule in rules:
        find, replace = rule["find"], rule["replace"]
        count = content.count(find)
        if count == 0:
            raise ValueError(
                f"Transform no-match in '{rel}': find string not found.\n"
                f"  Expected: {find!r}\n"
                f"  Source heading may have changed; update scaffold_manifest.yaml."
            )
        if count > 1:
            raise ValueError(
                f"Transform ambiguous in '{rel}': find matched {count} times "
                f"(expected exactly 1).\n"
                f"  Pattern: {find!r}"
            )
        content = content.replace(find, replace, 1)
    return content


def render(path: Path, rules: list[dict], rel: str) -> bytes:
    """Read dev file and apply transforms; return rendered bytes."""
    content = path.read_text(encoding="utf-8")
    if rules:
        content = apply_transforms(content, rules, rel)
    return content.encode("utf-8")


# ── category checks ───────────────────────────────────────────────────────────

def check_synced(
    paths: list[str], transform_map: dict[str, list[dict]], sync: bool
) -> list[tuple[str, str]]:
    results = []
    for rel in paths:
        d, s = _dev(rel), _scaffold(rel)
        rules = transform_map.get(rel, [])

        if not d.exists():
            results.append(("ERROR", f"missing from dev vault: {rel}"))
            continue

        try:
            rendered = render(d, rules, rel)
        except ValueError as exc:
            results.append(("ERROR", str(exc)))
            continue

        if not s.exists():
            if sync:
                s.parent.mkdir(parents=True, exist_ok=True)
                s.write_bytes(rendered)
                results.append(("SYNCED", rel))
            else:
                results.append(("DRIFT", f"missing from scaffold: {rel}"))
        elif s.read_bytes() != rendered:
            if sync:
                s.write_bytes(rendered)
                results.append(("SYNCED", rel))
            else:
                results.append(("DRIFT", f"differs: {rel}"))

    return results


def check_adapted(paths: list[str]) -> list[tuple[str, str]]:
    results = []
    for rel in paths:
        d, s = _dev(rel), _scaffold(rel)
        if not d.exists():
            results.append(("ERROR", f"missing from dev vault: {rel}"))
        elif not s.exists():
            results.append(("ERROR", f"missing from scaffold: {rel}"))
        elif d.read_bytes() == s.read_bytes():
            results.append(("WARN", f"adapted file identical in both trees — may no longer need adapted status: {rel}"))
        else:
            results.append(("ADAPTED", f"trees intentionally differ — review manually: {rel}"))
    return results


def check_scaffold_native(paths: list[str]) -> list[tuple[str, str]]:
    results = []
    for rel in paths:
        s, d = _scaffold(rel), _dev(rel)
        if not s.exists():
            results.append(("ERROR", f"missing from scaffold: {rel}"))
        if d.exists():
            results.append(("ERROR", f"scaffold-native file in dev vault — wrong tree: {rel}"))
    return results


def check_dev_only(paths: list[str]) -> list[tuple[str, str]]:
    results = []
    for rel in paths:
        d, s = _dev(rel), _scaffold(rel)
        if not d.exists():
            results.append(("ERROR", f"missing from dev vault: {rel}"))
        if s.exists():
            results.append(("ERROR", f"dev-only file in scaffold — wrong tree: {rel}"))
    return results


def check_independent(paths: list[str]) -> list[tuple[str, str]]:
    """Existence check only — content drift is expected and not reported."""
    results = []
    for rel in paths:
        d, s = _dev(rel), _scaffold(rel)
        if not d.exists():
            results.append(("ERROR", f"missing from dev vault: {rel}"))
        if not s.exists():
            results.append(("ERROR", f"missing from scaffold: {rel}"))
    return results


# ── wikilink validation ───────────────────────────────────────────────────────

_WIKILINK    = re.compile(r'\[\[([^\]|#\n]+?)(?:[|#][^\]\n]*)?\]\]')
_FENCE_START = re.compile(r'^```')
_INLINE_CODE = re.compile(r'`[^`\n]+?`')


def _strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans to avoid false-positive wikilink hits."""
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE_START.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(_INLINE_CODE.sub('', line))
    return '\n'.join(lines)


def _slugs_in(root: Path) -> set[str]:
    return {p.stem for p in root.rglob("*.md")}


def validate_links(wiki_root: Path, label: str) -> list[tuple[str, str]]:
    slugs = _slugs_in(wiki_root)
    results = []
    for md in sorted(wiki_root.rglob("*.md")):
        raw = md.read_text(encoding="utf-8", errors="replace")
        text = _strip_code(raw)
        for m in _WIKILINK.finditer(text):
            link = m.group(1).strip()
            slug = Path(link).stem
            if slug not in slugs:
                rel = md.relative_to(wiki_root)
                results.append(("DANGLING", f"[{label}] {rel}  →  [[{link}]]"))
    return results


# ── output ────────────────────────────────────────────────────────────────────

_W = 8


def _print(tag: str, msg: str) -> None:
    print(f"  {tag:<{_W}}  {msg}")


def _section(title: str) -> None:
    print(f"\n── {title} {'─' * max(0, 52 - len(title))}")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sync",  action="store_true", help="copy rendered synced files dev → scaffold")
    parser.add_argument("--links", action="store_true", help="validate wikilinks in both trees")
    args = parser.parse_args()

    if not MANIFEST.exists():
        sys.exit(f"Manifest not found: {MANIFEST}")

    with open(MANIFEST) as f:
        manifest = yaml.safe_load(f)

    transform_map: dict[str, list[dict]] = manifest.get("transforms", {}) or {}

    error_count = 0
    drift_count = 0

    def tally(results: list[tuple[str, str]]) -> None:
        nonlocal error_count, drift_count
        for tag, msg in results:
            _print(tag, msg)
            if tag == "ERROR":
                error_count += 1
            elif tag in ("DRIFT", "DANGLING"):
                drift_count += 1

    _section("synced")
    tally(check_synced(manifest.get("synced", []), transform_map, sync=args.sync))

    _section("adapted")
    tally(check_adapted(manifest.get("adapted", [])))

    _section("scaffold_native")
    tally(check_scaffold_native(manifest.get("scaffold_native", [])))

    _section("dev_only")
    tally(check_dev_only(manifest.get("dev_only", [])))

    _section("independent")
    tally(check_independent(manifest.get("independent", [])))

    if args.links:
        _section("wikilinks: dev vault wiki/")
        tally(validate_links(DEV_ROOT / "wiki", "dev"))

        _section("wikilinks: scaffold wiki/")
        tally(validate_links(SCAFFOLD / "wiki", "scaffold"))

    total = error_count + drift_count
    synced_note = " (run with --sync to apply)" if drift_count and not args.sync else ""
    print(f"\n{'OK — no drift or errors' if total == 0 else f'{error_count} error(s), {drift_count} drift(s){synced_note}'}")
    return 1 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
