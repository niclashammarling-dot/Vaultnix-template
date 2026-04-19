---
title: Vault Knowledge Workflow Design
project: knowledge-work
tags: [knowledge-work/workflow, knowledge-work/architecture]
source: braindex-template
date: 2026-04-08
related: [spreading-activation, moc-as-argument, hook-enforcement, stub-as-signal]
moc: [knowledge-work-moc]
status: active
---

## Summary

The vault operates on a three-phase cycle: raw input, compilation, and session-directed work. The human provides raw sources and strategic direction; the agent compiles them into wiki articles and maintains the graph; sessions orient the next compile based on what the graph most needs. The key property is that each phase feeds the next — compilation grows the graph, the graph improves session orientation, sessions direct better raw inputs. Without this cycle completing, the vault accumulates articles but does not compound. The design goal is a system that gets more useful the more it is used, not one that merely grows larger.

## Key Concepts

- [[spreading-activation]] — compilation is where spreading activation runs; the workflow schedules and enforces it
- [[moc-as-argument]] — MOC maintenance is mandatory in every compile run; the workflow ensures MOCs stay current
- [[hook-enforcement]] — the gate between compile output and committed vault content
- [[stub-as-signal]] — stubs produced during compile are the raw material SESSION_OPENER scores
- [[agent-traversal]] — session orientation depends on the traversal quality the workflow maintains
- [[external-cognition]] — the workflow is the operational expression of the external cognition model

## Details

**Raw phase:** the human drops files into `raw/[domain]/`. Format is unconstrained — rough notes, transcripts, screenshots, PDFs. The raw directory is read-only for the agent. Nothing is deleted from raw/ after compilation; it remains a source log.

**Compile phase:**
1. For each raw file: build a prompt with the compilation instructions + selective vault context (structural dirs + same domain)
2. Call the LLM → parse FILE block output → validate each block mechanically
3. Write validated articles to `wiki/` → commit to a compile branch
4. Run spreading activation: update 3-5 neighboring articles
5. Update domain MOC and indexes
6. Auto-merge if all validations pass; leave branch open for review if not

**Selective context:** the agent receives the relevant domain + structural directories (`_mocs/`, `_concepts/`, `_index/`), not the full vault. This manages context window while focusing spreading activation. The structural directories ensure cross-domain concept articles are always available as linking targets.

**Session phase:** SESSION_OPENER reads vault state (INDEX.md, MOC-INDEX.md, recent lint), scores stubs by inbound count × cross-domain reach × MOC alignment × synthesis potential, and surfaces the top 3 high-value sessions. The human selects a direction; the agent primes the session with domain context and a specific goal.

**Honesty, transparency, observability:**
- Compile reports are written to the vault before every commit — what changed, what failed, what was skipped
- Hook violations are logged with prescribed fixes — nothing fails silently
- SESSION_OPENER reads observable vault state, not agent memory — the session orientation is reproducible from the files alone
- Run logs (logs/runs.jsonl) record every compile and lint run with status, duration, and warnings

## Connections

- [[spreading-activation]] — compilation is the mechanism that drives spreading activation; the workflow enforces the 3-5 article minimum to prevent isolated article creation
- [[hook-enforcement]] — hook enforcement is the validation gate at the end of every compile step; it determines what enters the committed vault and what requires human review
- [[moc-as-argument]] — MOC maintenance is mandatory in every compile run; a compile that creates new articles without updating their MOCs is structurally incomplete
- [[stub-as-signal]] — the stubs created during compilation are the primary output that SESSION_OPENER uses to orient the next session; the workflow produces the agenda for the next phase
- [[external-cognition]] — the three-phase cycle is the operational expression of the external cognition model: compile is the write cycle, traversal and session are the read cycle

## Open Questions

- What raw input formats consistently produce the highest-quality compiled articles? Is there a preprocessing or templating step that would improve compilation quality without adding friction to the raw phase?
- When the vault grows large enough that full-wiki context exceeds the context window, does selective context adequately preserve cross-domain connection quality, or does it systematically miss concept article opportunities?
