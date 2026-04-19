---
title: Small-World Topology
project: knowledge-work
tags: [knowledge-work/graph, knowledge-work/architecture]
source: braindex-template
date: 2026-04-08
related: [moc-as-argument, spreading-activation, agent-traversal]
moc: [knowledge-work-moc]
status: active
---

## Summary

A vault that grows without topology management becomes a chain, not a network — average path length increases with every article added, and spreading activation degrades proportionally. The antidote is deliberate small-world design: high local clustering (MOCs create dense domain hubs) combined with low global path length (concept articles create cross-domain shortcuts). Without both properties simultaneously, the vault either becomes a set of isolated domain silos or a loosely connected flat list. The 4-hop target between any two MOCs is not aspirational — it is a hard structural requirement, and failing it means the vault cannot be effectively traversed by an agent.

## Key Concepts

- [[moc-as-argument]] — local hubs that create domain clustering
- [[spreading-activation]] — propagates through the graph; dense clusters amplify it
- [[agent-traversal]] — the traversal pattern this topology is designed to serve
- [[stub-as-signal]] — gaps signal where shortcuts are needed
- [[hook-enforcement]] — graph hooks enforce the minimum linking that sustains topology

## Details

The Watts-Strogatz model shows that rewiring a small fraction of links in a regular lattice dramatically reduces average path length while preserving local clustering. The vault exploits this: MOCs cluster domain articles (high local density); concept articles bridge domains (low global path length).

**Failure modes:**
- Chain topology: each article links forward only, never backward → path length grows linearly with vault size
- Star topology: all articles link to one hub but not to each other → single point of failure, no local clustering
- Island topology: domains with no cross-domain connections → activation cannot propagate across the graph

**Diagnostic:** if the average shortest path between any two MOCs exceeds 4 hops, the graph needs a bridging concept article. If an isolated cluster has no cross-domain links, it is an island — flag immediately.

**Design rules:**
- Every new article should reduce global path length, not merely add local content
- Concept articles in `_concepts/` are deliberately placed shortcuts — they exist because the concept appears across domains, creating a structural need for a shared node
- Backlinks are not optional: they are the return paths that give the graph its small-world property

## Connections

- [[moc-as-argument]] — MOCs are the clustering mechanism; they create the local density component of small-world topology without which the graph degrades into a sparse random network
- [[agent-traversal]] — small-world topology is the structural prerequisite for fast agent traversal; the 4-hop target defines the topology requirement
- [[spreading-activation]] — activation propagates faster through dense local clusters; small-world topology is why compilation ripples rather than terminates
- [[vault-knowledge-workflow-design]] — the compilation workflow is designed to maintain topology health; lint checks surface topology failures

## Open Questions

- At what vault size does topology management become the primary constraint rather than content creation? Is there a crossover point that can be measured?
- Is there a meaningful distinction between intentional shortcuts (concept articles placed deliberately) and emergent shortcuts (domain articles that happen to attract many inbound links)? Should the vault treat them differently?
