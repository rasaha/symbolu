# Varṇa Symbolic Resonance — B1.12 Instrument Refinement · PREREGISTRATION **V2 (DRAFT)**

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`
**Status: DRAFT_FOR_REVIEW — NOT frozen, NOT controlling. No words selected. Nothing run.**

This draft proposes a *next-version* evaluation protocol motivated by the completed v1 crossover
(`results/b1_12_symbolic_resonance_multillm_v1/`) and its disagreement audit (`B1_12_BSR_DISAGREEMENT_AUDIT.md`).
It **does not modify** anything frozen. The v1 controlling prereg (`VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md`), the
v1 verdict/role freeze (`B1_12_BSR_VERDICT_AND_ROLE_STABILITY_FREEZE.md`), the frozen mappings
(`frozen/varna_native_stage1_merged_v3.json`), and the recorded v1 result (`SIGNIFICANT_ROLE_DEPENDENCE`) all stand
as-is. V2, if adopted and frozen, is a **separate instrument** run on a **new fresh word set**.

---

## 0. Why a v2 at all

The v1 crossover produced a *methodological-limitation* result, not a verdict on the mappings. The audit traced its
`SIGNIFICANT_ROLE_DEPENDENCE` to three structured, correctable causes:

1. a **global scorer-strictness offset** (~+10 pts, Qwen over Mistral) that persists even when both models pick the
   identical relationship — a calibration difference;
2. an **unspecified score-scale convention for `opposition`/`resolution`** (opposition: Mistral 40.9 vs Qwen 66.7) —
   a rubric specification gap;
3. **under-enforced no-supplementation control at scoring** — the scorer accepted invented narrative bridges
   (dīpa#1: "lamp reveals unpleasant truths → revulsion" → 50).

Additionally, the author→scorer crossover design introduces **anchoring**: the scorer never judged the raw word +
mapping independently — it reacted to a narrative the *other* model had already assembled.

V2 targets these directly. **Its purpose is to make the instrument evaluator-reliable; it is not designed to make
more words "succeed."** No threshold is loosened.

---

## 1. Core V2 changes (the reliability fix) — proposed for adoption

### 1.1 Fully independent judgments (remove author→scorer anchoring)
- Each model receives the **same** frozen bare-word definition, the **same** exact frozen mapping(s), and the
  **same** rubric.
- Each model independently produces, for every occurrence: `supporting_evidence`, `opposing_evidence`,
  `relationship_type`, and `score` — **blind to the other model's output**. No model scores another model's
  narrative.
- Agreement is computed *after the fact* between two complete, independent judgments. This measures evaluator
  agreement without author-induced anchoring. (The v1 crossover is retained as the prior comparison point.)

### 1.2 Tighten the 25-vs-50 boundary (fixes Causes 1 & 3)
Re-anchor the scale so "requires interpretation/supplementation" cannot land at 50:
- **100** — the mapping is inherent in / directly characteristic of the ordinary meaning.
- **75** — strongly implied by the ordinary meaning; little interpretive work.
- **50** — a natural but nonessential association most evaluators would recognize **without constructing a story**.
- **25** — reachable **only** through metaphor, an external actor, contextual supplementation, or a special
  scenario. **If the adjudication says "requires external interpretation/context/inversion," the score is 25, not
  50.**
- **0** — no defensible relationship without importing outside meaning.
Each scale point gets ≥1 worked exemplar in the frozen prompt (calibration anchors).

### 1.3 Enforce the no-supplementation firewall *at scoring* (fixes Cause 3)
Explicit scorer instruction: *"If accounting for the mapping required inventing a causal or narrative chain that is
not part of the bare word's ordinary meaning, score 0 — no matter how plausible the chain is."* The model's own
`opposing_evidence` flagging an invented bridge must force ≤ 25.

### 1.4 Specify the `opposition`/`resolution` score convention (fixes Cause 2)
The single biggest structured disagreement was that the rubric never said whether a clean opposition scores high or
low. V2 must state one convention explicitly and freeze it **before** any run. Two candidate conventions to choose
between at freeze time (documented, not yet decided):
- **(2a) Oppositional relationships are scored on their own strength** — a clean, ordinary-meaning opposition
  (love ↔ hatred) is high; a strained one is low. Requires that the *report* separate "resonance-by-opposition"
  from "resonance-by-implication" so they are never silently summed.
- **(2b) Oppositional relationships are capped** (e.g. ≤ 50) because "the word *opposes* the mapping" is a weaker
  form of "the word *accounts for* the mapping" than embodiment/implication.
Whichever is chosen is frozen and applied identically to both models.

### 1.5 Keep everything that worked (unchanged from v1)
Frozen mappings; pronunciation-derived native Stage-1 decomposition; occurrence-level scoring; bidirectional
(supporting + opposing) evidence; the 10-type relationship taxonomy; component-level anti-rescue (holistic score
may not repair weak components); separate reporting of weak components; deterministic decoding; two hard gates
(input-hash match, no model-family substitution); glosses read only at scoring time.

### 1.6 New fresh word set
A **new** precommitted, attested-Sanskrit word list (FRESH_UNINSPECTED, category-balanced) — the v1 20 words are
**not** reused (they are now inspected). Selection is a separate gate, done before any scoring, glosses hidden
during selection.

---

## 2. Optional module — two-axis scoring (DBR / EPR) — **NOT adopted; decision required**

The audit and cross-experiment observation suggest v1 conflates **two constructs**: direct bare-word meaning vs. an
experiential/process reading. A two-axis scheme could expose rather than hide this:
- **DBR — Direct Bare-Word Resonance:** is the mapping inherent in / characteristic of / strongly implied by the
  ordinary meaning of the word itself? (0/25/50/75/100)
- **EPR — Experiential-Process Resonance:** does encountering/using/undergoing the referent naturally *instantiate*
  the mapped process? (0/25/50/75/100)

Then classify: high-DBR = semantic; low-DBR/high-EPR = process; both-high = dual; both-low = none.

**⚠ Adoption risk (why this is NOT in the core fix).** As illustrated in the source proposal, EPR would score
*nose → attachment via scent/memory* and *boat → striving toward a destination* at 50 — these are exactly the
invented bridges v1 correctly penalized. An unbounded EPR axis is a **resonance-inflation engine**: nearly every
noun participates in *some* process. If EPR is adopted it **must** carry a hard guard:
> EPR counts a process only if that process is **intrinsic and necessary** to the referent (a boat's function *is*
> transit), **never** merely associable (a nose is not *for* attachment). Associable-only processes score EPR 0.

**Open decision:** adopt DBR/EPR with the intrinsic-process guard, or keep a single tightened DBR axis (§1.2). The
core reliability fix (§1) does not depend on this choice.

---

## 3. Separate future study — distinguishing the two hypotheses — **out of scope for the reliability fix**

The strongest recurring cross-experiment pattern is *abstract/process words resonate better than concrete objects*.
This has **two** explanations that the reliability fix (and even DBR/EPR) **cannot** separate, because both predict
abstract > concrete:
- **H-transform:** varṇas encode cognitive transformations, so process/experiential words fit intrinsically.
- **H-neighborhood (simpler):** abstract psychological words have richer semantic neighborhoods, so an LLM can
  construct a plausible link to *any* mapping more easily than for a narrowly-defined concrete noun.

Distinguishing them requires a **discriminating control**, e.g.:
- **Shuffled/alternate-mapping baseline:** score each word against its *correct* mapping and against *wrong*
  mappings. H-transform predicts correct ≫ wrong for the same word; H-neighborhood predicts abstract words score
  high on wrong mappings too (they fit anything).
- **Matched concrete pairs:** concrete *process/functional* words (boat, bridge, lamp — things *for* doing) vs
  concrete *static* words (stone, crow, nose) — H-transform predicts the process nouns resonate even though both
  are concrete.

This is a **bigger, separate preregistration** (it is the study that could actually be conclusive about the
mappings). It is noted here so it is not confused with the reliability fix; it is **not** part of V2's core.

---

## 4. What must NOT change
- Do **not** rescore the v1 20 words or replace the v1 report.
- Do **not** lower thresholds to make more words pass.
- Do **not** add mythological/etymological/cultural narrative to the ordinary-meaning constraint without a
  separate, explicitly-labeled axis.
- Do **not** collapse direct-meaning and experiential-process readings into one optimistic number.
- Do **not** modify the frozen mappings, parser, v1 prereg, or the v1 verdict/role freeze.

## 5. Readiness / gate status
`DRAFT_FOR_REVIEW`. Before anything runs, in order: (1) resolve the §1.4 opposition-convention choice and the §2
DBR/EPR decision; (2) freeze this document as `VARNA_SYMBOLIC_RESONANCE_PREREG_V2.md` with a content hash; (3)
precommit a new fresh word list under it; (4) only then execute. No word has been selected and no model has been
called for V2.

## 6. Provenance
Motivated by `results/b1_12_symbolic_resonance_multillm_v1/` (v1 run) and its `B1_12_BSR_DISAGREEMENT_AUDIT.md`.
No frozen input, controlling preregistration, freeze, or prior artifact was modified by writing this draft.
