"""
query.py — Graph-walk vault query with traversal log.

Navigates wiki/ structure the same way a benchmark agent does:
  INDEX.md → relevant MOC → domain articles → answer

Every file opened is logged. The traversal path is the evidence that the
vault's structure is actually usable — not just that the LLM knows the answer.

Usage:
    braindex query "what is X?"
    braindex query "how does Y work?" --depth 6
    braindex query "..." --no-log
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install pyyaml")

from braindex import llm as llmlib
from braindex import logger as loglib
from braindex.vault import require_vault

WIKILINK_RE = re.compile(r'\[\[([^\]|#]+?)(?:\|[^\]]*)?\]\]')
SECTION_RE  = re.compile(r'^## (.+)$', re.MULTILINE)


# ---------------------------------------------------------------------------
# Graph walker
# ---------------------------------------------------------------------------

class GraphWalker:
    """
    Navigates wiki/ by following wikilinks and matching keywords.
    Records every file opened as a traversal step.
    """

    def __init__(self, wiki_dir: Path, max_depth: int = 8) -> None:
        self.wiki_dir  = wiki_dir
        self.max_depth = max_depth
        self.traversal: list[str] = []   # ordered list of opened paths
        self._opened:   set[str]  = set()

    def open(self, rel_path: str) -> str | None:
        """Open a wiki file, log it, return content or None if missing."""
        path = self.wiki_dir.parent / rel_path
        if not path.exists():
            # Try within wiki/
            path = self.wiki_dir / rel_path
        if not path.exists():
            return None
        key = str(path.relative_to(self.wiki_dir.parent))
        if key not in self._opened:
            self._opened.add(key)
            self.traversal.append(f'[[OPEN: {key}]]')
        try:
            return path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return None

    def find_moc(self, question: str) -> tuple[str | None, str | None]:
        """
        From INDEX.md → MOC-INDEX.md, find the most relevant MOC
        by keyword matching the question against MOC arguments.
        Returns (moc_rel_path, moc_content).
        """
        index_content = self.open('wiki/_index/INDEX.md')
        if not index_content:
            return None, None

        moc_index = self.open('wiki/_index/MOC-INDEX.md')

        # Collect all MOC paths
        mocs_dir = self.wiki_dir / '_mocs'
        if not mocs_dir.exists():
            return None, None

        moc_files = list(mocs_dir.glob('*-moc.md'))
        if not moc_files:
            return None, None

        # Score MOCs by keyword overlap with the question
        q_words = set(re.findall(r'\b\w{3,}\b', question.lower()))
        best_moc_path = None
        best_score = -1

        for moc_path in moc_files:
            try:
                content = moc_path.read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue
            # Score: count question word hits in MOC text
            moc_words = set(re.findall(r'\b\w{3,}\b', content.lower()))
            score = len(q_words & moc_words)
            if score > best_score:
                best_score = score
                best_moc_path = moc_path

        if not best_moc_path:
            # Fall back: load first MOC
            best_moc_path = moc_files[0]

        rel = str(best_moc_path.relative_to(self.wiki_dir.parent))
        content = self.open(rel)
        return rel, content

    def find_articles(self, question: str, moc_content: str | None, limit: int = 5) -> list[tuple[str, str]]:
        """
        Find the most relevant domain articles.
        Strategy: extract wikilinks from the MOC, score each by keyword overlap.
        Returns list of (rel_path, content).
        """
        q_words = set(re.findall(r'\b\w{3,}\b', question.lower()))
        candidates: list[tuple[int, Path]] = []

        if moc_content:
            # Pull article slugs from MOC links
            linked_slugs = WIKILINK_RE.findall(moc_content)
        else:
            linked_slugs = []

        # Resolve slugs to file paths
        candidate_paths: list[Path] = []
        for slug in linked_slugs:
            slug_clean = slug.strip().lower().replace(' ', '-')
            # Search wiki/ for a matching file
            matches = list(self.wiki_dir.rglob(f'{slug_clean}.md'))
            candidate_paths.extend(matches)

        # If MOC gave us nothing, fall back to scanning all wiki/ articles
        if not candidate_paths:
            candidate_paths = [
                p for p in self.wiki_dir.rglob('*.md')
                if not any(part.startswith('_') for part in p.parts[len(self.wiki_dir.parts):])
            ]

        # Score candidates by keyword overlap
        seen: set[str] = set()
        for path in candidate_paths:
            if str(path) in seen:
                continue
            seen.add(str(path))
            try:
                content = path.read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue
            words = set(re.findall(r'\b\w{3,}\b', content.lower()))
            score = len(q_words & words)
            if score > 0:
                candidates.append((score, path))

        candidates.sort(key=lambda x: x[0], reverse=True)
        results = []
        for _, path in candidates[:limit]:
            rel = str(path.relative_to(self.wiki_dir.parent))
            content = self.open(rel)
            if content:
                results.append((rel, content))
        return results


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_query_prompt(
    question: str,
    index_content: str | None,
    moc_content: str | None,
    articles: list[tuple[str, str]],
    vault_name: str,
    owner: str,
) -> str:
    parts = [
        f"You are the query agent for {vault_name}, an agent-operated knowledge vault owned by {owner}.",
        "Answer using only the vault content provided. Be specific and dense.",
        "If the vault doesn't contain enough to answer well, say exactly what's missing "
        "and what stub articles would need to exist to answer fully.",
        "Never confabulate. Surface gaps honestly. Format your answer in clean markdown.",
        "",
        "---",
        "",
    ]

    if index_content:
        parts += ["## VAULT INDEX", index_content, ""]

    if moc_content:
        parts += ["## DOMAIN MAP (MOC)", moc_content, ""]

    if articles:
        parts.append("## RELEVANT ARTICLES")
        for rel_path, content in articles:
            parts += [f"### {rel_path}", content, ""]

    parts += ["---", f"QUESTION: {question}"]
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_query(question: str, vault: Path, depth: int = 8, log_traversal: bool = True) -> dict:
    """
    Execute a graph-walk query. Returns dict with answer, traversal, article count.
    Can be called programmatically (e.g. from benchmark.py).
    """
    config_path = vault / 'vault.config.yaml'
    config: dict = {}
    if config_path.exists():
        with open(config_path, encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

    vault_name = config.get('vault', {}).get('name', 'Vault')
    owner      = config.get('vault', {}).get('owner', 'the owner')

    wiki_dir = vault / 'wiki'
    walker = GraphWalker(wiki_dir, max_depth=depth)

    # Step 1: INDEX
    index_content = walker.open('wiki/_index/INDEX.md')

    # Step 2: Find best MOC
    moc_path, moc_content = walker.find_moc(question)

    # Step 3: Find relevant articles
    articles = walker.find_articles(question, moc_content, limit=5)

    # Step 4: Build prompt and call LLM
    prompt = build_query_prompt(question, index_content, moc_content, articles, vault_name, owner)

    lc = llmlib.resolve(config)
    answer = llmlib.call(lc, prompt, max_tokens=2048)

    return {
        'question':       question,
        'answer':         answer,
        'traversal':      walker.traversal,
        'articles_loaded': len(articles),
        'moc_used':       moc_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Query the vault via graph-walk')
    parser.add_argument('question', nargs='+', help='Question to ask the vault')
    parser.add_argument('--depth', type=int, default=8,
                        help='Max traversal depth (default: 8)')
    parser.add_argument('--no-log', action='store_true',
                        help='Skip writing to run log')
    parser.add_argument('--show-traversal', action='store_true',
                        help='Print the traversal path after the answer')
    args = parser.parse_args()

    question = ' '.join(args.question)
    vault = require_vault()
    wiki_dir = vault / 'wiki'

    if not wiki_dir.exists():
        print('ERROR: wiki/ not found. Run braindex compile first.')
        return 1

    def _run() -> int:
        result = run_query(question, vault, depth=args.depth)

        print(f'\nQ: {question}')
        print('─' * 60)
        print(result['answer'])

        if args.show_traversal or True:  # always show traversal — it's the evidence
            print('\n─' * 30)
            print('TRAVERSAL PATH:')
            for step in result['traversal']:
                print(f'  {step}')
            print(f'  Articles loaded: {result["articles_loaded"]}')
            if result['moc_used']:
                print(f'  MOC: {result["moc_used"]}')

        return 0

    if args.no_log:
        return _run()

    with loglib.RunLogger('query') as log:
        log.set('question', question)
        result = run_query(question, vault, depth=args.depth)
        log.set('articles_loaded', result['articles_loaded'])
        log.set('traversal_steps', len(result['traversal']))
        log.set('moc_used', result['moc_used'])

        print(f'\nQ: {question}')
        print('─' * 60)
        print(result['answer'])
        print('\n' + '─' * 30)
        print('TRAVERSAL PATH:')
        for step in result['traversal']:
            print(f'  {step}')
        print(f'  Articles loaded: {result["articles_loaded"]}')
        if result['moc_used']:
            print(f'  MOC: {result["moc_used"]}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
