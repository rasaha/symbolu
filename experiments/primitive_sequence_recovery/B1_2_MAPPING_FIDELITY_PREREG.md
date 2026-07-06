# B1.2 Mapping-Fidelity Preregistration

## 1. Title and status

**B1.2 Mapping-Fidelity Preregistration** — the single authorized, final discriminative falsifier of the
corrected three-layer theory.

```
document:   B1.2 mapping-fidelity PREREGISTRATION (prereg only)
status:     NOT_RUN · NOT_FROZEN · NOT_AUTHORIZED_FOR_GENERATION_OR_JUDGING
authority:  one final authorized mapping-fidelity falsifier (per B1_2_MAPPING_FIDELITY_PREREG_DECISION.md)
amendment:  A1 — prediction-vs-answer-key design folded in (see §6a); G(word)=dictionary differential answer
            key, V(word)=varṇa prediction; §6a governs on any conflict with the original draft
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

**Primary:** *Does the varṇa-derived prediction `V(word)` align with the target word's dictionary-derived
differential answer key `G(word)` better than with wrong-word answer keys — under blinded conditions, and
with a semantic-distance gradient?*

**Not** the question: does the bridge improve open-ended generation? (That was B1.1; it failed and is not
re-asked.)

## 5. What B1.2 can and cannot prove

**Can test:**

- mapping-fidelity **within this artifact system** — whether the varṇa prediction V(word) is
  blind-distinguishable in its alignment to the *correct* dictionary answer key vs wrong keys;
- whether V(target) beats **G(near) / G(mid) / G(far)**, and whether alignment tracks semantic distance.

**Cannot prove (must not be claimed at any outcome):**

- ontology validation; Sanskrit truth or privilege; universal semantic truth;
- LLM-architecture validity; Track B unblocking; generation utility.

## 6. Study type

**Discriminative forced-choice / ranking study.** The primary endpoint is **alignment accuracy** — whether
the varṇa-derived *prediction* lands on the correct word's dictionary-derived *answer key* rather than a
wrong word's — **not** open-ended generation quality. No open generation is scored as a primary endpoint.

## 6a. Prediction vs answer key (Amendment A1 — governing definition; supersedes on any conflict)

B1.2 tests the varṇa mapping as a **predictor of meaning**, not as a piece of judged prose. Two objects,
built by **separate, frozen, word-agnostic** procedures, play two distinct roles:

- **G(word) — dictionary-derived differential answer key (the ground truth).** What makes the word distinct
  from its near neighbors, computed *mechanically from dictionaries* (§9). G is the **correct answer**; it is
  **never** scored as the "A signature" by itself. Judging G for fit would only prove that dictionaries
  describe words — vacuous, and invalid.
- **V(word) — varṇa-derived prediction (the object under test).** What Symbol-U's varṇa mapping *predicts*
  the word means, computed *mechanically from the varṇa skeleton + frozen gloss table* (§10). V is the
  **shot** at the answer.

**The test (governing endpoint):** does **V(target)** align with **G(target)** better than with the wrong
answer keys **G(near), G(mid), G(far)** and the non-answer-key controls **R_same, R_domain, generic_symbolic**
— and does alignment strengthen with semantic distance (near hardest, far easiest)?

Wherever an earlier draft says "A_correct is the Layer-3 differential signature," read it as: **A_correct =
the alignment V(target)↔G(target); Layer 3 is G(word), the answer key the prediction must hit — not the
judged signature.**

## 7. Unit of analysis

The item is the **target word**. Each item bundles:

- **target word**;
- **frozen dictionary semantic field** (Layer 2, §9) — input to G;
- **near-neighbor confusion set** (≥10 synonyms/category-neighbors used to build G);
- **G(target)** — the word's dictionary-derived differential **answer key** (frozen);
- **V(target)** — the word's varṇa-derived **prediction** (frozen);
- **wrong answer keys**: **G(near)** = G(R_deranged_near source), **G(mid)**, **G(far)** — other words'
  differential answer keys at near/mid/far semantic distance;
- **non-answer-key controls**: **R_same** (same-pool random differential), **R_domain** (mismatched-domain
  differential), **generic_symbolic** (high-quality non-varṇa reflective text), **dictionary_baseline**
  (optional floor).

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

## 9. Layer 2 construction (dictionary semantic grounding — input to G)

Layer 2 is the raw lexical material G is built from.

- The dictionary semantic field for each word is **created before judging** and **frozen**.
- **Source documented** (named dictionary / lexical resource; extraction rule recorded).
- **Same format for every word** (uniform fields: gloss, lexical category, semantic role).
- **No model output may influence Layer 2** — built from lexical sources only, never from generations.
- **Layer 2 is not, by itself, a success condition** — it is grounding/input, not the endpoint.

## 10. Layer 3 = G(word), the dictionary-derived differential answer key (NOT the judged signature)

**Layer 3 is the ground-truth answer key `G(word)`, produced mechanically from dictionaries — it is the
target the varṇa prediction `V(word)` must hit, never itself the "A" signature scored for fit.**

**G(word) is built by a fixed, word-agnostic procedure:**

1. **Target definition** — the frozen Layer-2 dictionary field of the target word.
2. **≥10 synonym / near-neighbor definitions** — the frozen Layer-2 fields of at least ten synonyms /
   category-neighbors, drawn by a documented rule (e.g. thesaurus + WordNet neighbors), **not** hand-picked
   to flatter the target.
3. **Shared-feature subtraction** — remove the semantic features the target shares with the neighbor set.
4. **Target-specific differential features** — what remains: the features unique to (or dominant in) the
   target relative to its neighbors. This residual **is** G(word).

Constraints on G(word):

- **Mechanical and uniform** — the *same* extraction+subtraction procedure produces G for every word
  (target and every control-source word). No bespoke per-word authoring.
- **Frozen and hash-bound before judging**; **not tuned** after seeing any output, score, or alignment.
- **Built from lexical sources only** — no model output, and crucially **nothing varṇa-derived** may enter G
  (G must be a clean, independent ground truth so the test of V is not circular).
- **Short and format-matched** across all G's (target and wrong keys), so the judge cannot win on surface
  form instead of alignment.
- **Not a success condition by itself** — judging G for word-fit only tests dictionaries and is **invalid**
  (§17 kill criterion).

## 10a. V(word) construction (the varṇa-derived prediction under test)

- Built **mechanically** from: (1) the **Layer-1 raw varṇa skeleton** of the word (real G2P→varṇa), (2) the
  **frozen varṇa gloss table** (the committed bridge pool / ontology), (3) a **frozen composition rule**.
- The **same** function produces V for every word — no per-word hand-authoring, no post-hoc tuning.
- **Layer 1 is mandatory, not optional** — V is the *only* legitimate source of the prediction's
  word-specificity. If the varṇa term is removed and alignment survives, the dictionary did the work (a
  null for Symbol-U).
- V is frozen and hash-bound before judging; format-matched to the G's for blinding.
- V and G are built by **independent** pipelines (varṇa vs dictionary) so that "does V hit G" is a real,
  non-circular test.

## 11. Semantic-distance tiering

Three **wrong answer keys**, each a `G(other word)` drawn at a specified distance from the target (the varṇa
prediction V(target) is scored against these as distractors):

- **G(near)** — differential answer key of a close semantic neighbor (shared category).
- **G(mid)** — differential answer key of a related but non-equivalent domain.
- **G(far)** — differential answer key of a semantically distant word.

**Tier assignment before judging**, by a documented, frozen procedure:

- **embedding similarity and/or WordNet** distance (named model/resource, pre-registered thresholds);
- **blind human grouping** if needed (annotators sort source words into near/mid/far without seeing
  signatures or outputs; agreement reported);
- **predefined thresholds/rules** fixed in the prereg;
- **no post-hoc reassignment** — a tier label cannot move after results are seen; divergent cases resolved by
  pre-set rule or dropped, never hand-adjudicated afterward.

## 12. Controls (the distractor answer keys V is scored against)

The prediction **V(target)** is matched against the correct key **G(target)** and these distractors:

- **G(near)**, **G(mid)**, **G(far)** — wrong-word differential answer keys at increasing semantic distance
  (§11);
- **R_same** — a differential answer key of a random same-pool word (no distance structure);
- **R_domain** — a differential answer key from a mismatched domain bucket;
- **generic_symbolic** — high-quality non-varṇa reflective text (bounds the generic-resonance baseline);
- **dictionary_baseline** — optional floor anchor.

Rules:

- every distractor is a **real, fluent, plausible** differential built by the same G procedure — **no
  ugly/nonsense** controls;
- **length/register/format matched** to G(target) and to V (uniform across tiers, so tier differences reflect
  semantics, not style drift);
- **"far" means a distant source word, not degraded text**;
- **no leakage of identity** — no marker revealing which key is G(target) vs a distractor, or which object is
  V.

## 13. Judge task (alignment of the varṇa prediction to the answer keys)

The judge is shown the varṇa-derived **prediction V(target)** (blinded, unlabeled) and asked which
**answer key** it best matches. Blinded discriminative prompts (a frozen B1.2 picks a pre-specified subset):

- **Selection:** *"This description was derived from one word's sound-structure. Which of these differential
  meanings does it best match?"* — candidates = G(target) + wrong keys, k-way, blinded.
- **Pairwise:** V(target) against G(target) vs one distractor key, blinded order; pick the better match.
- **Ranking (optional):** rank all candidate answer keys by match to V(target); score by rank of G(target).

The judge must evaluate **alignment/word-specific match**, **not** beauty, fluency, or style, and never sees
arm labels, varṇa/Sanskrit labels, or which object is the prediction vs a key. **G(target) is never judged
for word-fit on its own** — it only ever appears as one candidate key the prediction is matched against.

## 14. Blinding

- **Opaque IDs only**; no arm labels in judge-facing packets.
- **No varṇa / Sanskrit labels**, no bridge-source metadata, no Layer-1 phonetic tags.
- **No target/control truth leakage**; candidate order shuffled by a frozen seed.
- **Private truth map stored separately** from judge-facing packets (as in B1.1), revealed only at scoring.

## 15. Primary endpoints (alignment of V to G)

Primary **success** requires **all** — where "V(target) beats X" means V(target) aligns with G(target) more
than with X, corrected CI lower bound > chance:

- **V(target) aligns best with G(target)** overall (correct-key selection above chance);
- **V(target) beats G(far)** (corrected CI lower bound > chance);
- **V(target) beats G(mid)** (corrected CI lower bound > chance);
- **V(target) does not lose** to **G(near)**;
- a **monotonic distance gradient**: margin vs G(far) > margin vs G(mid) > margin vs G(near);
- **V(target) also beats R_same and R_domain** (and the generic_symbolic baseline);
- the result **survives** multiplicity correction and all pre-specified robustness checks.

Chance floor is explicit per task (1/k for k-way selection; 0.5 for pairwise/odd-one-out). The gradient — not
any single comparison — is the distinctive evidence that the varṇa mapping recovers word-specific meaning.

## 16. Allowed positive label

**Only `MAPPING_FIDELITY_SIGNAL`** (with a distance-gradient qualifier).

Explicitly **disallowed** at any outcome: `LIMITED_GENERATION_UTILITY`, ontology validation, Sanskrit
privilege, semantic-truth claim, Track B unblock.

## 17. Kill criteria

- **V(target) fails G(far)** → no recoverable word-specific signal (strongest kill).
- **alignment flat across G(near)/G(mid)/G(far)** → generic symbolic resonance explains the effect.
- **V(target) fails R_same or R_domain** → mapping fidelity unsupported regardless of the deranged gradient.
- **Success only on handpicked examples** / not surviving robustness → not robust, not support.
- **G(word) scored as the "A signature" by itself** (judging the dictionary key for word-fit) → **invalid**
  (tests dictionaries, not varṇa).
- **G(word) or V(word) hand-authored / hand-tuned post-hoc**, or **anything varṇa-derived leaking into G** →
  overfit / circular / **invalid**.
- **Layer 1 made optional in V** (alignment survives without the varṇa term) → the dictionary did the work →
  **null for Symbol-U**.
- **Controls weakened** (uglified, shortened, off-topic) → invalid.

Any kill closes the varṇa-mapping line (per the decision memo); no rescue language, no goalpost move to the
weak controls.

## 18. Statistical plan

- **Pairwise alignment-win rate** per comparison (V(target) matches G(target) over the distractor);
  **correct-key selection rate** and **ranking accuracy** (correct-in-top-1 / MRR) if ranking used.
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

*(All in terms of how well the varṇa prediction V(target) aligns with the correct answer key G(target)
against the distractor keys.)*

- **V hits G(target) with a clean monotonic gradient + beats R_same and R_domain** → `MAPPING_FIDELITY_SIGNAL`.
- **V beats G(far) only** (fails G(mid)/G(near)) → **category-level resonance**, explicitly **not**
  word-specific mapping.
- **V aligns flat across G(near)/G(mid)/G(far)** → **generic symbolic resonance**.
- **V fails G(far)** → no recoverable word-specific signal.
- **V loses to R_same or R_domain** → mapping fidelity **unsupported**.

## 22. Stop / default rule

If this prereg **cannot** specify a **mechanical, word-agnostic** procedure for **G(word)** (the
dictionary differential answer key), **V(word)** (the varṇa prediction), the near/mid/far tiering, or the
controls **without hand-tuning** — i.e. without a human authoring the answer key, the prediction, or the tier
labels to favor the target — then per the decision memo the **DECISION defaults to `STOP_NOW`** and the
varṇa-mapping line closes. In particular: if V cannot be derived from the varṇa skeleton by a frozen rule, or
if G can only be produced by hand, there is nothing varṇa-specific to test and the study must not run. A B1.2
that can only be made to pass by design choices is not a valid falsifier.

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
