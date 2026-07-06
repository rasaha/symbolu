# B1.2 Mapping-Fidelity Preregistration

## 1. Title and status

**B1.2 Mapping-Fidelity Preregistration** — the single authorized, final discriminative falsifier of the
corrected three-layer theory.

```
document:   B1.2 mapping-fidelity PREREGISTRATION (prereg only)
status:     NOT_RUN · NOT_FROZEN · NOT_AUTHORIZED_FOR_GENERATION_OR_JUDGING
authority:  one final authorized mapping-fidelity falsifier (per B1_2_MAPPING_FIDELITY_PREREG_DECISION.md)
```

This document specifies the study. It does **not** implement it, build packets, run models, judge, or score.

## 2. Non-rescue / locked-result clause

- B1.1 verdict remains **`RANDOM_OR_SCRAMBLED_MATCHES`**; `LIMITED_GENERATION_UTILITY` **not earned**.
- The B1/B1.1 **generation-utility** line is exhausted; B1.2 is **not** a continuation or rescue of it.
- Track B remains **BLOCKED**. Track G `RANDOM_POLARITY_EXPLAINS` and Track F `CORRECTNESS_DEGRADED` remain
  **preserved**.
- B1.2 does **not** validate ontology, Sanskrit privilege, or semantic truth. Its best possible outcome is a
  narrow `MAPPING_FIDELITY_SIGNAL` (discriminability within the frozen artifact system) — nothing more.
- No B1.2 result may reach back and alter B1.1. B1.1 may **not** be reused as a positive prior.
  **Structure, not validated meaning.**

## 3. Corrected three-layer theory under test

- **Layer 1 — raw varṇa mapping.** word → phoneme/varṇa skeleton. The substrate, not the meaning claim; not
  itself scored as success.
- **Layer 2 — dictionary semantic grounding.** word → its conventional semantic field (dictionary meaning,
  lexical category, semantic role). **Frozen before judging.** Anchors the signature to accepted meaning and
  prevents arbitrary varṇa poetry; not scored as success by itself.
- **Layer 3 — differential synonym-separation.** what makes the target word **distinct** from its near
  synonyms / category-neighbors — its word-specific signature. **Frozen before judging.** **This is the main
  target of B1.2.**

## 4. Research question

**Primary:** *Can the correct Layer-3 differential signature of a target word be distinguished from wrong but
equally fluent signatures, under blinded conditions?*

**Not** the question: does the bridge improve open-ended generation? (That was B1.1; it failed and is not
re-asked.)

## 5. What B1.2 can and cannot prove

**Can test:**

- mapping-fidelity **within this artifact system** — whether the target-specific differential signature is
  blind-distinguishable from wrong signatures;
- whether A_correct beats **near / mid / far** wrong signatures, and whether fit tracks semantic distance.

**Cannot prove (must not be claimed at any outcome):**

- ontology validation; Sanskrit truth or privilege; universal semantic truth;
- LLM-architecture validity; Track B unblocking; generation utility.

## 6. Study type

**Discriminative forced-choice / ranking study.** The primary endpoint is discrimination accuracy (correct
signature vs wrong signatures), **not** open-ended generation quality. No open generation is scored as a
primary endpoint.

## 7. Unit of analysis

The item is the **target word**. Each item bundles:

- **target word**;
- **frozen dictionary semantic field** (Layer 2);
- **near-neighbor confusion set** (the synonyms/category-neighbors Layer 3 must separate against);
- **A_correct** — the word's Layer-3 differential signature (frozen answer key);
- control signatures: **R_deranged_near**, **R_deranged_mid**, **R_deranged_far**, **R_same**, **R_domain**,
  **generic_symbolic**, and **dictionary_baseline** (optional, retained as a floor anchor if used).

## 8. Target word pool

- **Small enough for full hand audit** — every word's varṇa decomposition, Layer-2 field, and Layer-3
  signature manually verified stable and unambiguous.
- **Broad enough not to be cherry-picked** — a pre-registered, justified set spanning multiple semantic
  domains, not a handful of favorable words.
- **English G2P limitations acknowledged** — G2P→varṇa over English is lossy (forensic §4C); the pool must
  tolerate this and the risk is recorded as a threat to sensitivity, not silently ignored.
- **No post-hoc target replacement** — the word set is frozen before any output is seen; a word may not be
  swapped out after seeing results.
- **Sanskrit/IAST domain shift is excluded** from this B1.2 (it is a separate question requiring its own
  scoping memo; not a fix to B1.1).

## 9. Layer 2 construction (dictionary semantic grounding)

- The dictionary semantic field for each word is **created before judging** and **frozen**.
- **Source documented** (named dictionary / lexical resource; extraction rule recorded).
- **Same format for every word** (uniform fields: gloss, lexical category, semantic role).
- **No model output may influence Layer 2** — it is built from lexical sources only, never from generations.
- **Layer 2 is not, by itself, a success condition** — it is grounding, not the endpoint.

## 10. Layer 3 construction (differential signature — the answer key)

- Must **explicitly separate** the target word from its near neighbors (state what makes the target distinct,
  not merely what it evokes).
- **Frozen before judging** and hash-bound; **not tuned** after seeing any output or score.
- **Avoids generic universals** (clarity, release, warmth, protection) **unless** uniquely constrained to the
  target.
- **Short** — bounded length, to prevent a prose-quality/verbosity confound.
- **Matched across arms** — A_correct and every control signature share length, register, and structural
  format, so the judge cannot win on surface form instead of fit.
- Authored by a documented procedure recorded in the prereg **before** any packet is built.

## 11. Semantic-distance tiering

Three deranged tiers, each a wrong signature drawn from another word at a specified distance:

- **R_deranged_near** — signature of a close semantic neighbor (shared category).
- **R_deranged_mid** — signature of a related but non-equivalent domain.
- **R_deranged_far** — signature of a semantically distant word.

**Tier assignment before judging**, by a documented, frozen procedure:

- **embedding similarity and/or WordNet** distance (named model/resource, pre-registered thresholds);
- **blind human grouping** if needed (annotators sort source words into near/mid/far without seeing
  signatures or outputs; agreement reported);
- **predefined thresholds/rules** fixed in the prereg;
- **no post-hoc reassignment** — a tier label cannot move after results are seen; divergent cases resolved by
  pre-set rule or dropped, never hand-adjudicated afterward.

## 12. Controls

Arms: **A_correct**, **R_deranged_near**, **R_deranged_mid**, **R_deranged_far**, **R_same** (same-pool
random real signature), **R_domain** (mismatched-domain real signature), **generic_symbolic** (high-quality
non-varṇa resonant prose), **dictionary_baseline** (optional floor).

Rules:

- every control **fluent, real, plausible** — **no ugly/nonsense** controls;
- **length/register matched** to A_correct (uniform across tiers, so tier differences reflect semantics, not
  style drift);
- **"far" means a distant source word, not degraded text**;
- **no leakage of arm identity** — no marker that reveals which signature is A vs a control.

## 13. Judge task

Blinded discriminative prompts (a frozen B1.2 picks a pre-specified subset):

- **Selection:** *"Which signature best fits the target word and distinguishes it from its near synonyms?"*
  among k blinded candidates.
- **Pairwise:** A_correct vs one control, blinded order; pick the better-fitting signature.
- **Ranking (optional):** rank all candidate signatures by fit; score by rank of A_correct.

The judge must be instructed to evaluate **fit and word-specific distinction**, **not** beauty, fluency, or
style. Every candidate is presented without arm labels or mapping metadata.

## 14. Blinding

- **Opaque IDs only**; no arm labels in judge-facing packets.
- **No varṇa / Sanskrit labels**, no bridge-source metadata, no Layer-1 phonetic tags.
- **No target/control truth leakage**; candidate order shuffled by a frozen seed.
- **Private truth map stored separately** from judge-facing packets (as in B1.1), revealed only at scoring.

## 15. Primary endpoints

Primary **success** requires **all**:

- A_correct **beats R_deranged_far** (corrected CI lower bound > chance);
- A_correct **beats R_deranged_mid** (corrected CI lower bound > chance);
- A_correct **does not lose** to **R_deranged_near**;
- a **monotonic distance gradient**: margin_far > margin_mid > margin_near;
- A_correct **also beats R_same and R_domain**;
- the result **survives** multiplicity correction and all pre-specified robustness checks.

Chance floor is explicit per task (1/k for k-way selection; 0.5 for pairwise/odd-one-out). The gradient — not
any single comparison — is the distinctive evidence for word-specific mapping.

## 16. Allowed positive label

**Only `MAPPING_FIDELITY_SIGNAL`** (with a distance-gradient qualifier).

Explicitly **disallowed** at any outcome: `LIMITED_GENERATION_UTILITY`, ontology validation, Sanskrit
privilege, semantic-truth claim, Track B unblock.

## 17. Kill criteria

- **A fails far** → no recoverable word-specific signal (strongest kill).
- **near ≈ mid ≈ far (flat)** → generic symbolic resonance explains the effect.
- **A fails R_same or R_domain** → mapping fidelity unsupported regardless of the deranged gradient.
- **Success only on handpicked examples** / not surviving robustness → not robust, not support.
- **Layer 3 hand-authored post-hoc** → overfit and invalid.
- **Controls weakened** (uglified, shortened, off-topic) → invalid.

Any kill closes the varṇa-mapping line (per the decision memo); no rescue language, no goalpost move to the
weak controls.

## 18. Statistical plan

- **Pairwise A-win rate** per comparison; **ranking accuracy** (e.g. correct-in-top-1 / MRR) if ranking used.
- **Word-clustered paired bootstrap CIs** (item = word), n_boot and seed frozen in the config.
- **Holm–Bonferroni** correction across all co-primary comparisons and tasks.
- **Per-judge breakdown** reported.
- **Judge exclusion only by preregistered attention/parser rules** (as B1.1: fail > 1 or > 25% of attention
  checks); **no post-hoc judge selection**.

## 19. Robustness checks (pre-specified)

- **drop-judge** sensitivity;
- **drop-parse-fail** sensitivity;
- **drop-repaired** sensitivity (if the parser performs any repair);
- **near/mid/far tier** sensitivity (result stable to reasonable tier-boundary perturbation);
- **word-cluster** sensitivity (leave-one-word-out);
- **generic-symbolic comparison** (A must exceed the generic-resonance baseline, not just the weak controls).

## 20. Leakage and artifact freeze

- **Prereg before build**, **freeze before judging**; all configs **hash-bound** in a B1.2 manifest.
- **Leak scan under real G2P** if any phonetic rendering appears (the `artha`-class catch — real G2P, not
  illustrative spelling).
- **No Sanskrit/varṇa/meta labels** in judge-facing packets.
- **No post-hoc edits** to any frozen artifact; any change invalidates the run (`INVALID_POSTHOC`).

## 21. Expected interpretations

- **clean monotonic gradient + beats R_same and R_domain** → `MAPPING_FIDELITY_SIGNAL`.
- **beats far only** (fails mid/near) → **category-level resonance**, explicitly **not** word-specific
  mapping.
- **flat across tiers** → **generic symbolic resonance**.
- **fails far** → no recoverable word-specific signal.
- **loses to R_same or R_domain** → mapping fidelity **unsupported**.

## 22. Stop / default rule

If this prereg **cannot** specify Layer 2, Layer 3, the near/mid/far tiering, or the controls **without
hand-tuning** (i.e. without authoring the answer key or tier labels to favor A), then per the decision memo
the **DECISION defaults to `STOP_NOW`** and the varṇa-mapping line closes. A B1.2 that can only be made to
pass by design choices is not a valid falsifier and must not run.

## 23. Final status block

```
document:                   B1.2 mapping-fidelity PREREG (prereg only; nothing built/run)
status:                     NOT_RUN · NOT_FROZEN · NOT_AUTHORIZED_FOR_GENERATION_OR_JUDGING
implementation done:        NO
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
only allowed positive:      MAPPING_FIDELITY_SIGNAL
Track B:                    BLOCKED
Track G negative:           RANDOM_POLARITY_EXPLAINS (1fe5562; A_vs_R -0.1917, A_vs_X -0.075) — preserved
Track F negative:           CORRECTNESS_DEGRADED — preserved
ontology validation:        NONE
Sanskrit privilege:         NONE
semantic-truth claim:       NONE
default rule:               STOP_NOW if Layer 2 / Layer 3 / tiers / controls require hand-tuning
next:                       prereg review, then freeze — no build before both
```

**Structure, not validated meaning.** This preregisters one final, different, discriminative falsifier; the
B1.1 verdict stands, no result is rescued, Track B remains BLOCKED, the prior negatives (Track G, Track F)
are preserved, and nothing may be built or judged until this prereg is reviewed and a new freeze is created.
