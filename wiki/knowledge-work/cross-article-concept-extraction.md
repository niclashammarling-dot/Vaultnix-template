---
title: Cross-Article Concept Extraction — Category Boundary and Human-Loop Requirement
project: knowledge-work
tags: [knowledge-work/compilation, knowledge-work/concepts, knowledge-work/automation]
source: braindex-template
date: 2026-05-09
related:
  - [[agent-operated-knowledge-systems]]
  - [[session-opener-skill]]
  - [[vault-nightly-draft-workflow]]
  - [[spreading-activation]]
  - [[within-system-contrast]]
moc: [knowledge-work-moc]
status: active
---

## Summary

Concept articles emerge from two structurally distinct sources that require different extraction mechanisms. Single-article derivable concepts — those whose definition is present within one article's argument — are correctly surfaced by the nightly agent's single-article reading filter. Cross-article emergent concepts — those whose definition lives in the structural relationship *between* articles, in the comparison rather than in any node's content — require simultaneous access to multiple articles and cannot be detected by any single-article traversal, regardless of scoring refinement. The in-session compilation path (human noticing the pattern across articles, surfaced via the concept prompt in the session opener) is the architecturally correct mechanism for the second category. The two categories are not interchangeable; patching the nightly agent's filter cannot close the structural gap.

## Key Concepts

- [[within-system-contrast]] — the confirming instance: the concept was not in `compensatory-prompt-design` alone, not in `moc-as-argument` alone, but in the structural fact that both articles used the same detection move without naming it
- [[vault-nightly-draft-workflow]] — the nightly agent's single-article reading is the right mechanism for category 1; encoding the category boundary explicitly prevents the workflow from being incorrectly expanded to cover category 2
- [[session-opener-skill]] — the concept prompt in Step 3 is load-bearing precisely because it catches what the nightly agent cannot; it is the extraction mechanism for category 2
- [[agent-operated-knowledge-systems]] — the category boundary is an architectural constraint, not a quality deficit; no improvement to the automated layer can bridge a structural limitation

## Details

### The two categories

**Category 1 — single-article derivable:** The concept's definition can be inferred from reading one article in isolation. The nightly agent reads each article, generates a description, and applies a derivability filter. If the concept is fully present in the article, the filter fires. `spreading-activation`, `hook-enforcement`, `stub-as-signal` are examples: reading any one of them fully exposes the concept.

**Category 2 — cross-article emergent:** The concept lives in a structural relationship between articles. The definition requires asking: "why do these two articles share a move I can see in both?" `within-system-contrast` is the founding confirmed instance — it was invisible in `compensatory-prompt-design` alone (which is a compensatory design article, not a contrast article) and invisible in `moc-as-argument` alone (which is a MOC quality article, not a contrast article). The concept became visible only when both articles were held simultaneously and the shared epistemic move became apparent.

The agent cannot see this because it never holds two articles in view simultaneously. This is not a filter gap — it is a reading architecture limit.

### Why this distinction matters for compilation

The nightly draft workflow is designed around category 1. If the category boundary is not encoded explicitly, two failure modes emerge:

1. The workflow is expanded (incorrectly) to attempt cross-article extraction — resulting in hallucinated concepts or low-quality drafts that fail the source-diversity check
2. Category 2 concepts are never surfaced in the nightly path, leaving them invisible even to the session opener if the human doesn't happen to notice the pattern

The session opener's Step 3 concept prompt ("what concept is implied across multiple articles loaded this session?") is the correct and sufficient mechanism for category 2. Its value increases in proportion to the density of recent compilation — after a high-density compile run, the human holds more articles in working memory and the cross-article pattern becomes recognizable.

### Mandatory MOC removal test at compile time

A related gap: the current compilation template has no step that asks whether the MOC's argument still holds as a whole after a new synthesis claim is added. Fast claim accumulation without a MOC-level check is the mechanism by which an argumentative MOC degrades into a list of claims dressed as an argument — the exact failure mode `moc-as-argument` names.

The mandatory fix: the MOC update step in compilation-skill Step 4 must include a removal test before any new synthesis claim is added. "If this MOC were removed, would the domain articles still collectively answer the domain's central question, or would a reasoning gap remain?" The test must be mandatory; optional checks at compile time are skipped under time pressure.

## Visual References

None.

## Connections

- [[vault-nightly-draft-workflow]] — the category boundary must be encoded here as an architectural fact: single-article reading is the right mechanism for category 1; cross-article emergent concepts require human extraction; the two categories are not interchangeable
- [[session-opener-skill]] — Step 3 concept prompt is the extraction mechanism for category 2; its load-bearing status should be noted explicitly in the skill (not just treated as a bonus observation step)
- [[within-system-contrast]] — the founding confirmed instance of a category 2 concept; emerged from holding `compensatory-prompt-design` and `moc-as-argument` simultaneously; invisible to any single-article reader
- [[agent-operated-knowledge-systems]] — the category boundary is an architectural constraint on the AOKS model, not a deficit; the human loop's irreplaceable contribution is cross-article pattern recognition
- [[compilation-skill]] — Step 4 MOC update requires a mandatory removal test before any new synthesis claim; this finding identified the current absence of that test

## Open Questions

- Does the category boundary also apply to connection generation (Suggested Connections in spreading activation), or only to concept extraction? Spreading activation already requires holding source and target articles simultaneously — does that make it immune to the single-article limitation?
- Is there a structural signal that reliably predicts when cross-article emergent concepts are likely to surface? After a high-density compile session producing multiple articles in the same domain seems like a reliable predictor — but the session opener doesn't currently score for this.
- Does the mandatory MOC removal test change anything about how Synthesis Claims should be drafted? A claim that passes the removal test individually may still be one of five claims that collectively make the MOC argument circular rather than progressive.
