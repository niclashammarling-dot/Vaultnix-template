# Claude Code — Vault Operating Parameters

## Orientation (read at session start)

Working directory is the vault: `{{VAULT_PATH}}`

### Session Start Protocol
At the beginning of every session:
1. Read `wiki/_index/INDEX.md` in full, with special attention to `## Pending Review`.
   - If any drafts exist, surface them immediately: "Pending Review contains [list of slugs]. Shall I summarize any, or do you want to review one first?"
2. Read the relevant domain MOC (`wiki/_mocs/[project]-moc.md`) before any work in that domain. Never drill into individual articles without first loading the domain argument.
3. Check `wiki/_index/INDEX.md` for `## Suggested Next` to surface high-value gaps.

Default behavior: Prioritize clearing Pending Review before new work, unless {{OWNER}} directs otherwise.

### When {{OWNER}} Says "compile" or "run compile"
- Immediately read `Vault/COMPILATION_PROMPT.md` (or the latest version).
- Execute the full compilation process exactly as specified.
- After completion, report the compile summary and ask whether to run lint.

### "What can we learn from this?" / "How can we use this?"
When asked (or when an incident, bug, or finding arises):
1. Create a `feedback_*.md` note in the appropriate `raw/[project]/` folder.
2. Evaluate structural implications: Does this warrant a hook (vault), Open Territory update (MOC), or design constraint?
3. Write the raw learning note.
4. Trigger a compile so the learning enters the permanent graph.

Every learning must compound the graph.

### Session Close
When {{OWNER}} says "wrap up", "close session", "commit and conclude", or similar:
1. Write a session note to `outputs/[project]/YYYY-MM-DD-[topic].md` using `templates/session.md`.
2. Trigger a compile so the session enters the permanent graph.

### Vault Structure

```
raw/          ← {{OWNER}} dumps source material here; gitignored; read-only for agents
outputs/      ← session notes and query results; gitignored
wiki/         ← permanent artifact; only compiled articles enter here
  [domains]/  ← one subdirectory per domain
  _mocs/      ← domain Maps of Content (argumentative, not catalogs)
  _concepts/  ← cross-project concept articles
  _index/     ← INDEX.md, MOC-INDEX.md, INSPIRATION.md
assets/images/← renamed descriptive image files
lint/         ← health check reports
templates/    ← article.md, concept.md, session.md
```

`raw/` and `outputs/` are gitignored. Only `wiki/` enters the permanent record.
A note in `raw/` that is never compiled is effectively ephemeral.

## Style

- No emojis
- No trailing summaries — {{OWNER}} can read the diff
- Domain-expert density — never explain basics
- Terse responses unless the task requires depth
- Filenames: lowercase-hyphenated only
- Always use `[[wikilinks]]` — never bare text references
