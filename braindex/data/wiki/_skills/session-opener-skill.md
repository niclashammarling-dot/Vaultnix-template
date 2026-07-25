---
title: Session Opener Skill — Vault Session Orientation
project: knowledge-work
type: skill
tags: [knowledge-work/skills, knowledge-work/session]
source: derived
date: {{TODAY}}
related: [[skill-layer-architecture]], [[vault-nightly-draft-workflow]], [[agent-operated-knowledge-systems]], [[stub-as-signal]], [[session-agenda-skill]], [[within-system-contrast]]
moc: [knowledge-work-moc]
status: active
---

## Summary

Orients a new vault session. Two modes: **directed** ({{OWNER}} opens with a named project and focus — pull, commitments, domain orientation, work) and **open** (no direction — pull, commitments, read SESSION_AGENDA.md, concept prompt, wait). Scoring and agenda generation are delegated to [[session-agenda-skill]] — this skill is execution only.

---

## When to Invoke

- Start of every vault session
- CLAUDE.md session protocol Steps 1 and 2

---

## Session Modes

**Directed** — {{OWNER}} opens with a named project and specific question or area. Run Step 0 + Step 1, then Domain Orientation. Skip agenda.

**Open** — No direction given. Run full flow: Step 0 → Step 1 → Step 2 → Step 3 → wait.

**Detection rule:** named project + question or focus = directed. Named project only = brief domain orientation, ask what to work on. No project named = open.

---

## Execution — Open Session

**Step 0 — Pull vault (conditional)**
If the vault is a git repository (`git rev-parse --git-dir` succeeds) and a remote is configured, run:
```
git pull origin master
```
If the vault is not a git repo, or has no remote, skip this step entirely. A failed pull on a non-repo vault should not disorient the session — proceed directly to Step 1.

**Step 1 — Pending Commitments (all sessions)**
Read lines 7–15 of `wiki/_index/INDEX.md`. Surface each entry under `## Pending Commitments` — oldest first, max 3:
> "You committed to [[slug]] on [date]. Completed, carry forward, or drop?"
- Completed → remove entry, note in session audit
- Carry forward → leave unchanged
- Drop → remove entry, note reason in session audit

**Wiring constraint — opener-suppressed commitments:** A commitment whose payload requires opener suppression (e.g. a baseline measurement that must run before the opener reads any state) is structurally incompatible with this step. The opener IS the channel that surfaces it; any session that learns about it here has already invalidated the measurement condition. The correct disposition: spawn a named-task session (opener-skip fires automatically), execute the task there, and strike the commitment when the result lands. The `{what completing it requires}` field in the INDEX.md commitment line should state "requires opener-suppressed session" explicitly — this is the only signal that distinguishes a normal carry-forward from one that must be spawned. Without it, the next opener surfaces it as a normal work item and the structural conflict recurs.

Do not proceed to Step 2 until all surfaced commitments have a response.

**Step 2 — Regenerate SESSION_AGENDA.md**
Run [[session-agenda-skill]] unconditionally. Do not read the existing file first and do not check the SHA before deciding — the cache path is retired as an open-time decision gate.

**Why unconditional:** the SHA-sentinel architecture breaks at multi-session-per-day cadence — same-day writes can arrive after the last agenda generation without triggering a mismatch. The correction overhead of one stale-agenda opener exceeds the cost of one regeneration. The economy the sentinel provided no longer holds at realistic use cadence.

**SHA sentinel (mid-session use only):** the `generated_at_commit:` field remains in the output format. Use it only to detect drift *during* a session — if vault changes land after the opener, the sentinel flags that the agenda is now stale. It is not an open-time skip-gate.

Additionally:
- If `(hand-generated)` marker is present: note this to {{OWNER}} — content is valid but may not reflect the latest compile.

Present the regenerated agenda. Do not editorialize — the file is the opener output.

**Step 3 — Concept prompt**
Ask:
> "Before we dive in — any observations from recent work that haven't been named yet?"

The pattern most likely to surface here is [[within-system-contrast]]: two components in the same system behaving differently for structural reasons. If the observation names a divergence between components in the same project, that is a concept candidate.

This step is also the primary extraction mechanism for cross-article emergent concepts — see [[cross-article-concept-extraction]]. Patterns that live in the structural relationship *between* articles (visible only when two articles are held simultaneously) cannot be detected by the nightly agent's single-article filter. The concept prompt is the correct and sufficient mechanism for surfacing them.

Wait for response. If {{OWNER}} surfaces a concept candidate, treat it as the session agenda item. If not, ask {{OWNER}} to pick from the agenda or propose a different direction.

Never begin execution without direction.

**Once direction is picked:** write the selected item to `## Pending Commitments` in INDEX.md:
```
- [[item-or-slug]] — picked YYYY-MM-DD — [one line: what completing it requires]
```

---

## Execution — Directed Session

**Step 0** — Pull vault (same as above).

**Step 1** — Pending Commitments (same as above). Runs in directed sessions too — commitments are accountability items, not mode-conditional.

**Domain Orientation:**

1. Read `wiki/_mocs/[project]-moc.md` if it exists — extract current argument, active synthesis claims, Open Territory gaps. If no MOC exists, skip.
2. Search `raw/[project]/` for session notes; read the 2–3 most recent matching files. Extract decisions made (still load-bearing) and open threads (deferred or unresolved).
3. Brief {{OWNER}} in 4–6 lines:
   - Current state of the domain
   - Load-bearing decisions from recent sessions
   - Open threads or unresolved questions
   - Highest-value gap (MOC Open Territory or open threads)

Then proceed directly to the named work. Do not score stubs. Do not surface unrelated work.
