# B1.3 Field-Theory Preregistration (DRAFT — development, not evidence-frozen)

```
status:            PREREG_DRAFT · DEVELOPMENT_FREEZE · NOT_EVIDENCE_FROZEN · NOT_RUN
revision:          v3 (human-evaluation field variant; supersedes the v2 automated-affective instrument
                   as the EVIDENTIAL instrument — see revision log in the workplan)
authorizes a run?  NO — a run counts as evidence ONLY after an explicit EVIDENCE_FREEZE is declared
```

## 1. Scope and non-rescue rule

Preregisters (in draft) a test of the **field-theory** reframing of Symbol-U. Design/prereg only: no run, no
generation, no rating, no scoring, no models. It does **not** rescue or change any prior result (B1.1
`RANDOM_OR_SCRAMBLED_MATCHES`, B1.2 failures, B1.3-v1 ρ≈0), and makes **no**
`LIMITED_GENERATION_UTILITY` / `MAPPING_FIDELITY_SIGNAL` / ontology / Sanskrit-privilege / semantic-truth /
Track-B claim. **Structure, not validated meaning.**

## 2. The field-theory hypothesis

- Varṇa mappings are **propensities/fields**, **not** the word's meaning. The dictionary fixes *what a word
  denotes*; the varṇa field is the *tendency / texture / pressure / movement* the word-form carries **on top
  of** that fixed denotation.
- **Level:** the claim is pitched at the **manomaya** (mental) level — a mental propensity, not an acoustic/
  articulatory (annamaya) effect. This prereg therefore does **not** test sound-symbolism physics; it tests
  the claim's **third-person shadow**: whether the varṇa field produces a **convergent, controlled human
  response** that a wrong field does not.
- **Synonym intuition (the isolation):** *father* and *papa* share a denotation but carry different fields.
  Because meaning is held constant across synonyms, any reliable field difference cannot come from denotation.
- **Coherence claim:** word choice is (partly) governed by the field a speaker wants; the form and its effect
  cohere. The test asks whether that coherence tracks the **word's own** varṇa field above wrong fields.

## 3. What this preregisters — and what it cannot reach

- **Can test (third-person shadow):** do blinded human raters, reading **full generated prose**, judge a
  word's **own** varṇa-conditioned generation as *more genuinely that word* than generation conditioned on a
  **deranged / scrambled / random / neutral** field — above chance, with controls?
- **Cannot reach:** the *pure* manomaya propensity as directly apprehended in trained awareness. If the claim
  is defined to produce **no** third-person observable, it is outside any experiment (empirically private) —
  neither validated nor refuted here. This prereg only tests the version that casts a measurable shadow.

## 4. Instrument — human evaluation (and why)

- **Human raters, not LLM judges.** For a mental/field claim, an LLM judge models learned text statistics —
  the wrong instrument. B1.1 used LLM judges and found own ≈ deranged; that does **not** settle a field claim.
  Humans are the appropriate instrument; this is the one instrument the project has **not** used.
- This is a deliberate instrument change over the same stimulus family (full varṇa-conditioned generation),
  **not** a rerun.

## 5. Stimulus — full generation, not skeletons

- Judged objects are **full, fluent generated passages** (varṇa-conditioned), **not** feature checklists or
  abstract signatures — a felt field needs a felt object.
- **Style/length/fluency matched** across all arms (real and controls) by frozen decoding params and a
  post-generation length/register normalization, so the comparison cannot ride on one passage being written
  better. (The B1.2 prose style-tell hit 0.70 — this control is mandatory, not optional.)

## 6. Arms — retained from B1.2 (two-axis: semantic × varṇa)

Per target word, generate passages conditioned on:

- **A — real** (word's own varṇa field)
- **R_deranged** — another word's varṇa field (**the crux control**)
- **R_scrambled** — the word's own varṇas, order-permuted (tests order/sequence)
- **R_varṇa-near / semantic-far** — a sound-neighbor's field (sound-transfer confound; e.g. father↔feather)
- **R_semantic-near** — a synonym/near-neighbor's field (father↔guardian) — fine discrimination
- **R_random-screened** — random field, excluding semantic AND varṇa neighbors
- **X — neutral / no-varṇa** — baseline floor

## 7. Task — anchored forced choice (not "which do you like")

- Primary task: *"Both passages are about **<word>**. Which reads as more genuinely* **<word>** *— its
  essence/role — not merely which is better written?"* — **forced choice**, blinded order.
- The judgment is **anchored to the target word** (never bare "which do you connect with," which measures
  prose taste). Optional secondary: rate each passage on pre-registered field dimensions (potency, warmth,
  hardness, distance, movement) for a convergence check.

## 8. Blinding

Opaque passage IDs; **no arm labels, no varṇa/Sanskrit/mapping metadata**; order shuffled by a frozen seed;
private truth-map stored separately, revealed only at scoring; raters blind to the hypothesis.

## 9. Rater strata (the dilemma, resolved up front)

- **Naive raters** (no Sanskrit, no Symbol-U doctrine) — a hit here can't be shared training.
- **Trained raters from independent traditions/lineages** — convergence across *independent* doctrines guards
  against "they all learned the same mapping."
- **Pre-registered interpretation:** a signal counts only if it appears in **naive** raters *or* converges
  across **independent** trained groups. A signal present **only** within one trained group is scored as
  **shared doctrine / demand characteristics**, not field perception (kill, §11).

## 10. Primary endpoint & success criteria

Success requires **all**:

- **A beats R_deranged** on the anchored forced choice — selection rate > 0.5, rater- **and** item-clustered
  CI lower bound above chance;
- **A beats R_scrambled** (order matters) and **A beats R_random / X**;
- **R_varṇa-near does not win** (result is not sound-transfer);
- a **distance gradient** where expected (A ≥ R_semantic-near > R_random);
- survives **inter-rater agreement** thresholds, **multiplicity** correction, and the **style/projection/
  doctrine** controls (§5, §11);
- appears in **naive** or **cross-tradition** raters (§9).

**Only reachable positive label:** `PROPENSITY_MODULATION_SIGNAL` (field variant), **after** a future
EVIDENCE_FREEZE run. Never `MAPPING_FIDELITY_SIGNAL`, `LIMITED_GENERATION_UTILITY`, ontology, Sanskrit
privilege, semantic truth, or Track-B unblock.

## 11. Kill criteria

- **R_deranged ≈ A** (another word's field reads as this-word equally) — the B1.1/B1.2 wall; primary kill.
- **R_scrambled ≈ A** — order carries nothing.
- **R_random / X ≈ A** — any conditioning suffices.
- **R_varṇa-near wins** — it's sound-transfer, not field.
- **Raters can identify arm by style** (style-tell audit fails) — prose-quality confound, not field.
- **Effect only among one trained group** — shared doctrine / demand characteristics, not perception.
- **Real generation hand-polished** or arms not style/length-matched — invalid.
- **Real field fits many target words** (triviality) — generic resonance, not word-specific field.

## 12. Confound controls (integrity core)

Frozen rule-based generation (no per-word hand-polishing); style/length/fluency matching + a **style-tell
audit** on the passages before rating; anchored (not bare-preference) task; naive + cross-tradition raters;
demand-characteristic controls (hypothesis-blind, filler items, attention checks); triviality check (A must
not read as every word); pre-registered thresholds fixed before any rating.

## 13. Statistical plan

Forced-choice selection rate vs 0.5; **rater-clustered and item-clustered** bootstrap CIs; Holm–Bonferroni
across the co-primary arm comparisons; per-stratum breakdown (naive / trained-by-tradition); pre-registered
**power** target fixing #items × #raters before running; sensitivity analyses (drop-rater, drop-item,
drop-lowest-agreement); style-tell audit reported alongside.

## 14. Honest scope of any positive

A clean positive would show **human sensitivity to a word's own varṇa field above strong controls** — a real,
modest, **sound-symbolism-adjacent** result about *human response*, **not** validation of the specific varṇa
ontology, Sanskrit privilege, or semantic truth. Documented form→field effects are weak; the prior is small,
and the crux (`R_deranged`) has defeated every prior instrument.

## 15. Freeze & run gating (what must happen before this is evidence)

1. **EVIDENCE_FREEZE declaration** (explicit) — hash-binding this prereg, the generation rule, arms, seeds,
   rater protocol, and thresholds.
2. Human-subjects **ethics/recruitment** and rater-strata sourcing.
3. Generation run (frozen) → style-tell audit → **human rating** run → scoring per §10/§13.

None of these is authorized here. Until step 1, this is a revisable development draft.

## 16. Status block

```
document:                    B1.3 FIELD-THEORY preregistration (DRAFT; development; not run)
object:                      varṇa as propensity/FIELD (manomaya-level), NOT word meaning
tests:                       third-person shadow — human, blinded, anchored, deranged-controlled, full prose
instrument:                  HUMAN evaluation (LLM judges deemed wrong instrument for a field claim)
arms:                        B1.2 arms retained (A / R_deranged / R_scrambled / R_varṇa-near / R_semantic-near / R_random / X)
crux control:                R_deranged (defeated every prior instrument — the burden)
only reachable positive:     PROPENSITY_MODULATION_SIGNAL (field), AFTER EVIDENCE_FREEZE only
preregistered / evidence?:   PREREG DRAFT only — NOT EVIDENCE_FROZEN, NOT RUN
B1.1 verdict:                UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
EVIDENCE_FREEZE:             NONE
next step:                   operator review → (optional) EVIDENCE_FREEZE + ethics/recruitment before any run
```

**Structure, not validated meaning.** This preregisters, in draft, the human-evaluation test of the
field-theory reframing; it changes nothing about prior results, claims nothing as evidence, and cannot become
evidence until an explicit EVIDENCE_FREEZE and a controlled human-rating run are separately authorized.
