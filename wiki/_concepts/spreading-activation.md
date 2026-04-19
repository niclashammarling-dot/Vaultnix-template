---
title: Spreading Activation
project: knowledge-work
tags: [knowledge-work/compilation, knowledge-work/graph]
source: braindex-template
date: 2026-04-08
related: [small-world-topology, moc-as-argument, hook-enforcement]
moc: [knowledge-work-moc]
status: active
---

## Summary

A compile that only creates one article has failed, regardless of the quality of that article. Spreading activation is the mechanism that makes the difference between a vault that grows and a vault that compounds: every new source must propagate changes to 3-5 neighboring articles, updating their Connections, Details, or Open Questions as the new content adds evidence, counterpoints, or unresolved questions. The practical implication is that compilation is never local — every raw input touches a neighborhood, and the size and quality of that neighborhood determines how much the vault improves per compile run.

## Key Concepts

- [[small-world-topology]] — the graph structure spreading activation travels through
- [[moc-as-argument]] — Synthesis Claims accumulate from repeated spreading activation
- [[hook-enforcement]] — graph hooks on minimum outbound links create the channels activation travels
- [[stub-as-signal]] — spreading activation creates new stub links as a side effect; those stubs are signal
- [[vault-knowledge-workflow-design]] — the compile phase is where spreading activation runs

## Details

The term comes from cognitive science: reading one concept partially activates related concepts in memory, priming retrieval. In this vault, the analogue is structural: compiling one raw source activates its neighborhood, which activates its neighbors, propagating changes outward until the activation falls below a useful threshold.

**Execution:**
1. Compile the primary raw source → create or update the target article
2. Read its Connections section (2 hops outward)
3. For each neighbor: does the new source add evidence, a counterpoint, a missing link, or an unresolved question? If yes, update.
4. Update the primary domain MOC (mandatory)
5. Flag new stubs created during this run

**What to update in neighbors:**
- Connections: add the new article as a wikilink with an explanatory clause
- Open Questions: surface what the new source raises for this neighbor
- Details: add a paragraph if the new source adds evidence or counterevidence to an existing claim
- MOC Synthesis Claims: update if the new source tips an accumulating claim into a defensible assertion

**Failure mode:** A compile that only creates one article and touches nothing else. This produces isolated content — knowledge that exists in the vault but does not activate anything. The agent should ask why the propagation stopped.

## Connections

- [[small-world-topology]] — spreading activation is why topology matters; dense local clusters amplify propagation rather than absorbing it
- [[moc-as-argument]] — Synthesis Claims are the accumulated output of spreading activation; they capture what the domain knows as a whole
- [[hook-enforcement]] — the minimum outbound links requirement directly creates the channels spreading activation travels; a weakly-linked article is an activation dead end
- [[vault-knowledge-workflow-design]] — spreading activation is the compile-time mechanism; the three-phase workflow schedules and enforces it

## Open Questions

- How do you prevent spreading activation from being superficial — when does adding a Connections wikilink add genuine value versus merely satisfying a count requirement?
- Is the 2-hop rule a principled stopping criterion or a practical approximation? What would a principled criterion look like?
