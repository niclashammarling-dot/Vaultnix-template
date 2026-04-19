# Braindex

An agent-operated knowledge vault. You bring the raw sources and strategic direction. The agent writes and maintains the wiki.

The vault is a small-world knowledge graph — high local clustering, low average path length, structured so an agent can navigate to any concept within four hops. Each compile run creates new articles and propagates changes through the neighborhood, so the vault compounds rather than just grows.

---

## How it works

```
raw/[domain]/note.md   →   compile   →   wiki/[domain]/article.md
                                    ↘   wiki/_mocs/[domain]-moc.md
                                    ↘   wiki/_concepts/concept.md
```

1. You drop raw notes, transcripts, or rough thinking into `raw/[domain]/`
2. The compiler calls an LLM, writes structured wiki articles, runs validation, commits to a review branch
3. The SESSION_OPENER reads vault state at the start of each session and surfaces the highest-value gaps to fill next

The vault is built for agents to traverse, not for humans to browse. Every structural decision — naming, linking, MOC format, concept article placement — shortens traversal paths.

---

## Quickstart

**Requirements:** Python 3.11+, Git. Ollama optional (local LLM, no API key needed).

```bash
# 1. Use this template — click "Use this template" on GitHub, then clone your copy
git clone https://github.com/your-username/your-vault
cd your-vault

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the setup wizard
python3 scripts/wizard.py
```

The wizard configures your vault identity, domains, and LLM provider, then initializes the directory structure.

**Drop your first raw source:**

```bash
echo "# My first note\n\nSomething I've been thinking about..." > raw/[domain]/first-note.md
python3 scripts/compile.py
```

**Check what was written:**

```bash
python3 scripts/status.py
```

---

## LLM providers

Braindex is local-first. Ollama runs on your machine with no API key or internet connection.

```bash
# Install Ollama: https://ollama.com
ollama pull llama3.2
ollama serve
```

Online providers (OpenAI, xAI, Anthropic) are optional — configure in `vault.config.yaml` or set environment variables.

---

## Directory structure

```
your-vault/
├── raw/                  ← you write here. agent reads. never deleted.
│   └── [domain]/
├── wiki/                 ← agent writes everything here
│   ├── [domain]/
│   ├── _mocs/            ← Maps of Content — argumentative domain maps
│   ├── _concepts/        ← cross-domain concept articles
│   └── _index/           ← INDEX.md, MOC-INDEX.md, INSPIRATION.md
├── outputs/              ← query results and session notes
├── lint/                 ← weekly health check reports
├── scripts/              ← compile.py, run_lint.py, validate.py, ...
├── Vault/                ← COMPILATION_PROMPT.md, SESSION_OPENER.md
└── vault.config.yaml     ← single source of truth for all configuration
```

---

## Scripts

| Script | Purpose |
|---|---|
| `scripts/wizard.py` | First-run setup — configures vault.config.yaml and initializes structure |
| `scripts/compile.py` | Compiles raw/ files into wiki/ articles via LLM |
| `scripts/run_lint.py` | Weekly graph health check — mechanical + LLM analysis |
| `scripts/validate.py` | Mechanical hook validation — run standalone or in CI |
| `scripts/schedule.py` | Local cron scheduler for automated compile and lint |
| `scripts/status.py` | Shows recent compile and lint run history |

```bash
python3 scripts/compile.py --dry-run   # preview without calling LLM
python3 scripts/compile.py --force     # recompile all files
python3 scripts/validate.py wiki/      # validate all wiki articles
python3 -m pytest tests/              # run test suite
```

---

## Claude Code integration

Open `Vault/COMPILATION_PROMPT.md` and paste it into a Claude Code session to compile interactively. The agent writes directly to `wiki/`, runs hook enforcement after every write, and commits at the end.

Open `Vault/SESSION_OPENER.md` at the start of each session to orient on the vault's current state and surface the highest-value stubs to fill.

---

## Weekly lint

The vault runs a weekly structural health check. Configure in `vault.config.yaml`:

- `lint.platform: github-actions` — runs via GitHub Actions on your configured schedule, commits the report back to `lint/`
- `lint.platform: local-cron` — runs via `scripts/schedule.py`
- `lint.platform: manual` — run `python3 scripts/run_lint.py` when needed

The lint check surfaces orphaned articles, isolated clusters, MOC argument drift, and cross-domain connection gaps.

---

## Philosophy

The vault is built on three principles:

**Compounding over accumulation.** A vault that grows without topology management becomes a chain — path length increases linearly and activation degrades. Every structural decision (MOC arguments, minimum link counts, concept article placement) exists to maintain graph health as the vault scales.

**Honesty, transparency, observability.** Compile reports surface what changed and what failed. Hook violations are logged with prescribed fixes. The SESSION_OPENER reads observable vault state, not cached summaries. Nothing fails silently.

**File over app.** Your knowledge lives in markdown files in your git repository. The agent is interchangeable; the files persist.

---

## License

MIT
