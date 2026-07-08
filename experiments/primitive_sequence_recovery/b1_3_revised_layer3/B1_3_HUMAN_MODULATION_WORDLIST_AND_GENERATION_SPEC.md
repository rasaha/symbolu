# B1.3 Human Modulation — Word List & Generation Spec

## 1. Scope and status

Resolves the first three blockers for the reopened human judged-modulation study: **candidate word list**,
**generation template**, **arm-construction spec**. Preparation/specification only — **no final stimuli
generated, no judging, no scoring, no EVIDENCE_FREEZE.** Prior results unchanged; B1.3 register-field and B1.4
vṛtti paths remain closed; no positive label earned. **Structure, not validated meaning.**

## 2. Word-list principles

Broad, diverse pool; **kinship/register terms are NOT primary evidence** — they are flagged `high_confound`
and **excluded from the primary analyzable set** (diagnostic subset only, reported separately). Include
concrete, body/nature, relational/social, action, affect, abstract/ethical, and spiritual/contemplative
terms. **No cherry-picking** words that already look favorable; **no** words whose "modulation" is obvious
from baby-talk/register alone (that is the confound). Candidate list frozen before any final generation.

## 3. Candidate word list

`b1_3_human_modulation_candidate_wordlist.json` — **72 candidates, 71 eligible** (only *awe* excluded:
vowel-only, no consonant varṇa routing), **66 primary analyzable** (eligible, non-confound), **5 high-confound
diagnostic** (mother/mama/father/papa/dad). Categories: concrete_object 9, body_nature 12, relational_social
9, action_verb 9, affect_emotion 9, abstract_ethical 10, spiritual_contemplative 9, kinship_high_confound 5.
Each item carries word · category · dictionary_anchor · neutral_context · high_confound flag · eligible flag ·
exclusion_reason. **Final frozen list + full eligibility screen remains a downstream blocker.**

## 4. Dictionary anchor policy

The dictionary anchor **fixes denotation**; short, neutral, non-poetic; contains **no** Symbol-U/varṇa/vṛtti
language; **identical across all arms**; **no arm may alter the dictionary meaning**.

## 5. Neutral context policy

Each item has one simple context sentence; it does **not** force a modulation answer, is **not** emotionally
loaded (unless the category inherently is), and is **identical across all arms**.

## 6. Generation-template policy

`b1_3_human_modulation_generation_template_draft.json` — one fixed sentence with **4 field-phrase slots**
(≤4 words each), total length band 22–30 words, **same syntax for every arm**, no poetic flourish, **no new
denotation**, **no varṇa/Sanskrit/pole markers**, no arm-identifying vocabulary. Example shape: *"Within its
fixed meaning, {word} carries a tendency toward {f1}, {f2}, and {f3}, giving the concept a tone of {f4}."* A
**style-tell audit hook** runs on rendered options before any human rating.

## 7. Arm-construction specification

`b1_3_human_modulation_arm_construction_spec.json` — every arm supplies exactly **4 field phrases** into the
**same** template; arms differ **only** in the varṇa-derived field; phrases are derived by a **fixed
reduction rule** from the frozen bridge-pool glosses, normalized to a **shared plain register**, seeded,
**no per-word hand-polishing**. Arms: A_real · R_deranged · R_scrambled · R_random · X_neutral (+ optional
R_semantic_near, R_varṇa_near).

## 8. Real arm — `A_real`

Target word's **real** varṇa sequence (real G2P→varṇa) → `core_A` field phrases. Only the fixed anchor
supplies meaning; **no hand-polishing** to make it fit.

## 9. Deranged arm — `R_deranged`

**Another word's** real varṇa field via a **frozen derangement** π (π(w)≠w), **category/length matched** where
possible. Tests **word-specificity**. No accidental obvious-opposite/favorable pairing; mapping frozen before
judging. *(This is the crux; B1.1 found `R_deranged ≈ A_real`.)*

## 10. Scrambled arm — `R_scrambled`

Same varṇas, **order-disrupted** (`core_S`). Tests **order/structure**. **Critical control** given the prior
automated finding `scrambled ≈ real` (cosine 0.967).

## 11. Random arm — `R_random`

Random field phrases from the pool, excluding the word's own varṇas. Tests **generic symbolic prose**
(does any coherent field suffice?).

## 12. Neutral arm — `X_neutral`

Dictionary-only neutral rendering (no modulation content). Tests whether **modulation adds any value at all**.

## 13. Style-control constraints

Equal length bands; **same number (4) of field phrases**; same syntax; **no arm-specific richer adjectives**;
**no manual editing after arm identity is known** (editing only global/template-level); shared surface-register
normalization so no arm reads richer.

## 14. Blinding preparation

Arm labels hidden; position randomized; pairwise comparisons balanced; **no vocabulary that reveals the real
arm**. Private truth-map stored separately, revealed only at scoring.

## 15. Candidate exclusions

Exclude a word if: no stable dictionary anchor; highly culture-specific; too ambiguous; obvious
baby-talk/register confound (→ high-confound subset); hard to build comparable controls; or modulation would
change denotation. (Applied: *awe* excluded for no varṇa routing; kinship terms flagged, not primary.)

## 16. Freeze-readiness criteria

Ready-as-draft: word list broad + documented ✔; generation template fixed enough for a style audit ✔; arm
rules deterministic enough to implement ✔; **no final evidence stimuli generated** ✔; missing blockers updated
(§ manifest). **Not** freeze-ready — downstream blockers remain (§17 of the reopening draft).

## 17. Decision

```
DECISION: WORDLIST_GENERATION_SPEC_READY_FOR_STYLE_AND_SCORING_PROTOCOLS
```

The three blockers are resolved **as drafts**: a broad 72-word candidate pool (66 primary, kinship quarantined
as diagnostic), a fixed arm-agnostic template with a style-audit hook, and deterministic arm rules with the
crux (R_deranged) and order (R_scrambled) controls. This is not `HIGH_RISK_NEEDS_REVISION` (the specs are
adequate drafts) and not `…NOT_SPECIFIABLE_CLOSE_LINE` (they are specifiable). Next: the style-audit + scoring
protocols and the remaining freeze blockers.

## 18. Final status block

```
document:                    B1.3 human-modulation WORD LIST & GENERATION spec (preparation only)
decision:                    WORDLIST_GENERATION_SPEC_READY_FOR_STYLE_AND_SCORING_PROTOCOLS
candidate word list:         72 (71 eligible, 66 primary non-confound, 5 kinship high-confound diagnostic)
generation template:         fixed 4-slot sentence, 22–30 words, arm-agnostic, style-audit hook
arms specified:              A_real / R_deranged / R_scrambled / R_random / X_neutral (+ optional near arms)
final stimuli generated:     NO
ran humans / LLM judges / scoring: NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 real≈fake; B1.2; scrambled≈real; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
human judged-modulation:     NOT yet run
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL / LLM_PROPENSITY_FIELD_DISCRIMINATION: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next:                        style-audit protocol + scoring/thresholds spec; then remaining freeze blockers
```

**Structure, not validated meaning.** The word list, generation template, and arm-construction rules are
drafted for the reopened human judged-modulation study; no stimuli were generated, nothing was run or scored,
prior nulls and closures stand, Track B remains BLOCKED, and EVIDENCE_FREEZE is not declared.
