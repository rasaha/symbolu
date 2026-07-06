# B1.3 Concrete-Object LLM Judged-Modulation — Generation & Semantic-Baseline Spec

## 1. Scope and status

Specification only. **No evidence stimuli generated** (illustrative examples in §12 are explicitly marked
**NOT FINAL STIMULI**) · **no judging · no scoring · no EVIDENCE_FREEZE · no positive label earned · prior
results unchanged.** Specifies the final generation/arm-construction artifacts and the semantic-only baseline
construction for the concrete-object LLM judged-modulation study. **Structure, not validated meaning.**

**Hypothesis (unchanged):** dictionary meaning fixes the object; varṇa/vṛtti supplies a modulation-field, not a
definition; LLM judges assess whether the **real** varṇa-derived modulation better fits the fixed
object-function than control modulations.

## 2. Final stimulus unit

Each rendered comparison item carries: `item_id` · `target_word` · `dictionary_anchor` · `neutral_context` ·
`comparison_id` · `left_option` · `right_option` · hidden `left_arm`/`right_arm` · `position_seed`
(randomized position) · `metadata` (tier, object_family, generation_seed, source files). The pair
(`left_arm`,`right_arm`) is stored in a private truth-map, revealed only at scoring.

## 3. Constrained modulation template

Fixed 4-tag format, identical for every arm:

> *"Within the fixed meaning, this object is modulated by [tag1], [tag2], [tag3], and [tag4]."*

Rules: **exactly four tags** · **no full poetic paragraph** · **no Sanskrit/varṇa terminology visible** ·
**no target word repeated inside the option** · **no dictionary-definition restatement** · **no arm-specific
syntax** · **same punctuation and structure across all arms**.

## 4. Field-tag extraction rule

Converting a varṇa sequence into four tags is **deterministic and seeded**:

- Map the target word → phoneme string → varṇa sequence via the **bound G2P→varṇa pipeline**
  (`varna_lens`, cmudict), identical to B1.1/B1.2.
- For each varṇa in composition order, take its **pole gloss** from the frozen bridge pool
  (`b1_2_varna_bridge_pool.json`, 34 entries) under the **fixed read_op pole rule** ("zero free choices").
- **Reduce** each pole gloss to a **≤4-word neutral field tag** by a fixed reduction rule (lowercase; strip
  Sanskrit labels / "binding"/"liberating" wording; take the head noun-phrase; no synonyms substituted).
- **Take the first four** tags by composition order; if fewer than four distinct varṇas route, apply the
  **deterministic backfill** (next varṇa in sequence; if still short, repeat the seeded pool draw used by
  R_random — recorded, never hand-chosen).
- **No hand-polishing per item · no dictionary meaning input for A_real · same extraction method for every
  arm.** Ranking = composition order; tie-break = lexicon_key ascending. Unknown/missing varṇas → skipped
  deterministically, logged.

## 5. `A_real` construction

Target word's **real** varṇa sequence → fixed varṇa→tag extraction (§4) → **exactly four tags**. **No
dictionary anchor is used to choose tags. No post-hoc editing.** This is the reference arm.

## 6. `R_deranged` construction

Another word's varṇa-derived tags, assigned by a **frozen derangement π (π(w)≠w)** fixed **before** judging,
matched by broad category/length **only where the match is deterministic** (else nearest by frozen order).
Tests **object-specificity**. **No cherry-picking**, no obvious-opposite or obviously-favorable pairing.
*(Crux: B1.1/B1.2 found `R_deranged ≈ A_real`.)*

## 7. `R_scrambled` construction

Target word's **own** varṇas, **order-disrupted** by a recorded **deterministic scramble seed** (forces a real
order change), then the same §4 extraction over the scrambled sequence. Tests **order/structure**. **Critical**
given the prior automated `scrambled ≈ real` (cosine 0.967).

## 8. `R_random` construction

Four tags **sampled from the global field-tag pool** (all bridge-pool glosses reduced by the §4 rule) using a
**fixed seed**, excluding the word's own varṇa tags. Tests **generic symbolic tag fit** (does any coherent tag
set suffice?). **No dictionary input.**

## 9. `X_neutral` construction

A **neutral / no-varṇa** option: four generic non-modulating filler tags (or a bare no-modulation rendering,
per final design), carrying **no** varṇa-derived content. It tests whether **modulation adds any value at
all**. **It must not accidentally become a stronger dictionary baseline** — it is *content-free* (generic
filler), whereas the **semantic-only baseline (§10) is dictionary-derived object-function content**. The two
are kept **separate**: `X_neutral` = "does any modulation beat nothing"; semantic baseline = "does varṇa beat
ordinary object semantics".

## 10. Semantic-only baseline construction

A **dictionary-derived object-function baseline**: from the **dictionary anchor / object function only** (no
varṇa input), produce **four tags in the same format** by a fixed rule (extract the anchor's function head +
salient object properties; e.g. WordNet gloss/hypernym-derived function words, deterministic). Examples:

- `knife` → *cutting, edge, separation, precision*
- `cup` → *holding, containment, receiving, use*

**Purpose:** if the semantic-only baseline **matches or beats** `A_real`, the Symbol-U-specific claim **fails** —
the "modulation" is re-derivable from ordinary object semantics and adds nothing.

## 11. Baseline-vs-`A_real` comparison

The semantic baseline is a **required check**, not optional. `A_real` must **beat or add beyond** it. If
`A_real` wins **only because it restates object function** (i.e., its tags coincide with the dictionary-derived
function tags), that is a **fail**, not a signal.

## 12. Draft examples — NOT FINAL STIMULI

> **These are illustrative only. NOT FINAL STIMULI. NOT EVIDENCE.** Tags below are hand-sketched to show
> *shape*, not produced by the frozen extraction pipeline.

- **knife** — A_real: *"Within the fixed meaning, this object is modulated by drive, boundary, focus, and
  release."* / semantic-baseline: *"…modulated by cutting, edge, separation, precision."*
- **cup** — A_real: *"…modulated by holding, openness, offering, and return."* / X_neutral: *"…modulated by
  aspect, factor, feature, and element."*
- **rope** — R_scrambled: *"…modulated by binding, tension, pull, and hold."* (same tags, order-disrupted).
- **bridge** — R_deranged (from another word): *"…modulated by warmth, rest, shelter, and ease."*
- **wall** — R_random: *"…modulated by hope, motion, yielding, and search."*

Illustrative shape only; final tags come from the deterministic pipeline (§4) over the frozen word list.

## 13. Artifact reproducibility

All templates **JSON-serializable**; **seeds recorded**; **source files recorded** (bridge pool, lexicon,
word list, derangement map); **hash-bound at the actual evidence freeze**; **generated final stimuli saved
before judging**; **no manual mutation after hash binding**.

## 14. Style-audit interface

Generated artifacts must feed the four gates of
`b1_3_concrete_object_llm_style_audit_protocol_draft.json`: **style-parity**, **style-tell**,
**denotation-leakage**, **quality-parity**. **No judging until all audits pass**; fixes are global/template-
level only, never per-item.

## 15. Scoring interface

Output columns for scoring (feeds `b1_3_concrete_object_llm_scoring_protocol_draft.json`): `item_id` ·
`target_word` · `primary_or_secondary_or_diagnostic` · `comparison_id` · `arm_left` · `arm_right` ·
`option_left` · `option_right` · `position_seed` · `generation_seed` · `dictionary_anchor` · `neutral_context`.

## 16. Freeze-readiness criteria

Ready only if: **arm rules deterministic enough to generate final stimuli** ✔ · **semantic baseline rule
specified** ✔ · **no per-item hand tuning required** ✔ · **artifacts can be hash-bound** ✔ · **generated
stimuli can be audited before judging** ✔. (Ready-as-spec; not yet frozen — §17 blockers remain.)

## 17. Remaining blockers after this spec

Final screened primary object list · actual final stimulus generation · actual style-audit execution/result ·
final judge model list · final scoring script · final thresholds · manifest hash binding · explicit
EVIDENCE_FREEZE declaration.

## 18. Decision

```
DECISION: GENERATION_BASELINE_SPEC_READY
```

The stimulus unit, constrained template, deterministic field-tag extraction, all five arm constructions, and
the dictionary-derived semantic-only baseline (with the "if it matches A_real, the claim fails" rule) are
specified, deterministic, seedable, and hash-bindable, and feed cleanly into the style-audit and scoring
interfaces. This is not `GENERATION_BASELINE_SPEC_HIGH_RISK_NEEDS_REVISION` (the extraction is deterministic
and the baseline makes even a positive interpretable) and not `GENERATION_BASELINE_NOT_SPECIFIABLE_CLOSE_LINE`
(the generation and baseline are fully specifiable from existing frozen artifacts). No final stimuli were
generated; the §12 examples are illustrative only.

## 19. Final status block

```
document:                    B1.3 concrete-object LLM GENERATION & semantic-BASELINE spec (specification only)
decision:                    GENERATION_BASELINE_SPEC_READY
template:                    fixed 4-tag "modulated by [t1],[t2],[t3],[t4]" — identical across arms
field-tag extraction:        deterministic, seeded, bridge-pool pole glosses; no dictionary input for A_real
arms specified:              A_real / R_deranged / R_scrambled / R_random / X_neutral (deterministic, seeded)
semantic-only baseline:      dictionary-derived object-function tags; if it matches A_real, claim FAILS
final stimuli generated:     NO (§12 examples illustrative, NOT FINAL, NOT EVIDENCE)
ran LLM judges / scoring:     NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL: NOT earned
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
next:                        screen final object list, generate stimuli, run style audit, then freeze blockers
```

**Structure, not validated meaning.** The generation, arm-construction, and semantic-only baseline rules are
specified deterministically for the concrete-object LLM judged-modulation study; no final stimuli were
generated, no judges were run, nothing was scored, prior nulls and closures stand, Track B remains BLOCKED, and
EVIDENCE_FREEZE is not declared.
