# B1.3 Field-Theory — LLM-Judge Instrument Revision (v3.1, development)

## 1. Scope and non-rescue rule

Design revision memo only. It revises the **instrument** of the B1.3 field-theory prereg draft
(`B1_3_FIELD_THEORY_PREREG.md`) from human-first to **LLM-judge-first for development**. It does **not**
declare EVIDENCE_FREEZE, run, judge, or score anything; does **not** change any prior B1/B1.1/B1.2/B1.3
result; and claims **no** Symbol-U validation, `LIMITED_GENERATION_UTILITY`, `MAPPING_FIDELITY_SIGNAL`,
`PROPENSITY_MODULATION_SIGNAL`, ontology, Sanskrit privilege, semantic truth, or Track-B unblock. Status stays
`DEVELOPMENT_FREEZE · NOT_EVIDENCE_FROZEN · NOT_RUN`. **Structure, not validated meaning.**

## 2. Why LLM judges are allowed (for this object)

The field-theory target here is **textual**: does a word-form carry a different **contextual field / register
/ propensity** in language? That is coherence-, register-, synonym-fit-, and context-modulation judgment — a
**language-level** property LLMs genuinely model. An LLM can compare whether a passage better preserves an
intended register/field/anchor in context. This is a legitimate **development** instrument for the *textual*
version of the claim, and is faster/cheaper for iterating design before any human study.

## 3. What LLM judges cannot prove

- They do **not** prove human inner **felt** experience.
- They do **not** prove any metaphysical / manomaya varṇa ontology.
- They may reflect **learned textual convention** (register is a social fact LLMs absorbed), not a varṇa field.
- They may prefer **fluent/poetic** prose unless style is controlled.
- A later **human** study is required for human-felt validation; this instrument cannot substitute for it.

## 4. Revised claim label

**`LLM_PROPENSITY_FIELD_DISCRIMINATION`** — *blinded LLM judges prefer the real varṇa-derived propensity
modulation over scrambled, deranged, random, sound-neighbor, and neutral controls for contextual field
coherence, under style controls.*

- **Weaker than** a future `HUMAN_PROPENSITY_MODULATION_SIGNAL`.
- **Not yet earned.** Requires a future EVIDENCE_FREEZE and a successful judged run.
- Even if earned, it is a claim about **LLM textual-field discrimination**, not human feeling or ontology.

## 5. Correct judge task (anchored)

> *"Both passages use the target word/form in the same context. Given the fixed dictionary/contextual anchor,
> which passage better preserves the intended **field, register, and propensity** of the target word/form in
> context?"* — pairwise forced choice, blinded order.

**Forbidden phrasings:** "which is deeper," "which is more spiritual," "which is more poetic," "which do you
personally feel." These invite style/aesthetic/introspection confounds.

## 6. Synonym / context example

Same sentence frame, swap the form: **father / papa / dad**.

- *father* → formal / structural / distant field
- *papa* → warm / intimate / childlike field
- *dad* → casual / familiar field

The LLM is **not** judging dictionary meaning (all three denote male parent). It judges **contextual field /
register** — which form's propensity coheres with the intended field of the passage. (Honest caveat from §3:
this register difference is also explainable by learned convention, not necessarily varṇa — which is why the
controls in §7 and the style gate in §8 carry the weight.)

## 7. Arms retained (with failure meanings)

| arm | what it is | what a ≈-to-real result means |
|---|---|---|
| **A_real** | word's own varṇa field | (reference) |
| **R_deranged** | another word's varṇa field | **deranged ≈ real → varṇa profile not word-specific** (the B1.1/B1.2 wall) |
| **R_scrambled** | own varṇas, order-permuted | scrambled ≈ real → varṇa **order/structure** does no work |
| **R_varṇa_near** | sound-neighbor's field (father↔feather) | varṇa-near **wins** → sound-neighbor **artifact**, not field |
| **R_semantic_near** | synonym/near word's field (father↔guardian) | tests fine discrimination; should be intermediate |
| **R_random** | random screened field | random ≈ real → **generic prose**, any conditioning suffices |
| **X_neutral** | no-varṇa / neutral | neutral ≈ real → propensity **adds no value** |

## 8. Style / fluency controls (mandatory)

Equal **length bands**; **same template**; **same register**; matched **fluency**; **no arm-specific poetic
advantage**; **no hand-polishing** per arm; generation by frozen rule. **Style-tell audit before judging:** if
a blinded classifier/judge can identify the real arm from **style alone** (above threshold), **STOP** — the
comparison is contaminated (the B1.2 prose style-tell hit 0.70; this is not optional).

## 9. Judge panel

- **Multiple LLM judges from different model families** (aggregate across families).
- **Fixed prompts**; **temperature 0 / deterministic**; **pairwise forced choice**; **blinded arm labels**.
- **Position balancing** (each pair judged in both orders; average out order bias).
- **Parse-failure handling** (declared: schema-invalid → one bounded repair or drop by rule).
- **Tie handling** (declared: tie counts as 0.5, pre-registered).
- **No chain-of-thought required**; a short rationale may be collected **for diagnostics only** (style-leak
  detection), not as the decision.

## 10. Success criteria

All required:

- **A_real beats R_deranged**, **R_scrambled**, **R_random**, **X_neutral** (forced-choice rate > 0.5,
  item- and judge-clustered CI lower bound above chance);
- **R_varṇa_near does not beat A_real** (not a sound artifact); **R_semantic_near** intermediate (not > A_real);
- survives **model-family aggregation** (not one family only);
- survives **multiplicity correction** (Holm across arm comparisons);
- **style-tell passes** (real arm not identifiable by style);
- effect **not driven by a single judge/model** (drop-judge robustness).

**Only reachable positive label:** `LLM_PROPENSITY_FIELD_DISCRIMINATION`, and **only** after a future
EVIDENCE_FREEZE run.

## 11. Kill criteria

STOP / null if any: **R_deranged ≈ A_real**; **R_scrambled ≈ A_real**; **R_random ≈ A_real**; **X_neutral ≈
A_real**; **R_varṇa_near beats A_real**; **style-tell fails**; **A_real is longer / richer / more poetic** (arm
imbalance); **only one LLM judge** shows the effect; **judge rationales reveal reliance on surface style**;
**results collapse under position balancing**.

## 12. Relationship to the human study

- LLM judges are the **first-line development (and, post-freeze, evidence) instrument for textual-field
  coherence** — the language-level version of the claim.
- A **later human-rater study** (the v3 prereg design) validates human-**felt** resonance.
- **LLM-positive does not imply human-positive**, and neither implies ontology.
- **LLM-negative is still damaging** for the textual-field version — a null here is a real (development)
  negative for the language-level claim, not just "wrong instrument."

## 13. Evidence-freeze implication

A future EVIDENCE_FREEZE must explicitly hash-lock: **judge models**, **judge prompt**, **arms**, **generation
templates**, **seeds**, **style audit**, **scoring script**, **thresholds**, **parse/tie rules**. Until that
explicit declaration, status remains `DEVELOPMENT_FREEZE` and no run is evidence.

## 14. Decision

```
DECISION: LLM_JUDGE_REVISION_ACCEPTED_FOR_DRAFT
```

Accepted for the draft because the object is **textual-field coherence** (register/synonym-fit/context), which
LLMs are a legitimate instrument for; the strong controls (deranged crux, style-tell gate, multi-family panel,
position balancing) keep it honest; and the label is appropriately weak (`LLM_PROPENSITY_FIELD_DISCRIMINATION`)
with human validation retained as a later layer. **Honest burden flagged prominently:** this design is close
to B1.1 (LLM judges on varṇa-conditioned generation), which returned `RANDOM_OR_SCRAMBLED_MATCHES` with
`deranged ≈ real`; the one real difference is the **more targeted anchored field/register task** vs B1.1's
"which is better" preference — which *may* be more sensitive, but must clear the same `R_deranged` wall.
Acceptance is **not** a prediction of success. (Not `HIGH_RISK_NEEDS_ADJUDICATION`: controls are adequate for a
development draft. Not `REJECTED_HUMANS_REQUIRED`: humans are needed only for the *felt* claim, not the
*textual-field* claim.)

## 15. Final status block

```
document:                    B1.3 field-theory LLM-JUDGE instrument revision (v3.1; design only)
decision:                    LLM_JUDGE_REVISION_ACCEPTED_FOR_DRAFT
instrument:                  LLM judges (development-first) for TEXTUAL field/register/context; humans = later layer
object:                      textual contextual-field coherence (NOT human felt experience, NOT ontology)
only reachable positive:     LLM_PROPENSITY_FIELD_DISCRIMINATION (after EVIDENCE_FREEZE only) — NOT earned
crux control / burden:       R_deranged (B1.1 found deranged ≈ real with LLM judges)
ran / scored anything:       NO
EVIDENCE_FREEZE:             NONE
B1.1 verdict:                UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
B1.2 / B1.3 prior:           UNCHANGED (not rescued)
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                   B1_3_FIELD_THEORY_EVIDENCE_FREEZE_MANIFEST (draft the lock; still no run)
```

**Structure, not validated meaning.** LLM judges are accepted as the development-first instrument for the
**textual** field claim under strong controls and a weak, explicit label; nothing is run or claimed as
evidence, prior results are unchanged, Track B remains BLOCKED, and human-felt validation remains a separate
later layer.
