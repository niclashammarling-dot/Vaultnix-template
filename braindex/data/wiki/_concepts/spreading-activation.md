---
title: Spreading Activation
type: concept
projects: [general, knowledge-work, teaching, apex]
tags: [knowledge-work/compilation, knowledge-work/graph, teaching/assessment, apex/audit]
source: braindex-template
date: 2026-04-11
related:
  - [[small-world-topology]]
  - [[moc-as-argument]]
  - [[hook-enforcement]]
  - [[concept]]
  - [[knowledge]]
moc: [knowledge-work-moc]
status: active
---

## The Argument

A compile that only creates one article has failed, regardless of the quality of that article. Spreading activation is the mechanism that makes the difference between a vault that grows and a vault that compounds: every new source must propagate changes to 3–5 neighboring articles, updating their Connections, Details, or Open Questions as the new content adds evidence, counterpoints, or unresolved questions. The practical implication is that compilation is never local — every raw input touches a neighborhood, and the size and quality of that neighborhood determines how much the vault improves per compile run.

## The Shared Structure

The term comes from cognitive science (Collins & Loftus, 1975): reading one concept partially activates related concepts in semantic memory, priming retrieval. In the vault, the analogue is structural: compiling one raw source activates its neighborhood, propagating changes outward until the activation falls below a useful threshold. The classification function is binary — a compile either propagated to its neighborhood or it did not — but the inferential consequence is asymmetric: failed propagation produces isolated content that exists in the vault but changes nothing around it.

Execution follows a five-step pattern: (1) compile the primary raw source; (2) read its Connections section 2 hops outward; (3) for each neighbor, ask whether the new source adds evidence, a counterpoint, a missing link, or an unresolved question — if yes, update; (4) update the primary domain MOC (mandatory); (5) flag new stubs created during this run. What to update in neighbors: Connections (add the new article as a wikilink), Open Questions (surface what the new source raises), Details (add a paragraph if the new source adds evidence or counterevidence), MOC Synthesis Claims (update if the new source tips an accumulating claim into a defensible assertion).

The mechanism is content-neutral: it propagates errors at the same speed as insights along the same edges. In the 2026-04-09 TCX correction session, an unverified architectural claim about the Validation Gate reached six articles in one compile pass via backlinks — because it was treated as derivable and compiled normally. The same mechanism that makes a correct new article immediately improve six neighbors also makes a wrong claim immediately corrupt six articles. This is why the derivability filter must catch unverified claims before they enter the compilation path, not after.

## Domain Instances

*The following instances are from the vault this concept was compiled in. Your instances will differ; the pattern is what transfers.*

**Teaching** — updating one subtest interpretation in a Legilexi profile should propagate to neighboring subtests: a revised HÖR classification changes what the ORD and LÄS scores mean. The omtest methodology formalizes this: retest one subtest, re-examine the full profile. A diagnostic update that stops at the single subtest is a compile that touched only one article.

**APEX** — a new backtest finding (e.g., vol targeting hurts Sharpe) must propagate to config, audit CHECKs, MOC synthesis claims, and session memory — not just the immediately relevant parameter. The incident-learning-ritual is the APEX spreading-activation execution pattern: one incident produces four artifacts updated across the neighborhood (memory + CHECK + raw note + compile).

**Knowledge-work (vault)** — the canonical instance. Every compilation run is evaluated on neighborhood impact. The stub list grows during spreading activation: when a new article links to a concept that does not yet exist, the stub is the propagation signal from that article's neighborhood into the gap.

**Cross-domain gate (Validation Gate)** — the 2026-04-27 mobile interface build added a human-in-the-loop checkpoint specifically for the highest-uncertainty spreading activation decisions: cross-domain links at confidence ≥ 0.75. These queue to `raw/audit/spreading-activation-queue.ndjson` rather than committing to Connections immediately. The Validation Gate in vaultnix0.1 presents each queued entry as a swipe card; ACCEPT writes the link to Connections, REJECT generates a negative constraint hook (NC-NNN) preventing the same link from being proposed again. This gives spreading activation a human verification layer at the cross-domain boundary without blocking same-domain propagation.

## What Spreading Activation Is Not

**Not simple link-adding.** Adding a wikilink without propagating inferential implications satisfies the count requirement without producing the effect. The test is not "did I add a link?" but "did the neighbor article become more useful because of the new source?" A connection that could be removed without changing what the neighbor article says is not spreading activation — it is decoration.

**Not exhaustive propagation.** The 2-hop rule is a practical stopping criterion, not a principled one. Activation does not stop at 2 hops in either the cognitive science model or the vault — it attenuates. The rule is: propagate until the activation would produce no change in the neighbor. In practice, 2 hops captures most of the value; beyond that, the marginal article update is usually below the threshold of useful change.

**Not symmetric in value.** Spreading activation is symmetric in mechanism — it propagates equally well in any direction — but asymmetric in outcome. A correct synthesis claim propagated to six neighbors improves all six. An unverified claim propagated to six neighbors corrupts all six. The derivability filter exists because the mechanism does not distinguish; the editorial judgment must.

## Connections

- [[small-world-topology]] — spreading activation is why topology matters; dense local clusters amplify propagation; a weakly-linked article is an activation dead end; the 4-hop traversal target and the 3-5 neighbor propagation rule are designed to maintain this property as the vault grows
- [[hook-enforcement]] — the minimum outbound links requirement directly creates the channels spreading activation travels; graph hooks enforce the structural prerequisite for propagation
- [[compilation-skill]] — spreading activation is the compile-time mechanism; the execution sequence prescribes neighborhood updates as a mandatory step, not optional
- [[knowledge]] — spreading activation is the mechanism by which knowledge compounds in the vault; each propagation step converts a neighbor from a node with adjacent information into a node with richer inferential connections
- [[external-cognition]] — in cognitive science, spreading activation is the retrieval mechanism in external memory; in the vault, it is the write mechanism; the same propagation logic that makes retrieval fast also makes compilation compound
- [[stub-as-signal]] — spreading activation creates new stub links as a side effect; stubs are the graph's honest record of propagation that has not yet reached its destination
- [[concept]] — the unit that activation propagates through; filling a high-value stub is the most productive single act of spreading activation because it simultaneously enriches every article that linked to it

## Open Questions

- How do you prevent spreading activation from being superficial — when does adding a Connections wikilink add genuine value versus merely satisfying a count requirement? Is there a structural check for this, or does it require editorial judgment on every compile run?
- Is the 2-hop rule a principled stopping criterion or a practical approximation? What would a principled criterion look like — activation threshold, marginal article improvement, or something else?
- Error propagation via spreading activation is documented as a known failure mode (2026-04-09 TCX correction). Is there a structural intervention beyond the derivability filter that could catch unverified codebase claims before they enter the compilation path — e.g., a mandatory source-attribution check for any article that names a specific mechanism by file, function, or threshold?
