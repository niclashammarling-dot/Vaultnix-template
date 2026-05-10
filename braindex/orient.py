"""
orient.py — Vault orientation: surface highest-value stub gaps.

Reads wiki/ mechanically — no LLM. Extracts all [[wikilinks]], identifies
which targets don't exist (stubs), scores each by graph topology, and
surfaces the top candidates to fill next.

Scoring dimensions (each 1–10, total out of 40):
  Inbound link count   — how many articles reference this stub
  Cross-domain reach   — stub appears in articles from multiple domains
  MOC alignment        — any MOC's ## Open Territory mentions this slug
  Synthesis potential  — stub appears in both a MOC and ≥2 domain articles

Usage:
    braindex orient
    braindex orient --top 5
    braindex orient --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

from braindex import logger as loglib
from braindex.vault import require_vault

WIKILINK_RE = re.compile(r'\[\[([^\]|#]+?)(?:\|[^\]]*)?\]\]')
OPEN_TERRITORY_RE = re.compile(
    r'## Open Territory\s*\n(.*?)(?=\n## |\Z)', re.DOTALL
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StubScore:
    slug: str
    inbound_links: int = 0
    inbound_articles: list[str] = field(default_factory=list)
    domains: set = field(default_factory=set)
    moc_aligned: bool = False
    moc_sources: list[str] = field(default_factory=list)

    # Computed scores (1–10 each)
    score_inbound: int = 0
    score_cross_domain: int = 0
    score_moc: int = 0
    score_synthesis: int = 0

    @property
    def total(self) -> int:
        return self.score_inbound + self.score_cross_domain + self.score_moc + self.score_synthesis

    def to_dict(self) -> dict:
        d = asdict(self)
        d['domains'] = sorted(self.domains)
        d['total'] = self.total
        return d


# ---------------------------------------------------------------------------
# Wiki graph extraction
# ---------------------------------------------------------------------------

def _slug_from_path(path: Path, wiki_dir: Path) -> str:
    """Return the wikilink slug for a given wiki file path."""
    return path.stem  # filename without extension


def _domain_from_path(path: Path, wiki_dir: Path) -> str:
    """Infer domain from file location within wiki/."""
    try:
        rel = path.relative_to(wiki_dir)
        parts = rel.parts
        # _mocs, _concepts, _index, _skills are structural — use their name
        if parts[0].startswith('_'):
            return parts[0]
        return parts[0]
    except ValueError:
        return 'unknown'


def _is_moc(path: Path) -> bool:
    return '_mocs' in path.parts or path.stem.endswith('-moc')


def extract_graph(wiki_dir: Path) -> tuple[
    set[str],                    # existing slugs
    dict[str, list[str]],        # slug → list of referencing article slugs
    dict[str, str],              # slug → domain
    dict[str, str],              # slug → open territory text from MOCs
]:
    """
    Walk wiki/ and build the link graph.
    Returns (existing_slugs, inbound_map, slug_domain, moc_open_territory).
    """
    existing_slugs: set[str] = set()
    slug_domain: dict[str, str] = {}
    inbound_map: dict[str, list[str]] = defaultdict(list)
    moc_open_territory: dict[str, str] = {}  # moc_slug → open territory text

    all_files = list(wiki_dir.rglob('*.md'))

    # First pass: collect existing slugs and domains
    for path in all_files:
        slug = _slug_from_path(path, wiki_dir)
        domain = _domain_from_path(path, wiki_dir)
        existing_slugs.add(slug)
        slug_domain[slug] = domain

    # Second pass: extract links and MOC open territory
    for path in all_files:
        source_slug = _slug_from_path(path, wiki_dir)
        try:
            content = path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue

        # Extract all wikilinks
        links = WIKILINK_RE.findall(content)
        for link in links:
            target = link.strip().lower().replace(' ', '-')
            inbound_map[target].append(source_slug)

        # Extract open territory from MOCs
        if _is_moc(path):
            m = OPEN_TERRITORY_RE.search(content)
            if m:
                moc_open_territory[source_slug] = m.group(1).strip()

    return existing_slugs, inbound_map, slug_domain, moc_open_territory


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_inbound(count: int) -> int:
    """Score 1–10 based on inbound link count."""
    if count == 0:
        return 0
    if count == 1:
        return 2
    if count == 2:
        return 4
    if count <= 4:
        return 6
    if count <= 7:
        return 8
    return 10


def _score_cross_domain(domains: set) -> int:
    """Score 1–10 based on number of distinct domains referencing this stub."""
    n = len(domains)
    if n <= 1:
        return 2
    if n == 2:
        return 5
    if n == 3:
        return 7
    return 10


def _score_moc(moc_aligned: bool) -> int:
    return 8 if moc_aligned else 0


def _score_synthesis(moc_aligned: bool, inbound: int, domain_count: int) -> int:
    """
    Synthesis potential: stub is in both a MOC's Open Territory AND
    referenced from ≥2 articles across ≥2 domains.
    """
    if moc_aligned and inbound >= 2 and domain_count >= 2:
        return 10
    if moc_aligned and inbound >= 2:
        return 6
    if inbound >= 3 and domain_count >= 2:
        return 4
    return 0


def compute_scores(
    existing_slugs: set[str],
    inbound_map: dict[str, list[str]],
    slug_domain: dict[str, str],
    moc_open_territory: dict[str, str],
) -> list[StubScore]:
    """
    Identify stubs (links with no target file) and score each.
    Returns list sorted by total score descending.
    """
    stubs: dict[str, StubScore] = {}

    for target_slug, referencing_slugs in inbound_map.items():
        if target_slug in existing_slugs:
            continue  # not a stub

        # Determine which domains reference this stub
        domains = set()
        for ref_slug in referencing_slugs:
            d = slug_domain.get(ref_slug, 'unknown')
            # Normalise structural prefixes — _mocs counts as the domain of the MOC
            domains.add(d)

        # Check MOC open territory
        moc_aligned = False
        moc_sources = []
        for moc_slug, territory_text in moc_open_territory.items():
            if target_slug in territory_text.lower() or \
               target_slug.replace('-', ' ') in territory_text.lower():
                moc_aligned = True
                moc_sources.append(moc_slug)

        stub = StubScore(
            slug=target_slug,
            inbound_links=len(referencing_slugs),
            inbound_articles=sorted(set(referencing_slugs)),
            domains=domains,
            moc_aligned=moc_aligned,
            moc_sources=moc_sources,
        )

        stub.score_inbound = _score_inbound(stub.inbound_links)
        stub.score_cross_domain = _score_cross_domain(domains)
        stub.score_moc = _score_moc(moc_aligned)
        stub.score_synthesis = _score_synthesis(moc_aligned, stub.inbound_links, len(domains))

        stubs[target_slug] = stub

    return sorted(stubs.values(), key=lambda s: s.total, reverse=True)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _fmt_stub(stub: StubScore, rank: int) -> str:
    domains_str = ', '.join(sorted(stub.domains)) if stub.domains else 'unknown'
    moc_note = f'  MOC: {", ".join(stub.moc_sources)}' if stub.moc_sources else ''
    refs_preview = ', '.join(stub.inbound_articles[:4])
    if len(stub.inbound_articles) > 4:
        refs_preview += f', +{len(stub.inbound_articles) - 4} more'
    lines = [
        f'  {rank}. [[{stub.slug}]] — {stub.total}/40',
        f'     Inbound: {stub.inbound_links} ({stub.score_inbound}/10)  '
        f'Cross-domain: {len(stub.domains)} ({stub.score_cross_domain}/10)  '
        f'MOC: {stub.score_moc}/10  Synthesis: {stub.score_synthesis}/10',
        f'     Domains: {domains_str}',
        f'     Referenced from: {refs_preview}',
    ]
    if moc_note:
        lines.append(moc_note)
    return '\n'.join(lines)


def print_orient(ranked: list[StubScore], top: int, wiki_dir: Path, total_articles: int) -> None:
    stub_count = len(ranked)
    high = [s for s in ranked if s.total >= 20]
    mid  = [s for s in ranked if 12 <= s.total < 20]
    low  = [s for s in ranked if s.total < 12]

    print(f'\nORIENT — {wiki_dir.parent.name}')
    print('─' * 48)
    print(f'  Wiki articles: {total_articles}  |  Active stubs: {stub_count}  '
          f'({len(high)} high / {len(mid)} mid / {len(low)} low)')
    print()

    if not ranked:
        print('  No stubs found. Add raw/ sources and run compile to generate graph gaps.')
        print('  (Every article should link to ≥2 non-existent articles.)')
        return

    shown = ranked[:top]
    print(f'  TOP {len(shown)} STUBS BY SCORE')
    print('─' * 48)
    for i, stub in enumerate(shown, 1):
        print(_fmt_stub(stub, i))
        print()

    if stub_count > top:
        print(f'  ... and {stub_count - top} more stubs (run with --top N to see more)')


def load_nominations(vault: Path) -> list[dict]:
    """Load query-nominated stubs from vault/data/query_nominations.json."""
    path = vault / 'data' / 'query_nominations.json'
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return []


def print_nominations(nominations: list[dict]) -> None:
    if not nominations:
        return
    ranked = sorted(nominations, key=lambda x: x['count'], reverse=True)
    print()
    print('  QUERY-NOMINATED STUBS')
    print('─' * 48)
    for entry in ranked:
        slug = entry['slug']
        count = entry['count']
        first = entry.get('first_seen', '?')
        print(f'  [[{slug}]]  ×{count}  (first seen: {first})')
        for q in entry['nominated_by'][:2]:
            q_short = (q[:60] + '…') if len(q) > 60 else q
            print(f'    ← "{q_short}"')
        if len(entry['nominated_by']) > 2:
            print(f'    ← … and {len(entry["nominated_by"]) - 2} more questions')
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description='Surface highest-value stub gaps in the vault')
    parser.add_argument('--top', type=int, default=3,
                        help='Number of top stubs to display (default: 3)')
    parser.add_argument('--json', action='store_true',
                        help='Output full ranked stub list as JSON')
    parser.add_argument('--min-score', type=int, default=0,
                        help='Only show stubs at or above this total score')
    args = parser.parse_args()

    vault = require_vault()
    wiki_dir = vault / 'wiki'

    if not wiki_dir.exists():
        print('ERROR: wiki/ directory not found. Run braindex compile first.')
        return 1

    with loglib.RunLogger('orient') as log:
        existing, inbound, slug_domain, moc_territory = extract_graph(wiki_dir)
        ranked = compute_scores(existing, inbound, slug_domain, moc_territory)

        if args.min_score > 0:
            ranked = [s for s in ranked if s.total >= args.min_score]

        total_articles = len(existing)
        log.set('wiki_articles', total_articles)
        log.set('stubs_found', len(ranked))
        log.set('top_stub', ranked[0].slug if ranked else None)
        log.set('top_score', ranked[0].total if ranked else 0)

        if args.json:
            print(json.dumps([s.to_dict() for s in ranked], indent=2, default=list))
            return 0

        print_orient(ranked, args.top, wiki_dir, total_articles)
        nominations = load_nominations(vault)
        print_nominations(nominations)
        return 0


if __name__ == '__main__':
    sys.exit(main())
