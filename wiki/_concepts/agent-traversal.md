---
title: Agent Traversal
project: knowledge-work
tags: [knowledge-work/architecture, knowledge-work/graph]
source: braindex-template
date: 2026-04-08
related: [moc-as-argument, small-world-topology, hook-enforcement]
moc: [knowledge-work-moc]
status: active
---

## Summary

A vault optimized for human reading and a vault optimized for agent traversal are structurally different artifacts. Human reading tolerates long text, rich prose, and browsable catalogs. Agent traversal requires short paths, explicit connection reasons, and MOCs that state their argument before listing their articles. Every structural decision in this vault — naming convention, minimum link count, MOC format, concept article placement — is made for agent traversal, not human comfort. The payoff is that an agent can locate, activate, and synthesize relevant knowledge without exhaustive search; the cost is that the vault looks sparse and mechanical to a human skimming it for the first time.

## Key Concepts

- [[moc-as-argument]] — the primary traversal entry point; its Argument section orients the agent before it drills in
- [[small-world-topology]] — the structural property that makes the 4-hop target achievable
- [[hook-enforcement]] — graph hooks enforce the minimum linking that makes traversal possible
- [[external-cognition]] — agent traversal is the read cycle of the external cognition system
- [[stub-as-signal]] — stubs are traversal dead ends that the SESSION_OPENER surfaces for resolution

## Details

**Standard traversal path:**
1. Read the relevant MOC → The Argument, Core Articles
2. Follow Core Articles to understand domain shape
3. Follow Connections outward from the most relevant article
4. Reach the target within 2-4 hops

**Fast traversal (concept shortcut):**
1. Read the relevant MOC
2. Identify a concept article in `_concepts/` that bridges to the target domain
3. Jump directly to the target domain via the concept article
4. 2-3 hops total

**Traversal failures:**
- **Orphan articles:** exist in the vault but have no inbound links; unreachable through Connections traversal regardless of path
- **Weak nodes:** too few outbound links to navigate from; traversal terminates here
- **Island clusters:** no cross-domain connections; activation cannot propagate across the graph
- **Unnamed connections:** a Connections entry without an explanatory clause gives the agent no signal on whether to follow it

**Naming matters for traversal:** article slugs should encode semantic content, not just subject. An agent traversing a domain can predict likely article names. `engine-fast-architecture.md` is predictable; `efa.md` is not.

**The backlink requirement** ensures every article can be found from at least one direction other than direct search. An article with no backlinks can only be found by the agent if it already knows the article exists — which defeats the purpose of a navigable graph.

## Connections

- [[moc-as-argument]] — MOCs are the primary traversal entry points; the quality of the Argument section determines how efficiently the agent can orient and begin navigating
- [[small-world-topology]] — the 4-hop target is a direct statement of the topology requirement; small-world topology is the structural guarantee that traversal stays efficient as the vault grows
- [[hook-enforcement]] — graph hooks enforce minimum outbound links and backlinks; without these constraints, traversal would terminate at weakly-connected articles
- [[external-cognition]] — agent traversal is the read cycle of the external cognition system; the vault's architecture exists to serve this specific interaction pattern

## Open Questions

- How does optimal traversal change when the agent has semantic search available versus pure wikilink navigation? Do the structural requirements change, or only the traversal strategy?
- Is there a MOC structure that explicitly encodes likely traversal paths — pre-mapping the routes an agent would most often take — rather than leaving the agent to infer paths from Connections?
