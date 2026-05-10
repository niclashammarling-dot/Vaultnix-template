---
title: Compilation Skill — Vault Knowledge Compilation
project: knowledge-work
type: skill
tags: [knowledge-work/skills, knowledge-work/compilation]
source: derived
date: {{TODAY}}
related: [[skill-layer-architecture]], [[agent-operated-knowledge-systems]], [[hook-enforcement]], [[stub-as-signal]], [[spreading-activation]]
moc: [knowledge-work-moc]
status: active
---

## Summary

The compilation skill converts raw/ input into wiki/ knowledge: new articles, spreading activation across the neighborhood, MOC updates, concept articles, and index maintenance. It is the primary growth mechanism of the vault — the process by which {{OWNER}}'s raw thinking enters the knowledge graph and becomes agent-navigable. This skill is the canonical compilation reference; any separate COMPILATION_PROMPT.md file is superseded by this document.

---

## When to Invoke

- {{OWNER}} says "compile" or "run compile"
- A raw/ file has been added or updated
- A session ends and a session note needs to enter the graph

---

## Execution Pattern

Run steps strictly in sequence. Report Step 1 findings before any writes. Hook enforcement (Step 2C) runs after every individual write.

### Vault architecture

```
{{VAULT_NAME}}/
├── raw/                  ← {{OWNER}} dumps here. Read only. Never write.
│   ├── _inbox/           ← unprocessed captures
{{DOMAIN_LIST}}
├── wiki/                 ← Agent writes everything here.
{{DOMAIN_LIST}}
│   ├── _mocs/            ← Maps of Content
│   ├── _concepts/        ← Cross-project concept articles
│   ├── _skills/          ← Practice layer (skills)
│   └── _index/           ← INDEX.md, MOC-INDEX.md, INSPIRATION.md
├── assets/
│   └── images/           ← renamed, descriptive image files
├── outputs/              ← query results filed back in; never touch during compile
├── lint/                 ← health check reports
└── templates/
```

---

### Step 0 — Pre-flight: Known Failure Check

Before reading any files, run this checklist. Each item is a failure mode from past compile runs. If any box cannot be checked confidently, resolve it before proceeding.

- [ ] **Spreading activation**: plan to touch 3–5 articles minimum — a single-article compile without neighborhood updates is a graph failure
- [ ] **Hook enforcement position**: commit to running it after every individual write, not once at the end
- [ ] **Domain routing**: for each raw source, confirm `project:` field is present and maps to the correct `wiki/[domain]/` folder
- [ ] **Operational vs. theoretical routing**: content that describes how to run this specific vault (decisions, rituals, interface, infrastructure) stays in a vault-specific domain; content that makes an abstract claim about knowledge systems in general routes to `knowledge-work`; when in doubt, ask whether a different vault would also benefit from this article
- [ ] **Stale MOC risk**: every new article must update its domain MOC in the same run
- [ ] **New enforcement rule check**: if this compile session introduces a new enforcement rule (protocol, hook, naming convention), apply it immediately to all writes in this session — documentation without activation is latent failure; if earlier writes in the session already violated it, log them explicitly in the compile report
- [ ] **Notes-to-enforcement check**: if any source is an incident, learning, or design decision, ask whether the finding warrants a new lint check or structural update — if yes, that write is required before the compile is marked complete; a learning that only produces a wiki article but no enforcement update is incomplete
- [ ] **Commit scope**: only `wiki/` staged; `templates/`, `raw/`, operational config files never staged
- [ ] **Batch verification mode**: if this run will exceed 10 articles, or includes 2+ new `_concepts/` articles, plan a post-run sample pass before committing — pick 3–5 articles at random and apply the full hook checklist explicitly, then run the end-of-update argument audit on each updated MOC

---

### Step 1 — Inventory

Read the full directory tree of raw/, wiki/, assets/, and wiki/_mocs/.

Report clearly before any writes:
- New or updated raw files without a corresponding wiki article
- Unprocessed images in raw/ folders
- Stale MOCs or articles (raw source updated or neighborhood significantly changed)
- Current state of INDEX.md, MOC-INDEX.md, and INSPIRATION.md

Nothing in raw/ may remain unprocessed.

**Routing rule — ideas/:**
Actionable ideas — things to build, add, change, or investigate — compile to `wiki/general/ideas/` if a general domain exists, or to the most relevant domain's ideas subfolder. Ideas are distinguishable from inspiration by actionability: they imply a next step.

**Routing rule — inspiration/:**
Visual references, aesthetic references, and GitHub URLs compile to `wiki/inspiration/`. A GitHub repo is a technical and aesthetic reference: describe what it does, what direction it points, what decisions it might enable. Explicitly stated visions or desires that imply no concrete next step also land here.

---

### Step 2 — Compile new articles

For each new raw source, create or update the wiki article using templates/article.md.

**Required article structure:**
- `## Summary` — 3–5 sentences that capture the argument, not just the topic
- `## Key Concepts` — [[wikilinks]] only; link every concept even if the target does not yet exist (stubs are intentional)
- `## Details` — substantive content at domain-expert density
- `## Visual References` — any images that illuminate this article
- `## Connections` — 3–6 [[wikilinks]] with one clause each explaining the nature of the connection, not just that it exists
- `## Open Questions` — 2–3 genuine gaps this source raises; never delete on future updates, only append. If a question is blocked by a missing prerequisite that is not stated in the question text, append `[blocked: reason]` inline on the same line before the question mark. Three established reason categories: `missing-dataset` (answer requires data that has not been collected), `system-maturity` (answer requires infrastructure or scale not yet reached), `third-instance-needed` (answer requires a confirming instance that has not yet been observed). Placement rule: the tag follows the final clause of the question setup and precedes the question mark or sentence-ending period. Human tagging is required for implicit blocking conditions — an automated agent cannot detect them from article text alone.

**Required frontmatter:**
```yaml
---
title:
project:
tags: []          # format: domain/subtopic e.g. knowledge-work/compilation
source:
date:
related: []       # [[wikilinks]] to 3–5 most related articles
moc: []           # which MOC(s) this article belongs to
status: active | draft | stable
---
```

**Naming:** lowercase-hyphenated.md only.
✓ `route-planning-principles.md`
✗ `RoutePlanning.md`, `route planning.md`

**Domain routing — determined by `project:` frontmatter field:**

Route each article to `wiki/[project-name]/` where the project name matches the domain declared in the `project:` field. The domain list for this vault is defined in vault.config.yaml. `knowledge-work` is always a structural domain: use it only for abstract cross-domain theory (concepts that would be true in any vault). Use the vault's named domains for content that belongs specifically to this vault's knowledge areas.

**Cross-project flag:** if content appears substantively in 2+ domains, flag as `_concepts/` candidate at the bottom of the article.

---

### Step 2B — Process image assets

For every unprocessed image in raw/ subfolders:

1. **Read the image.** Describe as an agent briefing: subject + specific aesthetic qualities (color names, mood, composition, style, era, typography) + the precise decision or creative direction this image supports. Never use vague praise.

2. **Rename and copy to assets/images/:** `YYYY-MM-DD-[descriptive-slug].[ext]`
   Slug must encode aesthetic content, not just subject:
   ✓ `2026-04-05-birch-fog-muted-greens-horizontal.jpg`
   ✗ `2026-04-05-nature-photo.jpg`

3. **Create an inspiration article** in wiki/inspiration/:
   - Embed: `![[descriptive-slug.jpg]]`
   - Write the agent briefing
   - Capture the why: what specific decision does this image support?
   - Tags: `#inspiration/[theme]`, `#aesthetic/[quality]`, `#project/[relevant]`
   - [[wikilinks]] to every project or concept article it bears on

4. **Backlink from 2–3 existing articles.** Add or append a `## Visual References` section to those articles.

5. **Update wiki/_index/INSPIRATION.md** — filename, one-line briefing, linked articles, theme tag.

Orphaned images (not linked from any article) are a structural failure.

---

### Step 2C — Hook enforcement (after every single write)

Run after every individual file write. Fix structural and graph hooks before proceeding. Flag quality hooks in Pending Review.

**Structural hooks (hard fail — rewrite):**
- [ ] Frontmatter present with all required fields populated
- [ ] All six required sections present and non-empty
- [ ] `moc: []` references at least one MOC
- [ ] All [[wikilinks]] use lowercase-hyphenated format

**Graph hooks (hard fail — add links):**
- [ ] Minimum 3 outbound [[wikilinks]] with explanatory clauses
- [ ] Backlinked from at least one existing article
- [ ] Referenced from its project MOC
- [ ] Images properly embedded
- [ ] **`_concepts/` only — source-diversity check:** majority of `## Appears In` instances must predate this session; if majority are same-session articles, route to `wiki/_drafts/` (see Step 5 falsification gate)

**Quality hooks (soft flag — Pending Review):**
- [ ] Summary argues rather than describes
- [ ] Open Questions are genuine gaps, not rhetorical
- [ ] Connections explain the nature of each link
- [ ] No unverified architectural claims — codebase claims must be sourced from code or raw/, not derived from another wiki article; flag unverified claims in Open Questions

**Source file hook (after all hooks pass):**
- [ ] Update the source raw file's `compiled:` field from `false` to `true` — this is the final write of a successful compile run; an agent reading a raw file with `compiled: false` knows it has not yet been processed; `compiled: true` means a wiki article exists for this source

Log every violation: `HOOK FAIL [file.md]: [type] — [issue] — [fix]`

---

### Step 3 — Spreading activation

For any changed neighborhood: update Summary, Details, Connections, Open Questions as needed.

One new or updated source must ripple to at least 3–5 articles total. Traverse Connections two hops outward and enrich neighbors where the new content adds value. Run hook enforcement on every updated article.

**Activation justification:** Before drawing each spreading activation link, verify three fields: SHARED_CONCEPT (a term that exists or could exist as a vault node), DIRECTIONAL_REASON (a specific asymmetry between source and target), SPECIFIC_CONSEQUENCE (what a human reader would lose without the link). If any field cannot be completed honestly, do not draw the link — log the rejected candidate in the session audit's ## Rejected Activations section instead. The Connections section of each article is the accepted-activation record; the session audit is the rejected-activation record.

**Cross-domain gate protocol:** When a candidate link connects articles from different MOC domains (determined by comparing `project:` frontmatter of source and target), apply this routing based on justification strength:

1. **Confidence classification** — after completing all three justification fields, classify strength:
   - All three fields completed with high specificity (concrete concept, clear asymmetry, precise reader loss) → confidence 0.90+
   - Two fields strong, one weak or vague → confidence 0.75–0.89
   - One field strong or any field cannot be completed → confidence < 0.75 (below threshold)

2. **Routing by confidence:**
   - Confidence ≥ 0.75 → **do not write to Connections yet**; append one entry to `Vault/data/spreading-activation-queue.ndjson` and add `validation_pending: true` to the article's frontmatter
   - Confidence < 0.75 → log as activation_rejected in session audit; do not queue

3. **Queue entry format** (one JSON object per line, append-only):
   ```json
   {"id":"sa-<YYYYMMDDTHHmmssZ>","ts":"<ISO-8601>","source":"[[slug]]","target":"[[slug]]","shared":"<concept-name>","flows":"<source> → <target>: <asymmetry>","without":"<specific reader loss>","confidence":<float>,"session":"<session-slug>","domain_pair":"<domain-a>↔<domain-b>"}
   ```

4. **Same-domain links** are not gated regardless of confidence — complete the three-field check, then commit directly to Connections if all fields pass.

The Validation Gate drains the queue: {{OWNER}} reviews each proposed cross-domain link and accepts (link gets written to Connections) or rejects (encoded as a negative constraint). An article with `validation_pending: true` in frontmatter has at least one proposed cross-domain link awaiting approval.

If spreading activation only creates one new article, ask why — a single-article compile without neighborhood updates is a graph failure.

---

### Step 4 — Update MOCs

Every new article must be added to its domain MOC in the same compile run.

**One MOC per domain** at `wiki/_mocs/[domain-name]-moc.md`. The full domain list is in vault.config.yaml.

**Required MOC structure:**
```markdown
## The Argument
[2–3 sentences: what is this domain, what is its central tension?]

## Core Articles
[3–5 foundational articles with one clause on why each is foundational]

## Topic Clusters
[Articles grouped by sub-theme, each cluster with a 1-sentence description]

## Cross-Domain Connections
[Links to other MOCs with explicit reason an agent navigating this domain needs the other]

## Synthesis Claims
[2–4 claims visible at the MOC level but not within individual articles]

## Open Territory
[Genuine gaps: what should exist here that doesn't?]
```

A MOC that is only a list of articles has failed. It must make a claim. If a cluster exceeds 8 articles, split it.

**Mandatory removal test before adding any new Synthesis Claim:**

Before writing a new Synthesis Claim to a MOC, ask: "If this MOC were removed, would the domain articles still collectively answer the domain's central question, or would a reasoning gap remain?" If the answer is "reasoning gap remains," the MOC is argumentative and the claim belongs. If the answer is "navigation loss only," the MOC may be routing — the claim should not be added until the MOC's argument is restated.

**End-of-update argument audit (required after all article additions to a MOC):**

After all articles for a compile run have been added to a MOC, read the MOC's `## Synthesis Claims` section as a unit and apply the removal test to the argument as a whole:

> "If this MOC were removed, would the domain articles still collectively answer the domain's central question — or would a reasoning gap remain?"

This check is distinct from the per-claim removal test above. Batch compile runs are the highest-risk moment for MOC argument degradation: each individual article addition passes the per-claim check, but the cumulative effect can shift Synthesis Claims from a coherent position to a collection of loosely related observations. If the argument has drifted toward description: restate The Argument section before committing.

---

### Step 5 — Write or update concept articles

Concepts appearing substantively in 3+ articles across 2+ projects get their own article in `wiki/_concepts/` using templates/concept.md.

Each concept article must:
- Define the concept precisely in the context of this vault
- Explain why it matters across projects
- List every article using it under `## Appears In`, with one clause on how that article applies the concept
- Link to the MOC of every domain it appears in

**Falsification gate (required before any `_concepts/` article is committed to `wiki/_concepts/`):**

Ask and record the answer to: *"What would have to be true in practice for this to be wrong, and has {{OWNER}} encountered it?"*

- If the answer is "nothing I would encounter" or "I haven't tested it" → write the article to `wiki/_drafts/[slug].md` with `status: draft`, add a `## Falsification Status` section noting the gap, and surface it in `## Pending Review` in INDEX.md. It can be promoted to `_concepts/` when a practice instance exists that could have falsified the concept but didn't.
- If a genuine falsification instance exists → record it in `## Open Questions` or `## Details` as the confirming case.
- Design commitments (principles {{OWNER}} has chosen to adopt, not empirical claims about how systems behave) are not concept articles. They belong in a domain-specific article or a principles document. The test: would the concept be false if practice went differently, or is it a chosen value? If the latter, it is not a `_concepts/` candidate regardless of how many inbound links it has.

**Source-diversity check (hard fail for `_concepts/` — blocks commit):**

Before committing a `_concepts/` article, check the `## Appears In` instances:
- Count instances whose source articles predate this session vs. instances created or substantially edited in this session.
- If majority of `## Appears In` instances are same-session articles: the concept's "cross-domain evidence" is circular — the spreading activation that generated those links was driven by the same session that generated the concept. Block the commit; route to `wiki/_drafts/` instead.
- A concept grounded primarily in pre-existing articles that were not written to fit it is a candidate for `_concepts/`. A concept grounded primarily in articles written in the same session is a refined idea, not a tested concept.

**Third failure mode — accurate claim, misattributed evidence:**

An article can fail source-diversity not because its evidence is circular but because its self-description of that evidence is inaccurate. The article may log a prior independent instance as "same-session." The fix is correct attribution of existing evidence, not new evidence.

When source-diversity gate fires: **verify compile dates of each `## Appears In` instance independently** before routing to `_drafts/`. If the dates show prior independent compilation, the gate fired on a self-description error. Correct the Appears In entries and re-evaluate.

Three failure modes summary:
- **Circular evidence** — Appears In instances were written in the same session; fix: accumulate prior evidence
- **Misattributed evidence** — instances are prior and independent but misdescribed; fix: correct attribution, verify dates
- **Unfalsifiable claim** — claim is too abstract to encounter a falsifying instance; fix: restate at lower abstraction, or route to principles document

---

### Step 6 — Update indexes

**wiki/_index/INDEX.md** — master agent entry point:
- `## Pending Review` — nightly drafts awaiting {{OWNER}} review
- `## Recent Additions` — date + what changed + what it connects to
- `## Projects` — one line per project linking to its MOC
- `## Suggested Next` — top stubs prioritized by score (inbound links × cross-domain reach × synthesis potential)

**wiki/_index/MOC-INDEX.md:**
- Every MOC with its `## The Argument` text verbatim
- Cross-domain connection map: which MOCs link to which, and why

**wiki/_index/INSPIRATION.md:**
- Every image: descriptive filename, one-line agent briefing, theme tags, linked articles
- Grouped by theme

---

### Step 7 — Lint (run only when explicitly asked)

Follow the lint skill exactly. Lint is a standalone inspection layer on its own cycle — do not embed it inside a compile run.

---

### Step 8 — Commit

```
git pull --rebase
git add wiki/
git add -f raw/          # force-add raw/ source files with updated compiled: field
git add -f Vault/data/   # force-add operational data files if modified this run
git commit -m "compile: [brief one-line description]"
git push
```

Never stage: `templates/`, `raw/` (except source files with flipped `compiled:` fields), `Vault/` (except `Vault/data/` operational files written this run: spreading-activation-queue.ndjson). No other raw/ changes should be committed.

---

## Output Format

```
COMPILE REPORT — [date]
────────────────────────────────────────
Articles created:           N
Articles updated:           N
MOCs created/updated:       N
Concept articles:           N
Images processed:           N
Hook violations fixed:      N
Hook violations flagged:    N  ← needs {{OWNER}} review

Stub links created (gaps to fill):
  → [[article-name]] — from: [source article]

Spreading activation ripple:
  → [new source] touched N downstream articles: [list]

Validation queue entries added:
  → sa-<id> [[source]] ↔ [[target]] · <domain_pair> · conf <float>

Suggested next raw/ additions:
{{DOMAIN_RAW_SUGGESTIONS}}

────────────────────────────────────────
```

After the report, ask: "Run full lint check now, or save for later?"

---

## Known Failures

- **Single-article compile** — one article created, no neighbors updated; the graph grows heavier without growing more connected; spreading activation is not optional
- **Hook enforcement as a final step** — violations compound between writes; hook enforcement must run after every individual write, not once at the end
- **Committing {{OWNER}}-owned files** — templates/, raw/ (beyond compiled: flips), and operational config files are never staged
- **Stale MOC** — new article added without updating its domain MOC; the primary agent entry point drifts behind; over multiple runs a MOC becomes a list rather than an argument
- **Orphaned new article** — new article with no inbound backlink; hook enforcement catches it but the fix (finding an existing article to backlink from) is easy to skip under time pressure
- **Summary describes rather than argues** — a Summary that lists what an article covers rather than making a claim; the quality hook catches this but requires judgment, not mechanical detection
- **Spreading activation stopped at one hop** — the instruction is two hops outward; articles two hops from the new source often gain the most from enrichment because they are less obviously connected

---

## Theory and Concepts

- [[skill-layer-architecture]] — why this skill exists in the graph; the four-layer hierarchy; theory/skill distinction
- [[agent-operated-knowledge-systems]] — the theoretical frame: the vault compounds because compilation converts raw thinking into graph-connected knowledge
- [[small-world-topology]] — the structural goal every compile decision serves; new articles should shorten traversal paths, not add weight
- [[spreading-activation]] — the compilation mechanism: one new source ripples through 3–5 articles; the graph grows through connection, not accumulation
- [[hook-enforcement]] — the inline integrity layer running after every write
- [[moc-as-argument]] — the removal test as the operative standard for MOC quality: remove the MOC and check whether a reasoning gap remains (argumentative) or only navigation loss (routing)
- [[stub-as-signal]] — why stubs are intentional and never removed to satisfy hooks
- [[observability]] — the principle that every compile decision serves: the vault must be inspectable and correctable at every layer
