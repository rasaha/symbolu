# B1.3 Field-Theory — Confound-Controlled Measurement Spec (v3.2, development)

## 1. Scope and non-rescue rule

Measurement-spec revision to the B1.3 field-theory / LLM-judge plan, correcting the kinship-word confound and
defining a broad-synonym + pseudoword + **incremental-over-confounds** analysis. Design/spec only: no
implementation, no judge run, no stimulus generation, no scoring, **no EVIDENCE_FREEZE**. Does not change any
prior B1/B1.1/B1.2/B1.3-v1 result, does not rescue them, and claims **no** Symbol-U validation /
`PROPENSITY_MODULATION_SIGNAL` / `LLM_PROPENSITY_FIELD_DISCRIMINATION` / `LIMITED_GENERATION_UTILITY` /
`MAPPING_FIDELITY_SIGNAL` / ontology / Sanskrit privilege / semantic truth / Track-B unblock. Status stays
`DEVELOPMENT_FREEZE · NOT_EVIDENCE_FROZEN · NOT_RUN`. **Structure, not validated meaning.**

## 2. Why kinship triples are high-confound

mother/mummy/mama and father/dad/papa are vivid **illustrations** but poor **evidence**. The mama/papa/dada
forms are near-universal across unrelated languages because of **infant babbling** (bilabial /m/,/p/ + open
/a/, earliest-acquired, produced while nursing — Jakobson), compounded by **reduplication**, **diminutive
morphology**, **early acquisition**, **caregiver context**, and **register convention**. A correct Symbol-U
"prediction" on these forms may only **rediscover known developmental phonetics and convention** — and because
/m/,/a/ *are* the babble sounds, any mapping built on them predicts intimacy for free. Therefore kinship
triples appear **only as a labeled high-confound diagnostic subset**, reported separately, **never** as the
headline test.

## 3. Correct measurement target

Not denotation. The target is **field/register/propensity as a continuous, multi-dimensional profile** —
predict a word/form's position on fixed dimensions: **formality, intimacy, warmth, dependency, distance,
potency, activity, softness/hardness, sacred/institutional tone, domestic/personal tone.**

## 4. Broad synonym pool

- **Large, diverse** synonym / near-synonym set across many semantic domains; target **60–100+ groups**.
- Domains include (not limited to): size (big/large/huge), emotion (angry/mad/furious), dwelling
  (home/house/dwelling), action (throw/hurl/toss), speech (say/utter/speak), fear (afraid/fearful/scared),
  power (strong/mighty/powerful), care (protect/guard/shelter).
- **Kinship terms are not the main evidence** (high-confound subset only, §2).
- Selection frozen before ratings; eligibility = cmudict/varṇa-routable, WordNet-present, shares denotation
  within group.

## 5. Field-vector rating protocol

- **LLM panel** rates each word/form on the fixed field dimensions (§3) on a **1–7 numeric scale**.
- **Neutral frame** ("the word *X*") plus a small set of **anchored contexts** (per §6 of the LLM-judge
  revision) to capture context-modulation.
- **Multiple judge families** if available; **temperature fixed/deterministic**; **position/order balanced**;
  **no arm labels**; hypothesis-blind prompts.
- Output: a **measured field vector per word/form** (the prediction target).

## 6. Symbol-U prediction protocol

- Symbol-U must produce a **field vector prediction from varṇa/form**, **frozen before** any LLM ratings are
  seen; **no post-hoc tuning to ratings**.
- The varṇa prediction arm may use **only** varṇa/form information (varṇa sequence, pole, position) via a
  **fixed rule authored from the varṇa lexicon's own definitions** — **not** the test words' field ratings,
  **not** dictionary meaning, **not** usage statistics (those enter only as the §7 baseline).
- **Open prerequisite (see §15):** whether such a **frozen, non-circular** varṇa→field-dimension rule can be
  specified without tuning to the target is unresolved — the same crux that stopped the B1.3-v1 varṇa→feature
  model. This spec defines the measurement; the prediction-rule feasibility is adjudicated next.

## 7. Confound baseline

The convention/surface baseline model uses features known to drive field independent of any varṇa ontology:
**word frequency; length; syllable count; phoneme count; reduplication flag; diminutive-morphology flag;
etymology class (Germanic/Latinate/…) where available; register/frequency proxy; front/back vowel counts;
sonority; hard/soft consonant counts; and generic bouba/kiki-style sound-symbolism features.** This is the bar
Symbol-U must clear.

## 8. Primary analysis — incremental ΔR²

- **Model 1 (baseline):** measured field vector ~ confound baseline (§7).
- **Model 2 (baseline + Symbol-U):** confound baseline + Symbol-U varṇa field predictions.
- **Primary result = the incremental explained variance** (ΔR² / partial correlation) from **adding
  Symbol-U beyond the baseline**, per-dimension and aggregate.
- Symbol-U must **improve prediction beyond convention**, not merely beat chance.
- **Cross-validated** (held-out words) to avoid overfitting; **multiplicity-corrected** across dimensions.
- Report ΔR² with CIs; a null ΔR² (Symbol-U adds nothing over confounds) is the expected-and-believable
  negative given all priors.

## 9. Control arms (specificity)

Retain: **real** Symbol-U mapping · **scrambled** varṇa · **deranged** (another word's) · **random** ·
**neutral/no-varṇa** · **sound-neighbor** · **generic sound-symbolism baseline**.

Requirements: real must **beat scrambled/deranged/random/neutral**, and must **add beyond the generic
sound-symbolism baseline**. **If deranged ≈ real → STOP.** **If generic sound-symbolism explains the same
variance → the Symbol-U-specific claim fails** (it's rediscovering phonaesthetics, not its ontology).

## 10. Pseudoword arm (cleanest isolation)

- **Novel forms**, no learned convention; controlled for **length, syllable count, reduplication, phonotactic
  plausibility**.
- Symbol-U predicts field ratings **before** LLM/human ratings; compare vs **scrambled/random/generic
  sound-symbolism** baselines.
- This is the one arm where a hit **cannot** be "it learned the convention" (there is none to learn).
- Existing project pseudoword work (`crs_pseudoword_test.py`, `RESULTS_CRS_PSEUDOWORD_B.md`) **may be
  referenced but must be re-reviewed — not treated as current evidence.**

## 11. Style and prompt controls

- Rating prompts **must not reveal Symbol-U logic**; **no** "which is deeper/spiritual" framing.
- Ask for **field/register dimensions** (numeric ratings or forced rankings), **not** prose-explanation
  preference.
- If explanations are collected (diagnostics only), run a **style/length/fluency audit**; if the real arm is
  identifiable by style, **STOP**.

## 12. Success criteria (future frozen run)

- Symbol-U adds **significant ΔR² beyond the confound baseline** (cross-validated, corrected);
- real mapping beats **scrambled, deranged, random, neutral, and the generic sound-symbolism baseline**;
- effect appears **across multiple semantic domains**, **not** driven only by kinship/babble terms;
- **pseudoword arm** shows above-baseline prediction (if included);
- **multiple LLM judge families** agree directionally;
- **no style/prompt leakage**.

Allowed future label: **`LLM_PROPENSITY_FIELD_DISCRIMINATION` only** (after EVIDENCE_FREEZE).

## 13. Kill criteria

STOP / null if: Symbol-U adds **no ΔR²** beyond confounds · scrambled/deranged/random ≈ real · **generic
sound-symbolism explains the same variance** · effect exists **only in kinship/babble** words · ratings driven
by **frequency/register convention only** · **pseudoword arm fails** (if used as required) · **prompt/style
leakage** detected · results depend on **one judge model** only.

## 14. Relationship to prior results

This does **not** rescue B1/B1.1/B1.2/B1.3-v1. Those remain valid for the **dictionary-meaning** and
**bridge-gloss** designs. This is a **new field/register prediction** design with a confound-controlled
analysis. **No positive label is earned.**

## 15. Decision

```
DECISION: CONFOUND_CONTROL_MEASUREMENT_SPEC_HIGH_RISK_NEEDS_ADJUDICATION
```

The **measurement/analysis framework is sound and testable** — broad diverse pool, multi-dimensional field
target, ΔR²-over-confounds, strong specificity arms, generic-sound-symbolism baseline, and a pseudoword arm.
That part is `…READY`-grade. But it inherits **one unresolved prerequisite**: §6 requires a **frozen,
non-circular varṇa→field-dimension prediction rule**, and whether Symbol-U can produce one **without tuning to
the target** is exactly the crux that stopped the B1.3-v1 varṇa→feature model (no pre-existing non-circular
varṇa→feature map; bridge glosses generic). So `…READY_FOR_FREEZE_PACKAGE` **overstates** — you cannot freeze a
package whose prediction rule isn't shown to be specifiable non-circularly. `…NOT_TESTABLE_STOP_NOW`
**understates** — the analysis is genuinely testable *if* a non-circular field rule exists, and a pseudoword
arm gives a clean isolation. Hence **high-risk, needs adjudication** of the prediction-rule feasibility before
any freeze package.

## 16. Next gate

```
next gate: B1_3_FIELD_THEORY_CONFOUND_RISK_ADJUDICATION
```

(Adjudicate whether a frozen, non-circular **varṇa→field-dimension** prediction rule can be specified — authored
from the varṇa lexicon's own definitions, blind to the test words' field ratings. If yes →
`B1_3_FIELD_THEORY_EVIDENCE_FREEZE_PACKAGE_DRAFT`. If it can only be produced by tuning to ratings →
`VARNA_LINE_CLOSURE_MEMO`.)

## 17. Final status block

```
document:                    B1.3 field-theory CONFOUND-CONTROL measurement spec (v3.2; development only)
decision:                    CONFOUND_CONTROL_MEASUREMENT_SPEC_HIGH_RISK_NEEDS_ADJUDICATION
measurement framework:       sound/testable (broad pool · multi-dim field · ΔR²-over-confounds · arms · pseudoword)
unresolved prerequisite:     frozen NON-CIRCULAR varṇa→field prediction rule (same crux as B1.3-v1)
ran / scored anything:       NO
EVIDENCE_FREEZE:             NONE
B1.1 verdict:                UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
B1.2 / B1.3-v1 prior:        UNCHANGED (not rescued)
LLM_PROPENSITY_FIELD_DISCRIMINATION: NOT earned
PROPENSITY_MODULATION_SIGNAL:        NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                   B1_3_FIELD_THEORY_CONFOUND_RISK_ADJUDICATION
```

**Structure, not validated meaning.** The confound-controlled field measurement is specified and testable in
its analysis, but rests on an unresolved non-circular varṇa→field prediction rule; nothing is run or claimed
as evidence, prior results are unchanged, Track B remains BLOCKED, and the prediction-rule feasibility must be
adjudicated before any evidence-freeze package.
