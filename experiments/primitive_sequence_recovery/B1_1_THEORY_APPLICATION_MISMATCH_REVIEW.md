# B1.1 Theory-Application Mismatch Review (review only — does not change or rescue B1.1)

## 1. Scope and non-rescue rule

This is a **theory-application mismatch review only**. It asks whether B1.1 failed partly because the
*implemented experiment* did not faithfully instantiate the *intended three-layer theory* — not whether the
theory is thereby vindicated. It does **not**:

- change or reinterpret the B1.1 result, or read the failed null as hidden/partial success;
- rerun judges or scoring, or modify any B1.1 artifact, frozen manifest, or `varna_lens/` source;
- rescue B1.1, claim `LIMITED_GENERATION_UTILITY`, or unblock Track B;
- claim ontology validation, Sanskrit privilege, or semantic truth.

**Locked facts:** B1.1 verdict remains **`RANDOM_OR_SCRAMBLED_MATCHES`**; `LIMITED_GENERATION_UTILITY` is
**not earned**; Track B remains **BLOCKED**; Track G `RANDOM_POLARITY_EXPLAINS` and Track F
`CORRECTNESS_DEGRADED` remain **preserved**. Any future correction requires a **new prereg and a new
freeze**; B1.1 may not be reused as a positive prior. **Structure, not validated meaning.**

**Thesis.** B1.1 may have failed not *only* because the theory is false, but because the implemented
experiment did not cleanly separate and test the theory's three layers — in particular, it collapsed the
intended Layer 2 (dictionary grounding) and Layer 3 (synonym differentiation) into a single rendered
symbolic-conditioning object and scored it on open generation. This identifies the correct target for any
future study; it does **not** revive B1.1.

## 2. Corrected statement of the three-layer theory

The intended model is three distinct layers, not one bridge:

- **Layer 1 — Raw varṇa mapping.** word → phoneme/varṇa sequence: the raw sound/varṇa skeleton. This is the
  *substrate*, not the full meaning claim. It says which varṇas a word contains, nothing about whether that
  carries the word's meaning.
- **Layer 2 — Dictionary semantic grounding.** word → its actual conventional semantic field (dictionary
  meaning, lexical category, semantic role). This layer's job is to **prevent arbitrary varṇa poetry**: the
  bridge must be anchored to the word's accepted meaning, not free-associated from varṇa glosses. Without
  Layer 2, a bridge can be fluent and on-theme yet untethered from what the word actually denotes.
- **Layer 3 — Differential synonym-separation (word-specific signature).** identifies how the target word
  **differs** from its near synonyms and category-neighbors — its distinct semantic signature. Example:
  *mother* is not merely nurturer, caregiver, home, parent, shelter, or origin; Layer 3 must specify what
  makes *mother* specifically mother-like. **This is where near-neighbor confusion is supposed to be
  resolved** — and it is precisely the layer an open generation task does not force.

A faithful test of the theory would exercise these **separately**: is the skeleton right (L1), is the bridge
grounded in real meaning (L2), and can the system pick out the word's distinct signature against close
neighbors (L3)?

## 3. How B1.1 likely misapplied or under-applied the theory

- **B1.1 mostly tested rendered symbolic conditioning in open generation.** The A arm was a composed bridge
  fed as conditioning to a generator; the measured quantity was "did A's outputs read better than the
  controls' outputs," not "does each theoretical layer hold."
- **Layer 2 was not isolated as a separate requirement.** The bridge was built from varṇa/pole glosses; there
  was no independent step enforcing or checking that the bridge is anchored to the word's *dictionary*
  semantic field. Dictionary content entered only as the weak D control, not as a grounding constraint on A.
- **Layer 3 was not isolated at all.** Nothing in the pipeline required A to encode *how the target differs
  from its near synonyms*. The bridge could (and likely did) describe broadly-applicable tendencies that any
  category-neighbor shares.
- **The bridge phrases may have collapsed into broad symbolic prose.** Multi-varṇa composition concatenates
  tonal glosses; the result is evocative but generic — exactly what beats sparse controls (C, X) yet ties any
  other fluent bridge.
- **Scoring rewarded fluency/coherence over signature presence.** The LLM judges compared "which reads
  better," not "which output carries *this word's* distinct Layer-3 signature." Style could stand in for fit.
- **Flat R_deranged obscured the L3 question.** Because R_deranged mixed near, mid, and far wrong mappings
  (see the companion R_deranged control-validity review), B1.1 could not tell whether A fails specifically at
  the near-synonym boundary — the one place Layer 3 is supposed to do work.

## 4. What B1.1 actually tested

B1.1 tested **whether the current rendered A bridge, produced by the implemented end-to-end pipeline,
yielded better LLM generations than strong symbolic controls** (R_deranged, R_domain, R_same) on open
creative tasks. It did **not** directly test:

- whether the **Layer 1** varṇa skeleton is correct;
- whether **Layer 2** dictionary grounding was properly applied (that A is anchored to the word's real
  meaning rather than free varṇa association);
- whether **Layer 3** synonym-differentiation works (that A encodes the word's distinct signature);
- whether the target word's **distinct semantic signature can be recovered** at all under blinding.

It was an **end-to-end pipeline test**, not a **layer-by-layer** test.

## 5. What B1.1 failure means under the corrected theory

- B1.1 **falsifies or weakens the current end-to-end generation implementation** — as built and rendered, the
  A bridge does not beat strong symbolic controls in open generation.
- It does **not separately falsify each layer** of the intended theory: L1, L2, and L3 were never isolated,
  so their individual truth or application status is untested here.
- **But** — and this is the guardrail — because the implemented pipeline **failed strong controls**, **no
  positive claim is earned**. "The layers weren't tested separately" is not evidence that they would pass;
  it only means the burden is unmet, not disproven. The null stands.
- **The burden shifts** to a **new** study that directly tests **Layer 3 mapping-fidelity** (correct
  differential signature vs wrong-but-fluent bridges) rather than open generation utility.

The honest reading: B1.1 is a failure of *this implementation*, not a clean falsification of *each layer* —
and equally not a rescue of the theory. Untested ≠ vindicated.

## 6. Relationship to the R_deranged critique

- Flat R_deranged treated **every** wrong-word bridge as equally wrong.
- Under **Layer 3**, near-neighbor bridges are precisely the **hardest** cases — the ones L3 exists to
  resolve. A control that averages near, mid, and far together **cannot** show whether L3 works at the
  boundary that matters.
- A valid Layer-3 test must **stratify R_deranged into near / mid / far** semantic distance. The predicted
  Layer-3 signature is a **distance gradient**:
  - **A beats far** most strongly (a distant word's bridge should clearly misfit);
  - **A beats mid** moderately;
  - **A ties or only weakly beats near** (near-synonym bridges are legitimately close).
- A **flat** profile across tiers would support **generic symbolic resonance**, **not** Layer-3
  word-specificity. The gradient — not any single win — is the discriminating evidence.

## 7. Future B1.2 implication

B1.2 should be a **mapping-fidelity test**, **not** another open-ended generation test. Its question:

> Can the system identify the **correct Layer-3 differential signature** of the target word against
> **near / mid / far** wrong bridges, under blinding?

A faithful B1.2 item should carry:

- the **target word**;
- its **dictionary semantic field** (Layer 2 grounding, checkable);
- its **near synonyms / category-neighbors** (the L3 confusion set);
- the **correct differential signature** (the L3 answer, frozen before testing);
- **R_deranged_near**, **R_deranged_mid**, **R_deranged_far** (stratified wrong bridges);
- **R_same** (same-pool random real phrases);
- **R_domain** (mismatched-domain real bridge);
- a **generic symbolic control** (high-quality non-varṇa resonant prose, to bound the generic-resonance
  baseline A must exceed).

Tasks must be **discriminative** (forced-choice / ranking / odd-one-out) so a wrong mapping is **scored
wrong**, not merely read differently.

## 8. What would count as support in B1.2

Support requires **all** of:

- A_correct beats **R_deranged_far** and **R_deranged_mid** (corrected CI lower bound > chance);
- A_correct **does not lose** to **R_deranged_near**;
- a **monotonic semantic-distance gradient** (margin far > mid > near);
- A also beats **R_same** and **R_domain** (the arms B1.1 also failed);
- the result **survives** multiplicity correction and the pre-specified robustness/sensitivity checks.

**Allowed positive label:** `MAPPING_FIDELITY_SIGNAL` (with a distance-gradient qualifier).

**Not allowed** under any B1.2 outcome:

- `LIMITED_GENERATION_UTILITY` (that needs a *separate* generation study; B1.1 already failed it);
- ontology validation;
- Sanskrit privilege;
- semantic-truth claim;
- Track B unblock.

## 9. What would still kill the theory application

- **A cannot beat far wrong bridges** → no recoverable word-specific signal at all (strongest kill).
- **near / mid / far are flat** → generic symbolic resonance explains the effect; Layer 3 adds nothing.
- **R_same or R_domain still match/beat A** → mapping fidelity remains unsupported regardless of the deranged
  gradient.
- **Layer 3 must be hand-authored post-hoc** (the "correct signature" written or tuned after seeing outputs)
  → the test is **overfit and invalid**; the L3 answer key and all tier labels must be frozen before testing.

## 10. Recommended wording

> B1.1 should be read as a failure of the implemented end-to-end generation pipeline, not as a clean
> layer-by-layer falsification of the intended theory. The intended model requires Layer 1 raw varṇa mapping,
> Layer 2 dictionary semantic grounding, and Layer 3 differential synonym-separation. B1.1 mainly tested
> whether rendered symbolic bridges improved generation against strong symbolic controls, and it did not
> isolate whether Layer 3 word-specific differentiation works. This does not rescue B1.1 or change its null
> verdict; it only identifies the correct target for any future B1.2.

## 11. Final status block

```
document type:             theory-application mismatch review (review only; nothing run)
reran judges / scoring:    NO
B1.1 verdict:              UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
layers isolated in B1.1:   NONE (end-to-end pipeline test, not layer-by-layer)
burden:                    shifts to a new Layer-3 mapping-fidelity test (not rescued, not vindicated)
only allowed positive:     MAPPING_FIDELITY_SIGNAL (with distance-gradient qualifier)
Track B:                   BLOCKED
Track G negative:          RANDOM_POLARITY_EXPLAINS (1fe5562; A_vs_R -0.1917, A_vs_X -0.075) — preserved
Track F negative:          CORRECTNESS_DEGRADED — preserved
ontology validation:       NONE
Sanskrit privilege:        NONE
semantic-truth claim:      NONE
requires:                  new prereg + new freeze
```

**Structure, not validated meaning.** This review identifies a theory/implementation gap for a future study;
the B1.1 verdict stands, no result is rescued, Track B remains BLOCKED, and any future test requires its own
preregistration and freeze.
