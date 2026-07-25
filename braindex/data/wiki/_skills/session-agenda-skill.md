---
title: Session Agenda Skill — SESSION_AGENDA.md Generation
project: knowledge-work
type: skill
tags: [knowledge-work/skills, knowledge-work/session]
source: derived
date: {{TODAY}}
related: [[session-opener-skill]], [[vault-nightly-draft-workflow]], [[stub-as-signal]]
moc: [knowledge-work-moc]
status: active
---

## Summary

Generates `wiki/_index/SESSION_AGENDA.md` for session-start consumption. Called by the nightly agent after draft compilation, and on-demand when SESSION_AGENDA.md is stale or missing. Output ceiling: 25 lines. All scoring and data collection happens here — the session opener is a reader, not a generator.

---

## When to Invoke

- Nightly agent: after completing draft compilation, before git commit
- On demand: {{OWNER}} says "regenerate session agenda", or the session opener detects a stale or missing SESSION_AGENDA.md

---

## Execution

### Step 1 — Vault state

```bash
# Article count
grep -c "^\- \[\[" wiki/_index/INDEX.md

# Pending Commitments and Pending Review (lines 7–20)
# Read wiki/_index/INDEX.md offset=7 limit=13
```

Extract:
- Article count (integer)
- Pending Commitments: list entries or "none"
- Pending Review: status line — "empty — last cleared YYYY-MM-DD [[slug]]" or "N items — [[slug1]], ..."

### Step 2 — Open ideas

```bash
ls raw/_inbox/ideas/
# Read each .md file; note status field
```

Collect all files where `status: open`. Exclude `status: implemented` and `status: discarded`. `compiled: true` alone does not suppress. Sort by date ascending. Take top 2. If the ideas folder does not exist or is empty, omit the Ideas section from output.

### Step 3 — Score top stub

**3a — Get stub candidates**
Read the most recent lint report in `lint/` (offset=1, limit=100). Extract all stub links listed. If no lint report exists yet, read `wiki/_index/INDEX.md` — `## Suggested Next` section — and use those entries as candidates instead.

**3b — Filter compiled stubs**
For each candidate, check if the file exists:
```bash
ls wiki/_concepts/[slug].md   # cross-domain concepts
ls wiki/[domain]/[slug].md    # domain articles
```
Reject any candidate where the file exists — the lint report may be stale.

Also reject any candidate whose slug appears as a confirmed ghost:
```bash
grep "^| [slug] " lint/confirmed-ghosts.md
```
If the command returns any output, reject — confirmed-ghosts.md maps working-name slugs to their canonical compiled articles. Consult this file before scoring, not after; a ghost reaching the scoring step is a filter failure. Note that the lint report itself will already annotate confirmed ghosts if the report postdates confirmed-ghosts.md — this filter catches the case where the lint report predates the quarantine file.

Also reject any candidate that appears as "NEW" in INDEX.md Recent Additions with a date after the lint report date. Read INDEX.md with `offset=1 limit=80` — this covers 2–3 recent compile entries and is sufficient; do not read the full file.

**3c — Score remaining candidates**
Four dimensions, 1–10 each, sum to 40:

| Dimension | Measure |
|---|---|
| Inbound link count | Files referencing `[[slug]]` across wiki/ |
| Cross-domain reach | Distinct project MOCs the stub appears in |
| MOC alignment | Listed under `## Open Territory` in any MOC |
| Synthesis potential | Would filling this enable a new MOC synthesis claim |

Select the top scorer. If top score is below 20, note this in the output.

**Benchmark-tuned weighting:** if a benchmark run exists in `lint/benchmark/`, check the most recent score. If Surprise (SU) is the weakest dimension, weight cross-domain reach ×1.5. If Synthesis (SY) is weakest, weight synthesis potential ×1.5. If no benchmark run exists, use equal weights.

**3e — Domain allocation check (runs after top scorer is selected)**
Read the two most recent concept entries in `wiki/_index/CONCEPT-INDEX.md` (sorted by date descending — the last two `date:` frontmatter dates). Extract the filing domain from each entry's file path (`wiki/domains/[domain]/` → domain; `wiki/_concepts/` → cross-domain, check the article's `project:` frontmatter). If both are `knowledge-work` or `vault`, apply the allocation rule: override the top scorer with the highest-scoring candidate whose filing domain is neither `knowledge-work` nor `vault`. If no such candidate exists in the current lint report, proceed with the top scorer and note "allocation rule: no non-KW/vault candidate above threshold."

**Rule text (adopted 2026-07-25, plain filing-domain version):** After 2 consecutive concept compiles filed under `knowledge-work` or `vault` domain, the next compile slot goes to the top-scoring candidate from any other domain.

**Amendment pending (file in a disinterested session):** Whether a concept whose majority of confirmed instances are non-KW/vault should be exempt from triggering the consecutive-KW condition — i.e., cross-domain credit should count against the rule's trigger. Not decided 2026-07-25 because no live candidate was disinterested at that session. Decide and encode this clause when no candidate benefits from the ruling.

### Step 4 — Vault improvement candidate

Read `wiki/_mocs/knowledge-work-moc.md` — extract the first actionable item from `## Open Territory` that is not struck through and not already a committed stub. Prefer items that reduce friction in existing workflows over net-new infrastructure.

### Step 5 — Capture HEAD sha

```bash
git rev-parse HEAD
```

Store the output as `{current_sha}` for use in the `generated_at_commit:` field below.

### Step 6 — Write SESSION_AGENDA.md

Write to `wiki/_index/SESSION_AGENDA.md`. Hard ceiling: 25 lines. If content would exceed 25 lines, truncate ideas to 1, drop vault improvement rationale to one clause, and shorten stub rationale to one clause.

---

## Output Format

```
# Session Agenda — YYYY-MM-DD
Generated: YYYY-MM-DD HH:MM
generated_at_commit: {output of `git rev-parse HEAD`}
Vault state: N articles | Pending Review: {status line}
Pending Commitments: {none} OR:
  - [[slug]] — picked YYYY-MM-DD — {one line}

## Ideas ({n} open)
1. {title} — {date}
   → {one line: what acting on this produces}
2. {title} — {date}
   → {one line}

## Vault Improvement
{label}
→ {one line: what friction it resolves or capability it unlocks}

## Top Stub (per lint {lint-report-date})
[[slug]] — {score}/40 — {domains}
→ {one line: why it matters now}
```

Followed by nothing. Any concept prompt or open question surfacing happens live at session open, not pre-generated.

---

## Commit Scope

SESSION_AGENDA.md is a generated artifact in `wiki/_index/`. It is committed by the nightly agent in the same commit as the draft article. Commit with `git add wiki/_index/SESSION_AGENDA.md` — do not use `git add -A` unless a full compile is also running.

---

## Connections

- [[vault-nightly-draft-workflow]] — the nightly agent calls this skill after draft compilation; SESSION_AGENDA.md is committed in the same nightly commit as the draft article
- [[intent-carrying-artifact]] — SESSION_AGENDA.md is an intent-carrying artifact: the nightly agent encodes vault state and scoring decisions so the session opener can act on them without regenerating the traversal; the inter-session gap is the runtime boundary
- [[stub-as-signal]] — the scoring logic in Step 3 is the operational implementation of stub-as-signal: inbound link count and cross-domain reach are the mechanical measures of graph demand

## Open Questions

- Should the vault improvement candidate be scored like stubs (actionability field) or is one curated pick sufficient? The current design curates — if the knowledge-work-moc Open Territory grows past 10 items, a scoring pass may be warranted.
- If the nightly agent produces no derivable stub candidates (all stubs are non-derivable that night), should SESSION_AGENDA.md still be written with a "no stub tonight" line, or skipped entirely? Current assumption: always write the file — a missing file signals a run failure, not an empty queue.
