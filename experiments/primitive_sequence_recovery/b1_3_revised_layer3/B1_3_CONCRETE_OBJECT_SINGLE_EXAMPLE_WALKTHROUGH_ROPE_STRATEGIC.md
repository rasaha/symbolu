# B1.3 Concrete-Object LLM Judged-Modulation — Strategic Single-Example Walkthrough (rope)

## 1. Scope

Explanatory walkthrough only. **No new stimuli · no stimulus modification · no artifact change except this
memo · no judge run · no scoring · no EVIDENCE_FREEZE · no change to thresholds/prompts/judge-config/scorer.**
All values are read verbatim from the committed **v2** artifacts. **Structure, not validated meaning.**

## 2. Why rope is strategically useful

`rope` is concrete and physical, and its **ordinary object-function is binding / holding / tying / restraint /
connection / support**. That makes it a **theory-favorable** probe: if the varṇa-derived `A_real` field carries
any object-function modulation, rope is one of the friendlier places to see it — closer to the vṛtti "binding"
framing than `knife`. The adversarial reading rules:

- If `A_real` **still loses conceptually to the semantic baseline** here, that is a **serious warning** (a
  theory-favorable object where ordinary dictionary semantics win).
- If `A_real` **looks coherent**, that is only a **plausibility check, not evidence**.

## 3. Example target

- **item_id:** `co_023`
- **target word:** `rope`
- **object family:** `tool`
- **dictionary anchor:** *"a length of strong twisted fibre"*
- **neutral context:** *Consider the ordinary object "rope" in a plain, everyday sentence.*
- **WordNet synset:** `rope.n.01`

## 4. `A_real` construction (traced through the actual v2 pipeline)

1. **G2P (cmudict):** `rope` → `[('C','ra','R'), ('V','o','OW1'), ('C','pa','P')]`.
2. **Consonant varṇas:** `ra` (R), `pa` (P).
3. **read_op pole rule:** `ra` is the **first** consonant → **binding**; `pa` is **word-final** → **binding**.
4. **Bridge-pool gloss lookup:**
   - `ra` binding → *"rajasic activation driven by compulsion, desire, projection, or destructive collapse"*
   - `pa` binding → *"revulsion turned against another"*
5. **v2 gloss reduction** (in-band 4–8 plain token; **`rajasic` skipped as banned Sanskrit**; `activation`
   10 chars skipped):
   - *"rajasic activation **driven** …"* → **`driven`**
   - *"revulsion **turned** against another"* → **`turned`** (*revulsion* 9 chars skipped)
6. **Deterministic backfill to 4** (only 2 varṇas route) from the seeded in-band global pool → **`care`,
   `order`**.
7. **Final `A_real` tags:** `['driven', 'turned', 'care', 'order']`
   **Rendered option (verbatim from v2 stimuli):**
   > *"Within the fixed meaning, this object is modulated by driven, turned, care, and order."*

No dictionary meaning was used to choose these tags; no per-item hand-polishing; the v2 global register-polish
kept every token in-band.

## 5. Deranged arms (near / mid / far), from v2 stimuli

| stratum | source | family | basis | rendered other-option |
|---|---|---|---|---|
| **near** | `knife` | tool (same family) | WuP 0.526 | *"…modulated by sting, flight, spell, and stands."* |
| **mid** | `shell` | natural (diff family) | WuP 0.625 | *"…modulated by status, harm, torpor, and agency."* |
| **far** | `leaf` | natural (diff family) | WuP 0.533 | *"…modulated by harm, flight, loss, and grips."* |

**near** (`knife`, same tool family) is the hard word-specificity test; **mid** (`shell`) is the primary
object-specificity control; **far** (`leaf`) is the easiest.

> **Honest caveat (documented WuP coarseness):** rope is one of the flagged **13/53** cases where the
> same-family **near** source (`knife`, WuP 0.526) has a *lower* raw Wu-Palmer than the different-family
> **mid** source (`shell`, WuP 0.625). The strata are defined by **family membership** (near = same family;
> mid/far = different family) — the hard-specificity criterion — **not** raw WuP, so this is expected and was
> pre-disclosed in the final-screen memo; it is **not** hand-fixed here.

## 6. Other control arms (from v2 stimuli)

- **R_scrambled** (same tags, reordered): *"…modulated by turned, care, order, and driven."*
- **R_random** (seeded pool draw): *"…modulated by torpor, speech, holds, and agency."*
- **X_neutral** (content-free filler): *"…modulated by aspect, factor, facet, and nature."*
- **semantic_only_baseline** (dictionary-derived, no varṇa): *"…modulated by length, strong, twisted, and
  fibre."*

## 7. Strategic comparison — `A_real` vs semantic baseline (qualitative, NOT scored)

- **A_real:** `driven, turned, care, order`
- **semantic baseline:** `length, strong, twisted, fibre`

Qualitative read (one reader's impression, **not evidence, not a score**):

- The **semantic baseline directly names rope's physical make-up and function** — *length, strong, twisted,
  fibre* — precisely the ordinary object-function of a rope.
- **A_real** offers generic abstractions: *turned* and *order* faintly gesture at twisting/arrangement, but
  *driven* and *care* do **not** obviously encode **binding / holding / restraint / connection** — the very
  functions that made rope theory-favorable.
- So even on this friendly object, **A_real does not visibly out-fit the semantic baseline**; if anything the
  dictionary-derived tags look **more object-function-fitted**.
- **Verdict for this single example: neutral-to-ADVERSE for the hypothesis.** This is the strategically useful
  outcome the walkthrough was meant to expose: the semantic baseline is a strong competitor precisely because
  it *is* the object's ordinary function.

This is **not evidence** and **not a score** — only an implementation sanity check. It raises the honest prior
that the frozen aggregate may land at `SEMANTIC_BASELINE_EXPLAINS` or `NULL`. That is an acceptable, designed-for
outcome — not a reason to change rope or tune `A_real`.

## 8. Judge-facing block — `A_real` vs semantic_only_baseline

Exactly as the judge would see it (arm identities hidden; position from the frozen `position_seed = 1`):

```
Object: rope
Dictionary meaning: a length of strong twisted fibre
Context: Consider the ordinary object "rope" in a plain, everyday sentence.

Option A: Within the fixed meaning, this object is modulated by length, strong, twisted, and fibre.
Option B: Within the fixed meaning, this object is modulated by driven, turned, care, and order.

Question: Given the dictionary meaning of the object, which option gives a more fitting inner
tendency or field around this object without changing what it is?
Answer with exactly one letter: A or B. Optionally, on a second line, confidence 1-5.
```

**Hidden labels (never shown to the judge):** Option A = `semantic_only_baseline`; Option B = `A_real`.

## 9. Primary-endpoint block — `A_real` vs R_deranged_mid

```
Object: rope
Dictionary meaning: a length of strong twisted fibre
Context: Consider the ordinary object "rope" in a plain, everyday sentence.

Option A: Within the fixed meaning, this object is modulated by status, harm, torpor, and agency.
Option B: Within the fixed meaning, this object is modulated by driven, turned, care, and order.

Question: Given the dictionary meaning of the object, which option gives a more fitting inner
tendency or field around this object without changing what it is?
Answer with exactly one letter: A or B. Optionally, on a second line, confidence 1-5.
```

**Hidden labels (never shown to the judge):** Option A = `R_deranged_mid` (source `shell`'s field); Option B =
`A_real`. Qualitative read: neither option obviously "fits" rope; `A_real`'s *turned/order* is mildly more
plausible than `shell`'s *status/harm/torpor/agency`, but this is a weak, non-scored impression.

## 10. How this affects implementation strategy

- **Freeze can proceed unchanged.** This is a plausibility check, not evidence; the design already contains the
  exact gate that catches this — the **semantic-baseline gate** (`SEMANTIC_BASELINE_EXPLAINS` if the baseline
  matches/beats `A_real`).
- **No new global rule is warranted from this observation.** Adding a rule to make `A_real` express
  binding/restraint would be **tuning the treatment toward the hypothesis** — the opposite of adversarial
  practice. The register-polish (v2) was a *neutrality* fix (no arm reads richer); making `A_real` "more
  fitting" would be gaming.
- **The object-function framing is appropriately hostile to `A_real`** — that is a feature. A theory that only
  survives soft framings is not worth freezing; the concrete-object framing gives ordinary semantics a fair,
  strong baseline.
- **Semantic baseline is a live risk to dominate** — this example makes that concrete. Good: the scorer will
  report it honestly.
- **The example remains viable** for the study (rope is validly generated, audited, and in-band). **Do not
  change rope. Do not tune `A_real`. No per-item rescue.**

## 11. Full-study interpretation

- **One example proves nothing.** rope is **theory-favorable and not representative**; a single object cannot
  support or refute the hypothesis.
- The final decision comes **only** from the frozen aggregate scoring across **all 53 objects** and **all
  required comparisons**.
- **STRONG** requires `A_real` to beat near, mid, far, scrambled, random, neutral, **and** the semantic
  baseline.
- **CATEGORY_LIMITED** requires mid/far/control/baseline success but near weakness.
- **Semantic-baseline parity or superiority → the Symbol-U-specific claim FAILS**
  (`SEMANTIC_BASELINE_EXPLAINS`). This rope example suggests that outcome is a real possibility — honestly
  noted, not hidden.

## 12. Final status block

```
document:                    B1.3 concrete-object STRATEGIC WALKTHROUGH (rope) — explanatory only
object used:                 rope (item_id co_023, family tool)
A_real option:               "…modulated by driven, turned, care, and order." (v2)
semantic baseline option:    "…modulated by length, strong, twisted, and fibre." (v2)
A_real vs semantic-baseline: qualitative read NEUTRAL-TO-ADVERSE (baseline names rope's function directly)
A_real vs mid-deranged:      weak, non-scored; neither clearly fits
artifacts modified:          NONE (read-only; no stimuli regenerated)
ran LLM judges / scoring:     NO
EVIDENCE_FREEZE:             NOT declared
strategic recommendation:    proceed to freeze UNCHANGED; do not tune A_real; let frozen aggregate scoring decide
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL: NOT earned
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
```

**Structure, not validated meaning.** This walkthrough only reads and explains existing v2 artifacts for `rope`,
a deliberately theory-favorable object; the qualitative read is neutral-to-adverse (the semantic baseline names
rope's function directly), no stimuli were generated or modified, no judge was run, nothing was scored, prior
nulls and closures stand, Track B remains BLOCKED, and EVIDENCE_FREEZE is not declared.
