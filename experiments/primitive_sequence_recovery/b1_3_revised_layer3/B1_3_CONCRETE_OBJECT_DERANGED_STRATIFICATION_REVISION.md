# B1.3 Concrete-Object LLM Judged-Modulation — Deranged-Stratification Revision

## 1. Scope and status

Protocol revision only. **No final stimuli generated · no judge run · no scoring · no EVIDENCE_FREEZE · prior
results unchanged.** Revises the concrete-object LLM judged-modulation protocol so the single `R_deranged` arm
is stratified into **near / mid / far** deranged controls. Word set (`CONCRETE_OBJECT_WORDLIST_SPEC`),
instrument (`LLM_OBJECT_MODULATION_PROTOCOL_READY`), style/scoring protocol
(`LLM_STYLE_SCORING_PROTOCOL_DRAFT_READY`), and generation/baseline spec (`GENERATION_BASELINE_SPEC_READY`) are
otherwise unchanged. **Structure, not validated meaning.**

## 2. Why a single R_deranged is insufficient

`R_deranged` (another word's varṇa-derived modulation) tests **object-specificity** — is this *this* object's
field? But the **semantic/object-function distance** of the source word changes the difficulty:

- **Far** deranged (very different function family) is an **easy** control — beating it may only show broad
  category/function coherence, not word-specific modulation.
- **Near** deranged (adjacent object-function) is a **hard** control — beating it is the strongest evidence of
  word-specificity.
- **Mid** deranged (concrete but different function family, not absurd) is the best **primary practical** test —
  neither trivially easy nor unfairly hard.

A single undifferentiated `R_deranged` conflates these, so a "win" could be category-level while reading as
word-specific. The controls must therefore be **stratified**.

## 3. Deranged strata

**`R_deranged_near`** — source word semantically/functionally close to target; same or adjacent
concrete-object family; similar object-function where possible.
*e.g. knife vs needle/scissors/blade; cup vs bowl/bottle; bridge vs road/gate.*

**`R_deranged_mid`** — source word concrete and stable but a **different function family**; not obviously
opposite or absurd.
*e.g. knife vs rope/key/cup; cup vs lamp/box; wall vs table/rope.*

**`R_deranged_far`** — source word concrete but a **very different function family**.
*e.g. knife vs pillow/river/mountain; cup vs wall/stone; bridge vs bowl/lamp.*

## 4. Matching policy

- Use the **frozen object categories** from the candidate wordlist (`concrete_object_*` families).
- Use **WordNet path/Wu-Palmer similarity** (or simple category-distance) to bin a source as near/mid/far
  relative to the target; thresholds recorded.
- **Deterministic seed + tie-breaks** for source selection within a stratum.
- **No cherry-picking**; **no selecting deranged sources after seeing generated tags**; **no** obviously
  comical/nonsensical pairings that would make `far` artificially easy.
- Source assignment is **frozen before judging** and hash-bound at freeze.

## 5. Arm list revision

Replace single `R_deranged` with **`R_deranged_near` · `R_deranged_mid` · `R_deranged_far`**. Retain
**`A_real` · `R_scrambled` · `R_random` · `X_neutral` · `semantic_only_baseline`**. Optional
`R_semantic_near` / `R_varṇa_near` only if **not duplicative** of `R_deranged_near`.

## 6. Endpoint revision

**Primary endpoint → `A_real` vs `R_deranged_mid`** on the primary concrete-object set — mid is neither
trivially far nor unfairly near, and tests object-specificity **beyond broad concrete-object coherence**.

**Required secondary deranged endpoints:** `A_real` vs `R_deranged_far`; `A_real` vs `R_deranged_near`.

**Interpretation:**
- **Strong success** — `A_real` beats near, mid, and far.
- **Moderate success** — `A_real` beats mid and far; near remains close.
- **Weak / category-only** — `A_real` beats far only.
- **Failure** — `A_real` fails against mid or far.

## 7. Required comparisons after revision

`A_real` vs **R_deranged_mid** · **R_deranged_far** · **R_deranged_near** · **R_scrambled** · **R_random** ·
**X_neutral** · **semantic_only_baseline**.

## 8. Success-criteria revision

To earn a future `LLM_OBJECT_MODULATION_SIGNAL`:

- `A_real` beats `R_deranged_mid`.
- `A_real` beats `R_deranged_far`.
- `A_real` beats `R_scrambled`.
- `A_real` beats `R_random`.
- `A_real` beats `X_neutral`.
- `A_real` beats **or adds beyond** `semantic_only_baseline`.
- `A_real` vs `R_deranged_near` is **reported as a hard specificity test**; the **strong form requires
  `A_real > R_deranged_near`**.
- If `A_real` **fails near but passes mid/far**, label the result **weaker/category-level** and **do not
  overclaim word-specificity**.

## 9. Kill-criteria revision

**STOP** if any: `A_real ≈ R_deranged_mid` · `A_real ≈ R_deranged_far` · `R_scrambled` matches or beats
`A_real` · `R_random` matches or beats `A_real` · `X_neutral` matches or beats `A_real` ·
`semantic_only_baseline` matches or beats `A_real` · effect appears **only against far deranged** ·
near/mid/far sources were **cherry-picked after tag inspection** · style or denotation leakage fails.

## 10. Statistical-reporting revision

Report **separately**: near-deranged result · mid-deranged result · far-deranged result · **gradient pattern**.

**Expected gradient if signal is real:** `A_real` advantage generally **far strongest, mid moderate, near
weakest** (harder to beat closer sources). **Required minimum:** `A_real` must beat **mid and far**. A flat or
inverted gradient (e.g., beating near but not far) is a red flag for an artifact.

## 11. Examples — NOT FINAL STIMULI

> **Illustrative only. NOT FINAL STIMULI. NOT EVIDENCE.** Final source assignment comes from the frozen
> deterministic matching rule (§4), not these hand picks.

- **knife** — near: needle / scissors · mid: rope / key · far: pillow / river
- **cup** — near: bowl / bottle · mid: lamp / box · far: wall / mountain
- **bridge** — near: road / gate · mid: table / rope · far: cup / pillow

## 12. Downstream specs amended by this memo

This memo is the **controlling revision** (until later consolidated) for:

- **LLM judge revision** (`B1_3_CONCRETE_OBJECT_LLM_JUDGE_REVISION`) — required-comparison list expanded.
- **Style/scoring protocol** (`…LLM_STYLE_AUDIT_AND_SCORING_PROTOCOL`) — `required_comparisons`, primary
  endpoint, success/kill criteria now use the three deranged strata.
- **Generation/baseline spec** (`…LLM_GENERATION_AND_BASELINE_SPEC`) — `R_deranged` construction now produces
  three stratum-specific arms via the §4 matching rule.
- **Future scoring/freezing manifest** — must bind the three deranged arms and the mid-primary endpoint.

Prior specs are **not rewritten**; this memo governs where they differ, until a consolidation pass.

## 13. Decision

```
DECISION: DERANGED_STRATIFICATION_SPEC_READY
```

Stratifying `R_deranged` into near/mid/far, moving the primary endpoint to `A_real` vs `R_deranged_mid`, and
requiring the full gradient with a deterministic frozen matching rule makes the object-specificity test
**sharper and harder to fool** (a category-only win can no longer masquerade as word-specificity). This is not
`DERANGED_STRATIFICATION_HIGH_RISK_NEEDS_REVISION` (the matching rule is deterministic and cherry-picking is
gated) and not `DERANGED_STRATIFICATION_REJECTED` (stratification is a legitimate strengthening of the crux
control). No stimuli generated; §11 examples are illustrative only.

## 14. Final status block

```
document:                    B1.3 concrete-object DERANGED-STRATIFICATION revision (protocol revision only)
decision:                    DERANGED_STRATIFICATION_SPEC_READY
change:                      single R_deranged -> R_deranged_near / R_deranged_mid / R_deranged_far
primary endpoint:            A_real vs R_deranged_mid on primary concrete objects (was: A_real vs R_deranged)
required comparisons:        A_real vs mid / far / near / R_scrambled / R_random / X_neutral / semantic_baseline
interpretation:              strong=beat near+mid+far; moderate=mid+far; weak=far-only; fail=lose mid or far
required minimum:            A_real must beat mid AND far
final stimuli generated:     NO (§11 examples illustrative, NOT FINAL, NOT EVIDENCE)
ran LLM judges / scoring:     NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL: NOT earned
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
next:                        screen final list, freeze deranged source map, generate stimuli, run style audit
```

**Structure, not validated meaning.** The deranged control is stratified into near/mid/far with the primary
endpoint moved to mid; no final stimuli were generated, no judges were run, nothing was scored, prior nulls and
closures stand, Track B remains BLOCKED, and EVIDENCE_FREEZE is not declared.
