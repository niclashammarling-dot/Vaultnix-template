---
title: Stub as Signal
project: knowledge-work
tags: [knowledge-work/graph, knowledge-work/architecture]
source: braindex-template
date: 2026-04-08
related: [hook-enforcement, agent-traversal, moc-as-argument]
moc: [knowledge-work-moc]
status: active
---

## Summary

A stub is a wikilink pointing to a non-existent article. In most wikis, stubs are errors corrected by removing the link. In this vault, stubs are intentional — they are the graph's demand signal. The number of articles pointing to a stub measures how many knowledge sources already assume that concept exists. A stub with 5 inbound links represents a gap that, when filled, will simultaneously enrich 5 articles. Stubs are never removed; they are scored and prioritized. The stub list is the vault's honest statement of what it needs next.

## Key Concepts

- [[hook-enforcement]] — graph hooks create stubs deliberately during compilation; the enforcement layer signals gaps rather than blocking links
- [[moc-as-argument]] — MOC Open Territory sections surface the highest-priority stubs for each domain
- [[spreading-activation]] — filling a high-value stub triggers activation through all articles that linked to it
- [[agent-traversal]] — stub scoring is how SESSION_OPENER identifies the highest-value sessions
- [[small-world-topology]] — high-value stubs often indicate missing shortcuts; filling them can dramatically reduce average path length

## Details

**Stub scoring formula:** each stub is scored on four dimensions (1-10 each), summed for a total out of 40.

- **Inbound link count:** how many existing articles point to this stub? More inbound links means filling this stub will enrich more articles simultaneously.
- **Cross-domain reach:** does the stub appear in articles from multiple domains? A cross-domain stub is a concept article candidate — its existence would create a small-world shortcut.
- **MOC alignment:** is this stub listed under Open Territory in a MOC? Explicit MOC recognition means the domain has collectively identified this as a structural gap.
- **Synthesis potential:** would filling this stub enable a new Synthesis Claim in a MOC? Stubs that unlock higher-order arguments score higher than those that merely add detail.

**Priority tiers:**
- High-value (≥ 20): require human direction — genuine knowledge gaps, not just missing articles
- Mid-value (12-19): can be filled with focused research or synthesis from existing articles
- Low-value (< 12): candidates for automated nightly drafting

**What stubs are not:** a stub is not a placeholder or a mistake. Adding a wikilink to a non-existent article is an assertion — it says "this concept belongs here, and it will need its own article eventually." Removing the link to clean up the stub list is a structural failure: it hides the gap.

## Connections

- [[hook-enforcement]] — graph hooks require minimum outbound links; this requirement generates stubs as a side effect of ensuring articles are adequately connected
- [[moc-as-argument]] — Open Territory sections in MOCs are the curated version of the stub list; they surface stubs that a human has judged to be domain-level gaps, not incidental absences
- [[spreading-activation]] — filling a high-value stub is the highest-leverage compile action: one article fills a gap and immediately activates everything that was pointing to it
- [[agent-traversal]] — the SESSION_OPENER stub scoring runs before every session; the stub list is the primary mechanism for directing session work toward what the vault most needs

## Open Questions

- Is the four-dimension scoring formula the right decomposition, or are there stub properties that matter more in specific domains? Should domain MOCs be able to declare custom scoring weights?
- How do you distinguish a stub that represents a genuine knowledge gap from one that represents a naming collision or a concept that should be merged into an existing article rather than given its own?
