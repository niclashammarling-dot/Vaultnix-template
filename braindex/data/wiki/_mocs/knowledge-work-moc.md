---
title: Knowledge Work — Map of Content
type: moc
project: knowledge-work
date: 2026-04-08
status: active
---

## The Argument

This domain is about designing knowledge systems that compound — where each piece of knowledge makes the whole more useful rather than merely larger. The central tension is between local article quality and global graph topology: an individually well-written article that is poorly connected degrades the system; a densely connected article that argues nothing does too. The design question is always whether a decision makes agent traversal faster and knowledge synthesis more productive.

## Core Articles

- [[vault-knowledge-workflow-design]] — the operational cycle; understanding this first makes every other structural decision legible
- [[moc-as-argument]] — the structural distinction that determines whether a domain map enables traversal or merely catalogs it
- [[small-world-topology]] — why topology is the binding constraint on system effectiveness at scale
- [[spreading-activation]] — the compilation mechanism that separates a compounding knowledge graph from a document store
- [[hook-enforcement]] — the mechanical gate that keeps the graph structurally sound across compile runs

## Topic Clusters

### Graph Architecture
- [[small-world-topology]] — the structural property the vault targets; high local clustering, low global path length
- [[moc-as-argument]] — the clustering mechanism; domain hubs that orient agent traversal
- [[agent-traversal]] — the traversal pattern the architecture is designed to serve
- [[stub-as-signal]] — gaps as first-class graph elements; the vault's honest statement of what it needs

### Compilation Mechanics
- [[spreading-activation]] — how one source ripples through the graph; the anti-isolation mechanism
- [[hook-enforcement]] — mechanical validation before commit; the structural/graph/quality separation
- [[vault-knowledge-workflow-design]] — the full raw → compile → session cycle and how each phase feeds the next
- [[cross-article-concept-extraction]] — the category boundary between single-article derivable concepts and cross-article emergent concepts; the session-opener concept prompt is the extraction mechanism for the second category
- [[within-system-contrast]] — the concept extraction heuristic for detecting load-bearing structural asymmetries; the detection mechanism for cross-article emergent concept candidates

### Theoretical Grounding
- [[external-cognition]] — the off-loading model; why file-over-app and why the agent operates the external system

## Cross-Domain Connections

Every domain's MOC should link back to [[vault-knowledge-workflow-design]] — it is the mechanism that produced and maintains the MOC itself. Every cross-project concept article in `_concepts/` is a structural instance of [[small-world-topology]] in action: a shortcut node that collapses inter-domain traversal.

## Synthesis Claims

- A vault that grows without topology management becomes a chain, not a network — average path length grows linearly and spreading activation degrades proportionally
- The MOC Argument section is the highest-leverage artifact in the vault: it encodes domain shape for every future agent traversal, and a weak Argument multiplies the cost of every session that touches the domain
- Stubs are not failures; they are the most structurally honest signal the graph produces about what it needs next — removing them to clean up the stub list destroys information
- Hook enforcement must separate hard fails from soft flags: conflating them either blocks useful output or permits structural failures to accumulate silently

## Open Territory

- Multi-agent vault sharing — what breaks when two agents compile simultaneously, and what coordination mechanisms are required?
- Tiered context management for large vaults — when selective context is insufficient, what is the right escalation?
- The point at which vault size makes the session-opener-skill stub-scoring approach break down — too many high-value stubs to surface meaningfully
