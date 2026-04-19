---
title: Hook Enforcement
project: knowledge-work
tags: [knowledge-work/validation, knowledge-work/architecture]
source: braindex-template
date: 2026-04-08
related: [stub-as-signal, agent-traversal, vault-knowledge-workflow-design]
moc: [knowledge-work-moc]
status: active
---

## Summary

The most common failure mode in automated knowledge compilation is silent structural drift — articles accumulate without adequate linking, summaries grow descriptive rather than argumentative, and the graph degrades without anyone noticing. Hook enforcement exists to make failure visible and immediate rather than gradual and silent. It runs after every write, classifies violations into hard fails (rewrite before proceeding) and soft flags (surface for human review), and prescribes a fix for each violation rather than merely diagnosing it. The hard/soft separation is itself load-bearing: conflating them either blocks useful output or permits structural failures to accumulate undetected.

## Key Concepts

- [[stub-as-signal]] — graph hooks create stubs intentionally; the enforcement layer signals gaps rather than blocking links
- [[agent-traversal]] — graph hooks enforce the structural minimum that makes traversal possible
- [[moc-as-argument]] — a MOC reference is required in every article frontmatter; hook enforcement ensures MOCs stay current
- [[vault-knowledge-workflow-design]] — hook enforcement is the gate between compile output and committed vault content

## Details

**Structural hooks (hard fail — rewrite before proceeding):**
- Frontmatter present with all required fields: title, project, date, status, moc
- All six required sections present and non-empty: Summary, Key Concepts, Details, Connections, Open Questions
- `moc:` field references at least one MOC
- All wikilinks use lowercase-hyphenated format

**Graph hooks (hard fail — add links before proceeding):**
- Minimum 3 outbound wikilinks with explanatory clauses in Connections
- Backlinked from at least one existing article
- Referenced in its domain MOC

**Quality hooks (soft flag — surface for human review):**
- Summary argues rather than describes (minimum 50 characters is a proxy; the real criterion is argumentative structure)
- Open Questions section contains genuine gaps, not rhetorical questions
- Connections section explains the nature of each link, not just that a link exists

**Implementation split:** `validate.py` handles structural and graph checks mechanically (automated, CI-safe). The COMPILATION_PROMPT handles quality checks by judgment. The split maps to what can be computed vs what requires interpretation.

**The fix field:** every hook violation includes a prescribed fix, not just a description of the problem. The enforcement system prescribes, it does not merely diagnose.

## Connections

- [[vault-knowledge-workflow-design]] — hook enforcement is the gate at the end of every compile step; it determines what enters the committed vault
- [[agent-traversal]] — graph hooks directly enforce the structural requirements for fast traversal: minimum outbound links, backlinks, and MOC registration
- [[stub-as-signal]] — stubs created during hook-guided linking are intentional: the agent adds a link to a non-existent article because the concept belongs there, not because the article exists
- [[spreading-activation]] — the minimum outbound links requirement creates the channels spreading activation travels; weak nodes are activation dead ends

## Open Questions

- Is "summary argues rather than describes" automatable, or is it inherently a judgment call? What would a mechanical proxy look like beyond character count?
- Should quality hook thresholds scale with vault size? An argument that is weak in a 20-article vault may be strong in a 200-article vault where more supporting articles exist.
