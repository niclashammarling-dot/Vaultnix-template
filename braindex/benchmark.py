"""
benchmark.py — Weekly vault quality benchmark.

Runs a fixed set of queries (stored in vault.config.yaml under
benchmark.queries — auto-generated at vault init) through the graph-walk
query engine and scores across four dimensions:

  TD  Traversal Depth     — navigated via INDEX → MOC → articles, not a direct jump
  SQ  Synthesis Quality   — answer synthesises across multiple articles, not one quote
  GH  Gap Honesty         — admits when vault lacks information; doesn't confabulate
  SU  Surprise            — surfaces a non-obvious cross-domain connection

Each query scores 0–5 per dimension (20 points max). Overall max: 20 × N queries.
Scores are logged to logs/benchmark.jsonl. Trend is printed vs. the previous run.

Usage:
    braindex benchmark              — run all queries
    braindex benchmark --dry-run    — print queries without calling LLM
    braindex benchmark --query 1    — run a single query by index
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install pyyaml")

from braindex import llm as llmlib
from braindex import logger as loglib
from braindex.vault import require_vault
from braindex.query import run_query

BENCHMARK_LOG = 'logs/benchmark.jsonl'

SCORING_PROMPT = """\
You are scoring a vault query result across four dimensions.
Be strict. The vault must earn every point.

QUERY:
{question}

TRAVERSAL PATH (files opened during navigation):
{traversal}

ANSWER:
{answer}

---

Score each dimension 0–5. Output ONLY a JSON object — no prose.

{{
  "TD": <0-5>,  // Traversal Depth: did the answer navigate INDEX→MOC→articles (5), or jump directly to articles (3), or use no structure (0)?
  "SQ": <0-5>,  // Synthesis Quality: synthesises across 3+ articles (5), 2 articles (3), quotes one (1), generic (0)
  "GH": <0-5>,  // Gap Honesty: explicitly names missing stubs/gaps (5), partial gaps noted (3), confabulates or over-claims (0)
  "SU": <0-5>,  // Surprise: non-obvious cross-domain connection (5), within-domain insight (3), expected answer (1), no insight (0)
  "reasoning": {{
    "TD": "one sentence",
    "SQ": "one sentence",
    "GH": "one sentence",
    "SU": "one sentence"
  }}
}}
"""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(vault: Path) -> dict:
    path = vault / 'vault.config.yaml'
    if not path.exists():
        raise FileNotFoundError(f'vault.config.yaml not found at {vault}')
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def get_queries(config: dict) -> list[str]:
    queries = config.get('benchmark', {}).get('queries', [])
    if not queries:
        raise SystemExit(
            'No benchmark queries found in vault.config.yaml.\n'
            'Run: braindex benchmark --generate\n'
            'Or add them manually under benchmark.queries:'
        )
    return queries


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_result(result: dict, lc, config: dict) -> dict:
    """Call LLM to score a single query result. Returns score dict."""
    traversal_str = '\n'.join(result['traversal']) if result['traversal'] else '(no traversal logged)'
    prompt = SCORING_PROMPT.format(
        question=result['question'],
        traversal=traversal_str,
        answer=result['answer'],
    )
    raw = llmlib.call(lc, prompt, max_tokens=512)

    # Extract JSON from response
    import re
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        return {'TD': 0, 'SQ': 0, 'GH': 0, 'SU': 0, 'reasoning': {}, 'score_error': raw[:200]}

    try:
        scored = json.loads(json_match.group())
        return scored
    except json.JSONDecodeError:
        return {'TD': 0, 'SQ': 0, 'GH': 0, 'SU': 0, 'reasoning': {}, 'score_error': raw[:200]}


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------

def load_previous_run(vault: Path) -> dict | None:
    log_path = vault / BENCHMARK_LOG
    if not log_path.exists():
        return None
    lines = log_path.read_text(encoding='utf-8').strip().splitlines()
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return None


def append_run(vault: Path, run: dict) -> None:
    log_path = vault / BENCHMARK_LOG
    log_path.parent.mkdir(exist_ok=True)
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(run) + '\n')


def _delta_str(current: int, previous: int | None) -> str:
    if previous is None:
        return ''
    d = current - previous
    if d > 0:
        return f'  (+{d})'
    if d < 0:
        return f'  ({d})'
    return '  (=)'


# ---------------------------------------------------------------------------
# Generate queries
# ---------------------------------------------------------------------------

def generate_queries(vault: Path, config: dict, lc) -> list[str]:
    """
    Use the LLM to generate 10 benchmark queries from vault.config.yaml domain context.
    Writes them into vault.config.yaml under benchmark.queries.
    """
    domains = config.get('domains', [])
    domain_text = '\n'.join(
        f"- {d['name']}: {d.get('description', '').strip()}"
        for d in domains
        if isinstance(d, dict)
    )

    prompt = f"""\
You are generating 10 benchmark queries for a knowledge vault.

The vault has these domains:
{domain_text}

Generate exactly 10 queries that test whether the vault's knowledge graph
is actually useful. The queries must:
- Require navigating across multiple articles to answer (not single-fact lookups)
- Cover different domains and cross-domain connections
- Include 2 adversarial queries (what the vault would need that it doesn't yet have)
- Include 2 synthesis queries (what patterns span multiple domains)
- Be stable forever — they cannot change once set

Output ONLY a JSON array of 10 strings. No preamble.
["query 1", "query 2", ...]
"""
    raw = llmlib.call(lc, prompt, max_tokens=1024)

    import re
    arr_match = re.search(r'\[[\s\S]*\]', raw)
    if not arr_match:
        raise ValueError(f'LLM did not return a JSON array. Got: {raw[:300]}')

    queries = json.loads(arr_match.group())
    if not isinstance(queries, list) or len(queries) < 5:
        raise ValueError(f'Expected list of queries, got: {queries}')

    # Write back to vault.config.yaml
    config_path = vault / 'vault.config.yaml'
    content = config_path.read_text(encoding='utf-8')

    benchmark_block = 'benchmark:\n  queries:\n' + \
        '\n'.join(f'    - "{q}"' for q in queries) + '\n'

    if 'benchmark:' in content:
        # Replace existing benchmark section
        content = re.sub(r'benchmark:.*?(?=\n\S|\Z)', benchmark_block, content, flags=re.DOTALL)
    else:
        content += '\n' + benchmark_block

    config_path.write_text(content, encoding='utf-8')
    print(f'Generated {len(queries)} benchmark queries → vault.config.yaml')
    return queries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description='Run the weekly vault quality benchmark')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print queries without calling LLM')
    parser.add_argument('--query', type=int, metavar='N',
                        help='Run only query N (1-indexed)')
    parser.add_argument('--generate', action='store_true',
                        help='Generate benchmark queries from vault config and exit')
    parser.add_argument('--no-score', action='store_true',
                        help='Run queries but skip LLM scoring pass')
    args = parser.parse_args()

    vault = require_vault()
    config = load_config(vault)
    wiki_dir = vault / 'wiki'

    if not wiki_dir.exists():
        print('ERROR: wiki/ not found. Run braindex compile first.')
        return 1

    lc = None if args.dry_run else llmlib.resolve(config)

    if args.generate:
        if args.dry_run:
            print('Cannot generate in dry-run mode.')
            return 1
        generate_queries(vault, config, lc)
        return 0

    queries = get_queries(config)

    if args.query is not None:
        idx = args.query - 1
        if idx < 0 or idx >= len(queries):
            print(f'ERROR: query index {args.query} out of range (1–{len(queries)})')
            return 1
        queries = [queries[idx]]

    if args.dry_run:
        print(f'Benchmark queries ({len(queries)} total):')
        for i, q in enumerate(queries, 1):
            print(f'  {i}. {q}')
        return 0

    prev_run = load_previous_run(vault)
    prev_total = prev_run.get('total_score') if prev_run else None
    prev_scores = prev_run.get('query_scores', []) if prev_run else []

    with loglib.RunLogger('benchmark') as log:
        print(f'\nBENCHMARK — {datetime.now().strftime("%Y-%m-%d")}')
        print('─' * 60)
        print(f'  Queries: {len(queries)}  |  Max score: {len(queries) * 20}')
        print()

        run_record: dict = {
            'date': datetime.now(timezone.utc).isoformat(),
            'query_count': len(queries),
            'query_scores': [],
            'total_score': 0,
            'max_score': len(queries) * 20,
        }

        total = 0

        for i, question in enumerate(queries, 1):
            print(f'  Q{i}: {question}')

            result = run_query(question, vault)
            q_total = 0
            scores = {}

            if not args.no_score:
                scores = score_result(result, lc, config)
                q_total = scores.get('TD', 0) + scores.get('SQ', 0) + \
                          scores.get('GH', 0) + scores.get('SU', 0)

            prev_q_total = prev_scores[i - 1].get('total', None) if i - 1 < len(prev_scores) else None

            delta = _delta_str(q_total, prev_q_total)
            print(f'  Score: {q_total}/20{delta}  '
                  f'(TD:{scores.get("TD","?")} SQ:{scores.get("SQ","?")} '
                  f'GH:{scores.get("GH","?")} SU:{scores.get("SU","?")})')
            if 'reasoning' in scores:
                for dim, reason in scores['reasoning'].items():
                    print(f'    {dim}: {reason}')
            print()

            total += q_total
            run_record['query_scores'].append({
                'question': question,
                'total': q_total,
                'TD': scores.get('TD', 0),
                'SQ': scores.get('SQ', 0),
                'GH': scores.get('GH', 0),
                'SU': scores.get('SU', 0),
                'traversal_steps': len(result['traversal']),
                'articles_loaded': result['articles_loaded'],
            })

        run_record['total_score'] = total
        delta_total = _delta_str(total, prev_total)

        print('─' * 60)
        print(f'  **Total: {total}/{len(queries) * 20}**{delta_total}')
        if prev_total is not None:
            direction = 'up' if total > prev_total else ('down' if total < prev_total else 'flat')
            print(f'  vs. previous run: {prev_total} → {total} ({direction})')
        print()

        log.set('total_score', total)
        log.set('max_score', len(queries) * 20)
        log.set('query_count', len(queries))

        if not args.no_score:
            append_run(vault, run_record)

    return 0


if __name__ == '__main__':
    sys.exit(main())
