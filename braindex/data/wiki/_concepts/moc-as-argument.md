---
title: MOC as Argument
project: knowledge-work
tags: [knowledge-work/architecture, knowledge-work/graph]
source: braindex-template
date: 2026-04-08
related: [small-world-topology, agent-traversal, spreading-activation]
moc: [knowledge-work-moc]
status: active
---

## Summary

A Map of Content is not a table of contents. The distinction is structural: a table of contents organizes articles by category; a MOC makes a claim about how articles in its domain relate and what that relationship implies. A MOC that is a list has failed — it provides no synthetic value beyond what the individual articles already contain. A MOC that makes an argument gives an agent the shape of a domain before it reads a single article, enabling it to navigate toward what matters rather than scanning everything.

## Key Concepts

- [[small-world-topology]] — MOCs are the clustering mechanism; they create the local hubs that give the graph its small-world property
- [[agent-traversal]] — MOCs are the primary traversal entry point; the Argument section orients the agent before it drills in
- [[spreading-activation]] — Synthesis Claims accumulate from repeated spreading activation across the domain
- [[stub-as-signal]] — Open Territory sections in MOCs are the highest-priority stub signals
- [[vault-knowledge-workflow-design]] — MOC maintenance is a mandatory step in every compile run

## Details

**The Argument section** (2-3 sentences) is the MOC's core function. It answers: what is this domain about, and what is the central tension or design question? Written for an agent that needs the shape of the domain before navigating into it — not a description of what the MOC contains, but a claim about how the domain works.

**Core Articles:** not "which articles exist" but "which 3-5 articles must be read to understand the domain structure, and why are they foundational?" One clause each on why they matter structurally — not what they cover.

**Synthesis Claims:** 2-4 claims that only emerge from reading the domain together — things visible at the MOC level but not within individual articles. These are the product of accumulated spreading activation. A domain with no Synthesis Claims has not been compiled deeply enough.

**MOC drift:** a MOC that grows toward a mere list should have its Argument section rewritten before adding more articles. The signal: Synthesis Claims section is empty or the Argument describes the domain rather than asserting something about it.

**Cross-domain connections** in MOCs are the highest-value links in the graph. They create small-world shortcuts: an agent navigating one domain can jump directly to another domain's conceptual center rather than traversing through individual articles.

**Cluster splitting rule:** when a topic cluster exceeds 8 articles, split it. Document the split in Synthesis Claims — the fact that the cluster needed splitting is itself a claim about the domain's structure.

## Connections

- [[small-world-topology]] — MOCs create the clustering component of small-world topology; they are the local hubs around which domain articles organize
- [[agent-traversal]] — the MOC Argument section is the first thing an agent reads when entering a domain; the quality of that Argument determines the efficiency of everything that follows
- [[spreading-activation]] — MOC Synthesis Claims are the accumulated output of spreading activation; they capture what the domain knows collectively
- [[hook-enforcement]] — graph hooks require every article to reference its MOC; this enforcement keeps MOCs current as the vault grows

## Open Questions

- When does a domain split into two MOCs? The 8-article cluster rule is mechanical — what is the conceptual criterion for a principled split versus an arbitrary one?
- Is there a MOC structure that handles rapidly evolving domains without requiring constant Argument rewrites? How should a MOC signal that its Argument is provisional?
