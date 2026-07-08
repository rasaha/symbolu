# B1.4 / Milestone B — Word-Blind Varṇa-Attribute Validation Design

**Status:** Fresh versioned study design (docs-only). Not a run, not a dataset, not code.
**Governed by:** `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md` (hardened rules) and
`SYMBOL_U_L2_VALIDATION_RULEBOOK.md` (L1/L2/L3, probe `P`, baselines `B`, failure state `⊥`).
**No meaning validated. No dataset built. Nothing run or scored. B1.3 v3 remains parked.**
**Track B remains blocked. Structure, not validated meaning.**

Related documents:
- `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md` (the pipeline and blinding this design instantiates)
- `MILESTONE_A_L2_FOUNDATION_SPEC.md` / `MILESTONE_A_CANDIDATE_E_AUDIT.md` (result: `MILESTONE_A_INCONCLUSIVE`)
- `B1_3_V3_L2_RULEBOOK_COMPATIBILITY_MEMO.md` (B1.3 v3 parked, pre-rulebook exploratory)

---

## 1. Purpose

B1.4 is a **fresh versioned design** built from the start under the hardened varṇa-attribute / KCPR rules. It
tests whether **varṇa-derived attribute/propensity profiles** carry signal, using a **word-blind generator**
and a **fixed KCPR pole rule**. It is **not** a modification, continuation, or rescue of B1.3 v3; B1.3 v3 stays
parked and untouched. This document is a design only — it authorizes no dataset, no code, and no run.

---

## 2. Starting state

- **B1.3 v3 is parked** as a pre-rulebook exploratory study; not modified in place.
- **The L2 rulebook governs** all future semantic testing (probe/baseline/⊥ discipline).
- **The hardened KCPR/attribute rules govern this design** (generator-word blindness; kosha assigned before
  generation; attributes-not-meaning framing).
- **The candidate-E audit remains `MILESTONE_A_INCONCLUSIVE`** — no attribute table has yet been shown to be an
  admissible, independently-sourced essence table `E`. B1.4 therefore opens with an E-admissibility gate (§4)
  and cannot proceed past it until `E` is resolved.

---

## 3. Core hypothesis

- **Not** "varṇas recover the dictionary meaning of a word." That is explicitly rejected as the test object.
- **B1.4 hypothesis:** *a varṇa-derived attribute/propensity profile can generate or predict a concept's
  associated attribute field better than controls* — where the attribute field is measured independently of
  the dictionary definition (§5).

The null is the expected default given the prior (§16); the burden is entirely on `A_real` to beat every
control in §11.

---

## 4. E-admissibility gate (must clear before building B1.4)

Before any item, prompt, or dataset is designed, decide whether a varṇa attribute table can serve as an
**admissible essence table `E`** — i.e. whether it is independently sourced rather than derived from the test
concepts' dictionary meanings (per the candidate-E audit). Required decision label (exactly one):

- **`E_ADMISSIBLE_FOR_B1_4_DESIGN`** — an independently-sourced, audited attribute table exists; proceed.
- **`E_CIRCULAR_RETURN_BOTTOM`** — the table reduces to dictionary/gloss meaning; **stop, return `⊥`.**
- **`E_INSUFFICIENT_PROVENANCE`** — provenance cannot be audited free of leakage; **stop, do not proceed.**
- **`E_ADMISSIBLE_ONLY_AS_DECODER_NOT_ESSENCE`** — usable as an L3 decoder read-out but **not** as a validated
  essence foundation; B1.4 may run only as a *decoder-utility* probe, never as an essence-validation claim.
- **`B1_4_DESIGN_BLOCKED_PENDING_E`** — the E question is unresolved; **design is blocked** until Milestone A
  resolves it.

**If `E` is not admissible, this design must stop and return `⊥`.** Clean pipeline mechanics cannot rescue a
circular or unsourced `E`.

---

## 5. Definition of target `Y`

`Y` is an **independently measured attribute/propensity profile** of the target concept — **not** its
dictionary definition. Candidate `Y` sources (each pre-registered, gloss-independent, collected without
reference to the varṇa table):

- **Blind human attribute ratings** — raters score a concept on attribute dimensions while blind to the varṇa
  profile and to the hypothesis.
- **Independently collected association norms** — existing free-association / feature-production norms.
- **Behavioral attribute judgments** — task-derived attribute measures (e.g. forced-choice on attribute
  dimensions).
- **Non-varṇa semantic feature norms** — published semantic-feature datasets, where available.

Risk to control for on all of these: `Y` must not itself be gloss-in-disguise or built from the varṇa table,
or the test re-imports circularity. Whichever `Y` is chosen must be frozen before generation.

---

## 6. Clean pipeline (hardened)

Exactly the hardened pipeline, in order:

1. **Target concept selected** — recorded privately as the hidden answer.
2. **Generator never sees the target word** (§7).
3. **Varṇa split** — decompose the concept's word into varṇas.
4. **Frozen varṇa attribute table** — pre-registered, never per-item hand-edited, never target-fitted.
5. **Experimentally assigned kosha condition** — assigned by design and frozen before generation.
6. **Fixed KCPR pole rule** — resolves each attribute axis to a binding/liberating pole from the assigned
   kosha (§8).
7. **Profile assembled** — ordered attributes + selected poles; no word, no definition, no arm id, no source,
   no key.
8. **Generator writes from profile only** — word-blind rendering of the profile.
9. **Independent blinded judge** — a *different* model compares outputs against the target concept **or**
   against the target's blind attribute ratings (§10).
10. **Frozen scorer** — evaluates `A_real` vs controls on pre-registered metrics; emits its label as-is.

---

## 7. Generator-word blindness (hard exclusions)

The generator must **never** receive:

- the **target word** (or any orthographic/phonetic form),
- the **dictionary definition** / referent,
- **target-revealing context** (wording that names or unmistakably points to the concept),
- the **candidate label**,
- the **arm label**, or
- **source metadata** / provenance.

The generator may see **only** the profile / bridge representation plus target-neutral style instructions. A
leak scan must confirm no target-revealing token reaches the generator; any leak → `WORD_LEAKAGE_INVALID_RUN`.

---

## 8. KCPR rule

- **Kosha condition is assigned by design before generation** and frozen; never read off the word.
- **Same kosha condition within paired arms** — within an `A_real`-vs-control pair, only the attribute mapping
  changes; the kosha/pole is held fixed (avoids confounding mapping with pole).
- **Kosha levels may vary across items or in a separate ablation**, where kosha is the deliberately
  manipulated variable and analyzed as such.
- **No pole selection from dictionary meaning after seeing the target** — assign kosha first, apply the rule
  mechanically; any post-hoc pole adjustment → `KCPR_POSTHOC_INVALID_RUN`.

---

## 9. Arms

- **`A_real`** — the true varṇa-derived attribute profile for the target concept.
- **`R_deranged`** — attribute profile from **another word** / a **mismatched varṇa sequence**.
- **`R_scrambled`** — the target's varṇa-to-attribute mapping with **varṇa order scrambled**.
- **`R_random`** — a **random / relabel** attribute profile.
- **`semantic_only_baseline`** — an ordinary **concept/word meaning** baseline (no varṇa profile); the
  gloss-leakage control.
- **phonological baseline** — a **sound-similar, meaning-unrelated** control.
- **Barnum / generic attribute baseline** — a **vague, universally-fitting** attribute profile.
- **sentiment / lexicon baseline** — an affect/lexicon predictor, where applicable.

---

## 10. Probe `P`

`P` is the **test**, not a decoder. Two probe forms (use either, or both if separable):

- **Attribute-profile prediction task** — does the `A_real` profile predict the target's independently measured
  attribute ratings `Y` better than controls? (correlation / ranking against `Y`.)
- **Word-blind generation fit task** — does a blind judge find the `A_real`-profile passage a better fit to the
  target concept (or its attribute ratings) than control passages? (forced-choice / ranking.)

**The probe is not the decoder.** The decoder (attribute table + KCPR) *produces* profiles/passages; `P`
*scores* them against `Y` and the baselines. Producing a plausible profile is not evidence; only beating the
baseline suite under `P` is.

---

## 11. Baseline suite `B`

`A_real` must be tested against **all** of:

- **random / relabel**,
- **deranged**,
- **scrambled**,
- **phonological similarity**,
- **length / frequency**,
- **sentiment / lexicon**,
- **semantic-only baseline**,
- **Barnum / generic attribute baseline**, and
- **chance / null**.

Beating some but not all is **not** signal.

---

## 12. What counts as signal

`A_real` is credited with signal **only if it beats every control in §11 on pre-registered metrics**.

- It is **not enough** for `A_real` to sound plausible.
- It is **not enough** for `A_real` to beat only the dictionary-only / weak controls.

Any un-beaten control is dispositive against the claim.

---

## 13. Failure / `⊥` conditions

Return `⊥` (null / invalid, as appropriate) if any hold:

- `E` is **circular** (or unsourced),
- the **generator sees the word** (or any target-revealing token),
- the **KCPR pole is chosen post-hoc** from the target's meaning,
- the **semantic-only baseline explains** the result,
- the **phonological / sentiment / Barnum** controls match `A_real`,
- the **judge only rates plausibility** (not fit-to-target against controls), or
- outputs **require post-hoc interpretation** to look like a hit.

`⊥` is the correct, expected output in these cases — not a prompt to re-tune. No rescue.

---

## 14. Metrics (pre-registered)

- **pairwise win rate** (`A_real` vs each control),
- **MRR / Top-1** if ranking multiple arms,
- **correlation** of `A_real` profile with blind attribute ratings `Y`,
- the explicit contrasts: **A_vs_deranged, A_vs_scrambled, A_vs_random, A_vs_semantic_only, A_vs_phonological,
  A_vs_Barnum**,
- **confidence intervals** on every rate/correlation (e.g. Wilson / bootstrap),
- **multiple-comparison correction** across the contrast family (e.g. Holm), with the **primary endpoint**
  named in advance (recommended: `A_vs_deranged` and `A_vs_semantic_only` both required to pass).

All metrics, thresholds, and the primary endpoint are fixed in pre-registration **before** any data is seen.

---

## 15. Sample size and pilot stages

- **Synthetic harness first** — validate plumbing, blinding, and leak scans on synthetic (non-real) items; no
  evidence value.
- **10–15 item smoke** — plumbing only; confirms the pipeline runs word-blind end-to-end. **No evidence claim
  from smoke.**
- **Larger pilot only after smoke passes** — powered to the pre-registered primary endpoint; size fixed in
  pre-registration.
- **No evidence claim from smoke or pilot plumbing** — only the pre-registered, frozen run yields a terminal
  label.

---

## 16. Relationship to prior studies

- **Tracks C / D / E / F / G remain unchanged** (incl. Track G `RANDOM_POLARITY_EXPLAINS`, Track F
  `CORRECTNESS_DEGRADED`).
- **B1.1 remains unchanged** (`RANDOM_OR_SCRAMBLED_MATCHES`; scrambled ≈ real ~0.967).
- **B1.3 v3 remains parked** (pre-rulebook exploratory; not modified).
- **This design does not rescue prior negatives.** A B1.4 result stands only for B1.4; it cannot relabel any
  prior null/negative as positive.

---

## 17. Allowed terminal labels

The B1.4 scorer/design may emit exactly:

- **`ATTRIBUTE_PROFILE_SIGNAL`** — `A_real` beat every control on the pre-registered endpoint.
- **`SEMANTIC_ONLY_EXPLAINS`** — the semantic-only baseline accounts for the result.
- **`PHONOLOGICAL_BASELINE_EXPLAINS`** — a sound baseline accounts for the result.
- **`BARNUM_PROFILE_EXPLAINS`** — a generic/vague profile fits as well.
- **`SCRAMBLE_OR_RANDOM_EXPLAINS`** — scrambled/random matches `A_real`.
- **`E_CIRCULAR_RETURN_BOTTOM`** — `E` was not admissible; terminal `⊥`.
- **`WORD_LEAKAGE_INVALID_RUN`** — the generator saw a target-revealing token.
- **`KCPR_POSTHOC_INVALID_RUN`** — the pole was chosen post-hoc from meaning.
- **`ATTRIBUTE_PROFILE_NULL`** — clean run, no signal.
- **`INCONCLUSIVE`** — the study could not resolve the question.

No positive label other than `ATTRIBUTE_PROFILE_SIGNAL`, and it is earned only by beating **all** controls.
**No ONTOLOGICAL_SIGNAL. No Sanskrit privilege.**

---

## 18. Next-step gate

The next step after this document is **not implementation.** It is:

1. an **explicit E-admissibility decision** (§4), and
2. a **pre-registration review** (arms, `Y`, probe, baselines, metrics, primary endpoint, thresholds, `⊥`
   conditions) approved before any harness is built.

Only after both — and an explicit operator authorization — would synthetic-harness work begin. This document
authorizes none of it.

---

## 19. Boundary statement

> B1.4 word-blind varṇa-attribute validation design drafted only. No meaning validated. No dataset built.
> Nothing run or scored. B1.3 v3 remains parked. Track B remains blocked. Structure, not validated meaning.
