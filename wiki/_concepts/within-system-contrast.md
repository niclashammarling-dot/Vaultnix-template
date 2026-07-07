---
title: Within-System Contrast
type: concept
projects: [knowledge-work, apex, tcx]
tags: [knowledge-work/concept-extraction, knowledge-work/session, vault/compilation]
source: braindex-template
date: 2026-05-09
related:
  - [[compensatory-prompt-design]]
  - [[moc-as-argument]]
  - [[stub-as-signal]]
  - [[spreading-activation]]
moc: [knowledge-work-moc]
status: active
---

# Within-System Contrast

## The Argument

Within-system contrast is a concept extraction heuristic: when two components in the same system diverge on a measurable property, and the divergence is traceable to a structural asymmetry between them, that asymmetry names a load-bearing principle. The heuristic is more reliable than cross-system observation because shared context eliminates confounds — both components operate under the same goals, constraints, and environment, so their difference cannot be attributed to context. The divergence must be explained by something structural about the components themselves, and that structural fact is the concept.

The classification function: a within-system contrast picks out a principle as load-bearing (vs. incidental) when the observed divergence would disappear if the asymmetric structural fact were equalized. If making the two components structurally identical would collapse their property difference, the difference was a consequence of the structural asymmetry — not noise.

## The Shared Structure

Within-system contrast is operative when all four conditions hold:

1. **Same system** — both components share context: same goals, constraints, environment, deployment conditions. This is what eliminates the cross-system confound.
2. **Observable property divergence** — one measurable dimension differs between the components (prompt strictness, mechanism type, correction frequency, documentation depth).
3. **Causal asymmetry** — the property divergence traces to a structural fact that applies to one component but not the other. The structural fact is not a design choice made in isolation; it is a consequence of the component's position, function, or constraints within the system.
4. **Collapse test** — equalizing the asymmetric structural fact would collapse the property divergence. This is what distinguishes load-bearing contrast from stylistic variation.

**The failure mode:** when contrast is observed but the collapse test is not applied. Stylistic divergence (a shorter prompt because the prompt author was pressed for time; a different mechanism because a different engineer wrote it) can produce observable property differences without a load-bearing concept underneath. Within-system contrast as a heuristic requires the causal step — tracing the divergence to a structural fact — not just the observation step.

## Domain Instances

*The following instances are from the vault this concept was compiled in. Your instances will differ; the pattern is what transfers.*

**Knowledge-work (vault — moc-as-argument)** — Within the vault, MOCs that argue vs. MOCs that route are two implementation types of the same component class (Maps of Content) operating in the same graph. The contrast is detectable by the removal test: argumentative MOCs leave a reasoning gap when removed; routing MOCs leave only navigation loss. The structural asymmetry is whether the MOC stakes a position on the domain's central tension. Equalizing that asymmetry — making a routing MOC argumentative, or flattening an argumentative MOC to a list — collapses the removal-test outcome. The within-system contrast between current vault MOCs and the "failing MOC" archetype named the concept.

**TCX / APEX (compensatory-prompt-design)** — Within TCX, the teacher agent and the counselor agent operate in the same system, under the same architecture, toward the same goal. Their prompts diverge sharply: teacher prompts are sparse; counselor prompts are maximally specified with named failure modes and explicit prohibitions. The structural asymmetry is output reversibility combined with the presence or absence of a per-output correction loop. Counselor outputs initiate hard-to-reverse processes; no output-level audit exists. The same asymmetry is present within APEX between Lock 1–4 (classifier gates with mechanical audit) and Lock 5 (reasoning gate with no per-decision audit). Equalizing the correction-loop structure would equalize the required prompt strictness. The within-system contrast named compensatory prompt design as a principle.

## What Within-System Contrast Is Not

**Not cross-system comparison.** Comparing a sparse prompt in one system to a maximally specified prompt in a different system cannot isolate the structural cause — different systems differ on too many dimensions simultaneously. The within-system constraint is load-bearing for the heuristic's reliability, not a convenience.

**Not anomaly detection.** An anomaly is a deviation from a system norm, and the response is to investigate whether the deviation is an error. Within-system contrast treats both components as correctly implemented — the divergence is evidence of principled asymmetry, not a defect to investigate.

**Not a counterfactual or removal test.** The removal test (from [[moc-as-argument]]) asks: what would break if this component were removed? Within-system contrast does not remove anything — it observes two live implementations simultaneously and asks: what structural fact explains why they differ? The two heuristics are complementary but distinct: the removal test validates that a concept does argumentative work; within-system contrast detects that a concept exists.

**Not the same as strictness differential.** Strictness differential is one observable property that within-system contrast can surface. It is not the concept itself. Two components can exhibit identical strictness while still instantiating within-system contrast along a different dimension (mechanism type, documentation depth, correction frequency).

## Connections

- [[compensatory-prompt-design]] — primary source; "The Pattern That Makes It Visible" section names within-system contrast explicitly as the detection mechanism; the TCX teacher/counselor and APEX Lock 1–4/Lock 5 tables are the clearest instantiation in the vault.
- [[moc-as-argument]] — second confirmed instance; argumentative vs. routing MOC implementations within the same vault graph; within-system contrast is the implicit heuristic behind the removal test comparison.
- [[stub-as-signal]] — within-system contrast observations produce concept candidates before any article exists; they become stubs when named, and the stub score reflects the cross-domain reach of the underlying contrast.
- the session opener skill — Step 3 ("any observations from recent work that haven't been named yet?") is the session mechanism designed to catch within-system contrast before the observation is lost; this article is the theory basis for what Step 3 is listening for.
- [[spreading-activation]] — once a concept is extracted via within-system contrast and compiled, activation propagates to all articles that contain the underlying structural asymmetry; the two confirmed instances had activation spread to six existing articles on 2026-05-09 compile.
- the compilation skill — the concept prompt in Step 3 of the session opener is a compilation input; within-system contrast explains why that prompt reliably surfaces extractable concepts rather than vague impressions.

## Falsification Status

Both confirmed instances were compiled 2026-05-09. A source-diversity concern was raised at session close: because both wiki articles (compensatory-prompt-design, moc-as-argument) were written in the same compile session, the majority-prior test on compilation dates produces a borderline result — moc-as-argument was compiled 2026-05-08 (prior session, passes), compensatory-prompt-design was compiled earlier the same day (same session).

The interpretation applied and accepted: **the relevant timestamp is not the wiki article compilation date but the date the underlying artifacts were created.** The agents.js counselor prompt and the APEX Lock 5 reasoning gate both predate this session by months. The moc-as-argument contrast (argumentative vs. routing MOC implementations) references vault MOC files that similarly predate this session. The wiki articles are descriptions of pre-existing structural facts, not the evidence itself. On this interpretation, the source-diversity gate passes cleanly.

A future agent applying the source-diversity check to this article should evaluate: are the underlying artifacts (agents.js, lock5-claude-reasoning, vault MOC files) the correct evidence base, or does the check require the wiki compilation dates? The interpretation is defensible but is a judgment call, not a mechanical pass. If the check is applied against compilation dates alone, the result is borderline (1 of 2 instances prior).

## Open Questions

- **Teaching domain instance.** The `compensatory-prompt-design` Open Questions section flags omtest as a candidate third instance: classroom intervention protocols may operate under the same structure — rules substituting for absent per-output correction on consequential student actions [blocked: third-instance-needed]. If confirmed, this widens the concept and may warrant a slug rename. Confirmation requires examining the actual review path for IUP documentation and student referral outputs.
- **Minimum contrast threshold.** When is a divergence too small to extract a concept rather than label a stylistic preference? The current criterion (causal asymmetry traceable to a structural fact, collapse-test positive) needs a sharpness threshold. Two prompts that differ in length because of author preference and two prompts that differ because of correction-loop asymmetry can look observationally similar before the collapse test is applied.
- **Automated detection as a lint pass.** Could a lint pass flag component pairs with significant property divergence as concept candidates — e.g., pairs of agents in the same system with large prompt-length differentials, or MOCs with divergent removal-test scores? This would require formalizing "component pair," "property," and "divergence magnitude." The precondition test for open-question tagging (current session agenda) is an adjacent infrastructure question.
