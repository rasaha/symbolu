# B1.6 — Symbol-U Generative Utility — Pre-Registration (Path B)

**Status:** Pre-registration (docs-only). A **new, separate track** — not a continuation or rescue of B1.4b′ or
B1.5. No code, no generation run, no dataset (beyond one `TOY_ONLY` illustration).
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`, no `L1_L2_L3_ATTRIBUTE_SIGNAL`. Original B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.**

Related: `B1_4B_PRIME_SCREENING_OPERATOR_COMMANDS_EXECUTED.md` (`880ad1a`, NULL),
`B1_5_THREE_CLUE_WORD_RECOVERY_PREREG.md` (`cde0a9c`),
`B1_4B_PRIME_WORD_IDENTITY_BLINDING_CLARIFICATION.md` (`6edf3ea`),
`SYMBOL_U_L2_VALIDATION_RULEBOOK.md`, `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md`.

---

## 1. Purpose

This tests a **different claim** from every prior track:

- **B1.4b′** asked: *do phoneme/operator (Stage A′ → F-3) structural features **blindly predict** a concept's
  McRae attribute vector?* → **`NULL_RETURN_BOTTOM`** (all arms at chance). **That result stands.**
- **B1.5** asks: *can a Symbol-U scoring method **rank/recover** an intended target word from three semantic
  clues, above chance and controls?* → a blind **decoding/ranking** test; low prior.
- **B1.6 (this document)** asks a narrower, different question: *used as a **generative/interpretive scaffold**
  — a structured prompt template, not a blind decoder — does Symbol-U **improve the quality** of generated
  interpretations under blinded evaluation, versus plain and generic-structured baselines?*

B1.6 does **not** test whether phonemes carry meaning. It tests whether the Symbol-U **procedure**, as a
scaffold for a generator, produces outputs that blinded judges rate higher than baselines — a statement about
**task utility of a scaffold**, nothing more. Drafting B1.6 does **not** erase, weaken, or reinterpret the
B1.4b′ null (§18).

## 2. Hypothesis

**H1 (narrow, candidate):** using a frozen Symbol-U scaffold (varṇa/phoneme sequence + polarity/profile table +
transformation template, **no dictionary lookup**) to prompt a generator yields interpretations that blinded
judges rate **higher** than a plain prompt **and** a generic structured prompt **and** a randomized-scaffold
control.

**H0 (null, expected default given priors):** any quality gain from the Symbol-U scaffold is explained by
**generic prompt structure** (the scaffold merely imposes organization), by **verbosity**, by **mystical
register**, or by a **randomized scaffold** doing just as well — i.e. the specific varṇa content adds nothing a
generic structured prompt would not.

The burden is entirely on the Symbol-U arm to beat **all** of: plain, generic-structured, randomized-Symbol-U,
and a semantic/LLM baseline (§7, §10, §13).

## 3. What this experiment CAN prove

Within a constrained, blinded generation-and-rating setup, and **only** as a statement about task utility:

- **Task-specific generative utility** — whether Symbol-U-scaffolded outputs are rated higher on this task.
- **Scaffold usefulness** — whether the scaffold, as an operational prompt structure, helps a generator produce
  interpretations judges prefer.
- **Rubric-measured quality improvement** — a measurable, pre-registered rubric delta over baselines.
- **Human and/or LLM-judge preference** — win rates / preference under blinded evaluation.

All of the above are claims about **usefulness on this task**, not about truth, ontology, or meaning.

## 4. What this experiment CANNOT prove

It cannot prove, and no label may imply: an **ontology**; **Sanskrit semantic truth**; that **phonemes/varṇa
encode meaning**; that **B1.4b′ was wrong** (it stands); **dictionary semantics**; `ONTOLOGICAL_SIGNAL`;
`L1_L2_L3_ATTRIBUTE_SIGNAL`; or **universal validity** beyond this task and dataset. A win here is **task
utility of a scaffold** under blinded rating — explicitly **not** validated meaning. If a generic structured
prompt matches the Symbol-U scaffold, the effect is generic structure, not Symbol-U
(`GENUTILITY_COLLAPSES_TO_GENERIC_STRUCTURE`).

## 5. Task design

Each **task item** asks a generator to produce a short **interpretation** for a given prompt object. Task types
(a frozen mix, spanning abstract and concrete):

- **Word interpretation** — an interpretive reading of a given word.
- **Name interpretation** — a reading of a personal/place name.
- **Concept interpretation** — a reading of an abstract concept.
- **Symbolic interpretation** — reading a symbol/glyph/short symbolic phrase.
- **Metaphor generation** — produce an evocative metaphor for the object.
- **Contemplative reflection** — a short contemplative/meditative reflection prompt.
- **Brand naming** — an interpretive rationale for a candidate brand name.
- **Mantra-style composition** — a short mantra-style / sound-centred composition.

The set must include **both abstract items** (concept, contemplative, metaphor) **and concrete items** (word,
name, brand), so utility is not confined to one register. Each item specifies only the **object** and the
**task type** — never a target "correct" interpretation.

## 6. Dataset

- **Frozen set of 50–200 items**, hash-frozen **before any generation**. A **mix** across the §5 task types,
  abstract and concrete.
- **Fields per item:** `id`, `object`, `task_type`, `source`, optional `category`, optional `notes`.
- **No post-hoc edits** to items, objects, or task types after any generation or rating is seen.
- **Provenance** documented per item; license-clear objects only.
- **`TOY_ONLY` example permitted** for format illustration; it is not part of the frozen set and is never rated
  or counted as evidence.

**TOY_ONLY illustration (not a dataset; format only, not for scoring):**

| id | object | task_type | source |
|---|---|---|---|
| toy-1 | "river" | word_interpretation | TOY_ONLY |
| toy-2 | "Maya" | name_interpretation | TOY_ONLY |

*(Illustrative format only. Marked `TOY_ONLY`. Not frozen, not generated from, not rated, not evidence.)*

## 7. Generation arms

All arms generate for the **same items**, with **matched** model, temperature, max length, and target format
(§8). Each arm is a **prompt condition**; the generator is the same underlying model.

- **A. `SYMBOLU_SCAFFOLD`** — the candidate: prompt the generator with the **frozen Symbol-U scaffold** (§9):
  the object's varṇa/phoneme sequence, the polarity/profile table, CSR/STL dimensions, transformation rules, and
  the template — **with a strict no-dictionary constraint**.
- **B. `PLAIN_PROMPT_BASELINE`** — plain prompt: "interpret this object" with no scaffold. The floor.
- **C. `GENERIC_STRUCTURED_PROMPT_BASELINE`** — a **generic** structured prompt of matched length/organization
  (e.g. "consider form, sound, associations, transformation; write a structured reading"), containing **no
  varṇa/Symbol-U content**. Isolates *generic structure* from *Symbol-U content*. **The critical control.**
- **D. `RANDOMIZED_SYMBOLU_CONTROL`** — the Symbol-U scaffold with **shuffled/relabelled** varṇa→profile
  mappings (same template, same length, structure destroyed). Tests whether the *specific* content matters.
- **E. `SEMANTIC_EMBEDDING_OR_LLM_BASELINE`** — a strong ordinary baseline: the generator prompted with
  conventional semantic/associative context (or a plain high-quality LLM interpretation). The benchmark a
  "useful" scaffold must at least match.
- **F. `ASTROLOGY_OR_SYMBOLIC_SYSTEM_BASELINE`** *(optional)* — an alternate symbolic system (e.g. an
  astrology-style / numerology-style scaffold) of matched form. Contextualizes any Symbol-U effect against a
  *different* symbolic scaffold; clearly **not** Symbol-U evidence and cannot emit a Symbol-U positive.

## 8. Prompt controls (strict; a breach → `GENUTILITY_INVALID_LEAKAGE`)

- **Same generator model, temperature, max length, and target output format** across all arms.
- **No arm labels reach the judges** — outputs are stripped of any marker of which arm produced them.
- **No self-praise / no meta-claims** in generated text (no "this Symbol-U reading is deep/true/ancient"); such
  leakage is stripped or the item is voided.
- **No system name leakage** — generated outputs must not name "Symbol-U", "varṇa", "astrology", etc., in a way
  that reveals the arm; a scrubbing pass + audit removes register giveaways where feasible, and any residual is
  logged.
- **No target/gold interpretation** is provided to any arm (there is none).
- **Judges never see** arm identity, the scaffold used, or another arm's output ordering (randomized).

## 9. Symbol-U scaffold definition (frozen)

The `SYMBOLU_SCAFFOLD` prompt is **frozen before generation** and consists **only** of structure-derived
material — **never dictionary definitions**:

- **Varṇa / phoneme sequence** of the object (via the frozen Stage A / Stage A′ decomposition where applicable).
- **Polarity / profile table** — the per-varṇa attribute/propensity profile (structural, not lexical meaning).
- **CSR / STL dimensions** — the declared structural dimensions used as scaffold axes.
- **Transformation rules** — the frozen operator/transformation description used to shape the reading.
- **No-dictionary constraint** — an explicit instruction that the reading must be built from the scaffold's
  structural profile, **not** from the dictionary meaning of the object.
- **Template** — a fixed output template (fields/sections) the generator fills.

The scaffold text, the profile table, and the template are **hash-frozen**; no per-item tuning. The randomized
control (arm D) uses the **same frozen template** with a shuffled profile table.

## 10. Evaluation rubrics

Each output rated on a fixed scale (**1–5** or **1–7**, frozen before rating) across these dimensions:

- **Coherence** — internally consistent, well-formed.
- **Usefulness** — helpful/actionable for the stated task.
- **Richness** — depth/texture of the interpretation.
- **Specificity** — tailored to *this* object, not generic.
- **Non-genericity** — not a template that fits any object (explicitly penalizes fill-in-the-blank vagueness).
- **Creativity** — originality of the reading.
- **Consistency** — coherent within itself and with the object.
- **Insight** — offers a non-obvious, valuable angle.
- **Aesthetic** — quality of expression.
- **Overclaim / hallucination penalty** — a **negative** dimension: fabricated etymology, false factual claims,
  mystical overreach, or unearned certainty **reduce** the score. High-confidence falsehood is penalized, not
  rewarded.

A **primary composite** (pre-declared weighting, or a pre-declared subset) is frozen before rating; the
individual dimensions are secondary/diagnostic.

## 11. Judges

- **Human blind rating** — preferred gold standard: raters see only the object, task type, and (blinded) output.
- **LLM-as-judge** — permitted **as a pilot / screening** signal only; a **different** model from the generator,
  never emitting a terminal truth claim on its own.
- **Mixed** — LLM-judge pilot to triage, human blind panel for any terminal claim.
- **Inter-rater reliability (IRR)** computed (e.g. Krippendorff's α / ICC); low IRR → `GENUTILITY_INCONCLUSIVE`.
- **Human evaluation may be deferred**, but the design must remain **fully compatible** with a later human panel
  (same items, same blinding, same rubric); an LLM-only pilot **cannot** emit a terminal `..._BEATS_*` label.

## 12. Primary metrics

Per arm, over the frozen items, with blinded ratings:

- **Mean rubric composite by arm** (and per-dimension means).
- **Pairwise preference** (forced-choice A-vs-B win rate) for the key contrasts.
- **Win rates** of `SYMBOLU_SCAFFOLD` vs `PLAIN_PROMPT_BASELINE`, vs `GENERIC_STRUCTURED_PROMPT_BASELINE`, vs
  `RANDOMIZED_SYMBOLU_CONTROL`, vs `SEMANTIC_EMBEDDING_OR_LLM_BASELINE`.
- **Effect sizes** (e.g. standardized mean difference / rank-biserial) for each contrast.
- **Confidence intervals** (bootstrap) on every metric.
- **Inter-rater reliability** (IRR) reported alongside.
- **Multiple-comparison correction** (Holm) across the control-contrast family.

## 13. Terminal labels

- **`GENUTILITY_SYMBOLU_BEATS_BASELINES`** — Symbol-U beats **all** of: plain, generic-structured,
  randomized-Symbol-U, **and** semantic/LLM baseline, on the pre-registered primary metric with correction and
  adequate IRR. **The only "win" label.**
- **`GENUTILITY_SYMBOLU_BEATS_PLAIN_ONLY`** — beats plain but **not** generic-structured (so the gain is
  structure, not Symbol-U content).
- **`GENUTILITY_COLLAPSES_TO_GENERIC_STRUCTURE`** — generic structured prompt matches/beats Symbol-U (effect is
  generic structure).
- **`GENUTILITY_RANDOMIZED_SYMBOLU_MATCHES`** — the randomized-scaffold control matches Symbol-U (specific varṇa
  content irrelevant).
- **`GENUTILITY_LLM_BASELINE_WINS`** — the semantic/LLM baseline matches/beats Symbol-U.
- **`GENUTILITY_NO_PREFERENCE`** — no arm reliably preferred / all within CI.
- **`GENUTILITY_HALLUCINATION_OR_OVERCLAIM_FAIL`** — Symbol-U's apparent quality is driven by overclaim/
  hallucination (the penalty dimension flips or dominates); not a genuine win.
- **`GENUTILITY_INCONCLUSIVE`** — low IRR / underpowered / no clean resolution.
- **`GENUTILITY_INVALID_LEAKAGE`** — a prompt-control (§8) or blinding breach.

**Hard rule:** `GENUTILITY_SYMBOLU_BEATS_BASELINES` may be emitted **only** if `SYMBOLU_SCAFFOLD` beats
**plain, generic-structured, randomized-Symbol-U, AND semantic/LLM** by the pre-registered margins with
acceptable IRR. Beating some but not all → the corresponding collapse/matches/wins label. **No
`ONTOLOGICAL_SIGNAL`, no `L1_L2_L3_ATTRIBUTE_SIGNAL`, no validated-meaning claim under any label.**

## 14. Thresholds (conservative, pre-registered)

- **Above plain** — primary-metric CI lower bound of the Symbol-U−plain contrast > 0, with correction.
- **Above generic structure** — a **pre-declared minimum margin** of Symbol-U over
  `GENERIC_STRUCTURED_PROMPT_BASELINE`; if generic structure ties/wins →
  `GENUTILITY_COLLAPSES_TO_GENERIC_STRUCTURE`. **This is the decisive control.**
- **Above randomized Symbol-U** — a pre-declared margin over `RANDOMIZED_SYMBOLU_CONTROL`; tie →
  `GENUTILITY_RANDOMIZED_SYMBOLU_MATCHES`.
- **Not worse than semantic/LLM baseline** to claim unique utility; if it ties/wins →
  `GENUTILITY_LLM_BASELINE_WINS`.
- **Overclaim guard** — if removing/penalizing the overclaim dimension erases the Symbol-U advantage →
  `GENUTILITY_HALLUCINATION_OR_OVERCLAIM_FAIL`, not a win.
- **IRR floor** — a pre-declared minimum IRR; below it → `GENUTILITY_INCONCLUSIVE`.
- All margins, the primary metric, the rubric weighting, the scale, the item count, and the judge protocol are
  frozen before any generation or rating is seen.

## 15. Pilot plan (tiny; no claim)

- **20–30 items**, **2–3 generations per arm**, plumbing + blinding + leakage-control validation only.
- **LLM-as-judge pilot-only** to check the rubric discriminates and the harness runs; **no terminal label / no
  truth claim** may be emitted from the pilot.
- A **synthetic positive control** (a deliberately better vs deliberately worse output pair) should confirm the
  rubric + judge *can* detect a quality difference when one exists — so a real null is informative, not a dead
  pipeline.

## 16. Full run plan

Before any evidence run: **freeze** the target item set, the arm prompts (including the Symbol-U scaffold and
template), the randomized-control seed, the rubric + weighting + scale, and the judge protocol; then an
**operator `EVIDENCE_FREEZE` declaration** — exactly the gated discipline used for B1.4b′. **Generation happens
only after the freeze.** Outputs are **blinded/packaged** (arm labels stripped, order randomized) before rating.
**No post-hoc tuning** of scaffold, items, rubric, or thresholds. Report the terminal label as-is.

## 17. Failure modes (explicitly anticipated)

- **Verbose-not-better** — the scaffold just makes outputs longer; controlled by matched length + non-genericity
  + specificity dimensions.
- **Generic-explains** — a generic structured prompt does as well (`..._COLLAPSES_TO_GENERIC_STRUCTURE`).
- **Randomized-matches** — shuffled scaffold does as well (`..._RANDOMIZED_SYMBOLU_MATCHES`).
- **Mystical-language preference** — judges reward mystical register per se; mitigated by the overclaim penalty,
  register-scrubbing, and human calibration.
- **Overclaim-creates-quality** — apparent depth is unearned certainty/fabrication
  (`..._HALLUCINATION_OR_OVERCLAIM_FAIL`).
- **LLM-recognizes-target-independently** — an LLM judge favors an arm because it independently "knows" the
  object; mitigated by blinding, human panel for terminal claims, and the semantic/LLM baseline arm.

## 18. Relationship to previous work

- **B1.4b′ remains `NULL_RETURN_BOTTOM`.** This document does **not** erase, weaken, or reinterpret it. B1.4b′
  was a **blind attribute-prediction** test; its null stands.
- **B1.5** is a **blind ranking/recovery** test (separate, low-prior). B1.6 is neither prediction nor recovery.
- **B1.6 is a different claim**: **generative utility of a scaffold** under blinded rating — an
  *interpretive-practice* utility question, not a *blind-signal* question. A B1.6 outcome — positive or null —
  says **nothing** about the B1.4b′ or B1.5 results, and vice versa. Even a `..._BEATS_BASELINES` here would be
  **task utility of a scaffold**, never validated meaning, never ontology, never a rescue of any prior null.

## 19. Guardrails

No `ONTOLOGICAL_SIGNAL`. No `L1_L2_L3_ATTRIBUTE_SIGNAL`. No Sanskrit privilege. No semantic-truth /
validated-meaning / "sound encodes meaning" claim. No rescue of Track B. No reuse-as-positive of any prior null.
A generative-utility win is a statement about **scaffold usefulness on this task only**. Original B1.4b remains
blocked. Track B remains blocked. **Structure, not validated meaning.**

## 20. Implementation status

**Docs-only.** No code, no generation run, no datasets are produced by this document — except a single
`TOY_ONLY` illustration (§6) that is never generated from or rated. No frozen artifacts are modified (Stage A /
`symbolu_neural` / Stage A′ / scorer / B1.3 / B1.4a / B1.4b / lexicons all untouched). Any future pilot or run
requires its own separate approval, its own freeze, and does not alter any prior result.

---

## Next gate

Docs-only pre-registration only. Next step (separate approval) would be a **tiny pilot harness** with the
blinding + leakage scans, matched-length controls, and a synthetic rubric positive control — **not** a real run.
No dataset is built and no generation is performed by this document.

> Symbol-U generative-utility prereg drafted docs-only. No generation run. B1.4b′ remains NULL_RETURN_BOTTOM.
> Original B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.
