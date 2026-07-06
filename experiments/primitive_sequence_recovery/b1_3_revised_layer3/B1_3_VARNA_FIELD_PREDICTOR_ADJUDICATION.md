# B1.3 Varṇa→Field Predictor Adjudication

## 1. Scope

Adjudicates **how (or whether) to construct a frozen, non-circular varṇa→field-vector predictor** for the
B1.3 field-theory test. Adjudication/design memo only: no final scoring, no LLM-judge run, no evidence-stimulus
generation, **no EVIDENCE_FREEZE**. No prior B1/B1.1/B1.2/B1.3 result is changed or rescued, and no
`LLM_PROPENSITY_FIELD_DISCRIMINATION` / `PROPENSITY_MODULATION_SIGNAL` / `LIMITED_GENERATION_UTILITY` /
`MAPPING_FIDELITY_SIGNAL` / ontology / Sanskrit / semantic-truth / Track-B claim is made. **Structure, not
validated meaning.**

## 2. Required output dimensions

Predict a **field vector** over dimensions that are register/propensity, **not** denotation:

| dimension | why it is field, not meaning |
|---|---|
| warmth · intimacy | affective coloring shared by many denotations |
| formality · distance | register, independent of what a word denotes |
| potency · authority | force/dominance texture, not category |
| softness/hardness | perceptual/dynamic quality, not definition |
| dependency · containment/expansion | relational/dynamic tendency |
| activity · calm/force | motion/energy texture |

None of these tells you *what a word denotes*; they describe the *field* a form carries — the thing synonyms
differ on with denotation held fixed.

## 3. Candidate predictor types

- **A. Fixed varṇa contribution table** — each varṇa → a fixed vector over the dimensions; word vector =
  composition. *Order-invariant → `scrambled = real` → fails a core control.*
- **B. Role-sensitive contribution table** — contribution varies by **position/pole** (onset/coda/first/
  doubled/vowel-following), reusing the existing frozen `read_op` pole rule. *Order-sensitive → `scrambled ≠
  real` possible.*
- **C. Sequence-composition rule** — combine varṇa vectors by weighted/position/interaction rules (not a bare
  sum).
- **D. Pseudoword-first calibration** — development-only calibration on pseudowords, frozen before real
  evidence. *Risk: "calibration" can slide into tuning-to-target; must be blind and frozen, and even so tests
  a learnable map, not the ontology.*

## 4. Preferred solution

**Route B + C: a role-sensitive fixed contribution table with a deterministic, order-sensitive composition
rule.** Rationale: (i) it reuses Symbol-U's **already-frozen** pole/position rule (`read_op`), so poles aren't
a new free choice; (ii) order-sensitivity lets `scrambled` diverge from `real` (a required control); (iii) it
takes **no dictionary input**; (iv) table + rule are **hash-bindable** before scoring. Plain fixed table (A)
is rejected (order-invariant). Learned calibration (D) is dev-only and reframes the hypothesis.

## 5. Building the table without circularity

**Allowed sources (all predate this field test):**

- the **existing frozen Symbol-U varṇa glossary** (`varna_lens/lexicon_authoritative_varna.json`; the
  binding/liberating pole glosses), and prior theoretical mapping docs;
- a **manually specified** dimension-value-per-varṇa table **only if** authored **before** any ratings and
  labeled development-origin, by a coder **blind to the test-word list and to which varṇas they contain**,
  with **inter-coder agreement** reported.

**Forbidden:** tuning to LLM/human field ratings; tuning to synonym examples; using mother/mama/father (or any
test word) to choose weights; any change to the table after seeing results. The table is authored from **the
varṇa's own glossary description → dimension values**, uniformly, then frozen + hashed.

## 6. Composition rule (to be pinned in the predictor spec)

- **Per-varṇa vector** from the role-sensitive table (pole/position from `read_op`).
- **Repeated sounds:** counted per occurrence with the doubled-consonant pole rule already in `read_op`.
- **Onset/coda weights:** fixed, pre-registered (e.g., onset weighted vs coda), same for all words.
- **Vowels:** handled by the frozen vowel-attachment rule (they set consonant poles; vowel own-contributions
  pinned or excluded — a declared choice).
- **Unknown/missing sounds:** dropped by rule + logged (no silent imputation).
- **Normalization:** L2 or L1, pre-registered, identical for real and all control arms.

## 7. Pseudoword-first requirement

**Pseudowords are the primary clean test:** no learned convention, no denotation, no register. The predictor
maps novel forms → field vectors; LLM/human rate the same forms; compare vs scrambled/random/generic
sound-symbolism. **Real synonyms are secondary** and only interpretable through the confound baseline (§8).

## 8. Confound-baseline interface

The final analysis compares the Symbol-U predictor against a baseline of: **frequency, length, syllable count,
reduplication, generic sound-symbolism features, sonority, hard/soft consonant counts, front/back vowels,
etymology/register proxies.** Symbol-U must add **ΔR² beyond** these (the §8 analysis of the measurement
spec). The predictor's outputs must be structured so this regression is well-posed (fixed-length numeric
vectors, aligned dimensions).

## 9. Controls

**scrambled** varṇa predictor · **deranged** (another word's varṇas) · **random** mapping · **neutral/no-varṇa**
· **generic sound-symbolism baseline** · **sound-neighbor** controls. Real must beat scrambled/deranged/random/
neutral **and** add beyond generic sound-symbolism.

## 10. Freeze-ready success criteria (development pre-checks, before any evidence)

- outputs **non-degenerate** field vectors (variance across forms, not all-same);
- **distinguishes pseudowords** (different forms → different vectors);
- **not all vectors dense/identical** (entropy/density within bounds);
- **`scrambled ≠ real`** and **`random ≠ real`** at the vector level;
- **no dictionary leakage** (predictor provably uses only sound/varṇa inputs);
- dimensions **align** with the rating dimensions (§2);
- table + composition rule **hash-bindable**.

## 11. STOP conditions

STOP if: **no** non-circular contribution table can be specified; the predictor **requires dictionary
meaning**; it **requires tuning to ratings**; **all outputs are generic/same** (degenerate); **`scrambled =
real`**; it **merely duplicates generic bouba/kiki** features (no incremental structure); or the **dimensions
are too vague to score** reliably.

## 12. Decision

```
DECISION: VARNA_FIELD_PREDICTOR_HIGH_RISK_NEEDS_TABLE_SPEC
```

A non-circular predictor **is specifiable in principle** — Symbol-U has a frozen varṇa glossary predating this
test, and a role-sensitive table + `read_op` + deterministic composition can be authored blind and hash-bound.
So `NOT_FEASIBLE_STOP_NOW` is too strong. **But** `FEASIBLE_TO_SPEC` is too generous, for two real reasons the
table construction must confront first:

1. **Degeneracy is the *likely* outcome.** The table would be built from the **same glosses** the prior arc
   showed carry no word-specific signal (ρ≈0, `V_deranged ≈ V_real`). Composed field vectors may inherit that
   genericness and collapse to near-identical vectors — tripping the §11 STOP. This must be settled by a
   **development non-degeneracy pre-check on pseudowords** *before* committing to a full predictor spec.
2. **Interpreter degrees of freedom + dimension-mismatch.** Mapping each varṇa's gloss → numeric field-dimension
   values is an interpretive act with real bias surface (blind authoring, pre-registration, inter-coder
   agreement all required), and Symbol-U's varṇa qualities are **vṛtti** (mental tendencies), which may not map
   cleanly onto affective/sensory **field** dimensions — a theoretical choice needing justification.

Hence **high-risk: the table construction needs its own dedicated adjudication** (blind-authoring protocol +
degeneracy pre-check + dimension-mapping justification) before a predictor spec or freeze.

## 13. Next gate

```
next gate: B1_3_VARNA_FIELD_TABLE_RISK_ADJUDICATION
```

(Resolve the blind-authoring/circularity protocol, run a development-only **non-degeneracy pre-check** on
pseudowords, and justify the vṛtti→field-dimension mapping. If the table is authored non-circularly **and**
passes non-degeneracy → `B1_3_VARNA_FIELD_PREDICTOR_SPEC`. If it can only be made non-degenerate by tuning to
ratings, or collapses → `VARNA_LINE_CLOSURE_MEMO`.)

## 14. Final status block

```
document:                    B1.3 varṇa→FIELD PREDICTOR adjudication (design only)
decision:                    VARNA_FIELD_PREDICTOR_HIGH_RISK_NEEDS_TABLE_SPEC
preferred route:             role-sensitive fixed table (B) + deterministic order-sensitive composition (C)
non-circular source:         existing frozen varṇa glossary (predates this test), blind-authored, hash-bound
biggest risk:                degeneracy — table inherits the known-generic glosses (ρ≈0, deranged≈real)
ran / scored anything:       NO
EVIDENCE_FREEZE:             NONE
B1.1 verdict:                UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
B1.2 / B1.3 prior:           UNCHANGED (not rescued)
LLM_PROPENSITY_FIELD_DISCRIMINATION / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                   B1_3_VARNA_FIELD_TABLE_RISK_ADJUDICATION
```

**Structure, not validated meaning.** A frozen, non-circular varṇa→field predictor is specifiable in principle
from the existing glossary, but its table construction carries a serious degeneracy risk (it inherits the same
generic glosses that returned nulls) and interpreter/dimension-mapping risks; these must be adjudicated with a
development non-degeneracy pre-check before any predictor spec or freeze. Nothing is run or claimed as
evidence, prior results are unchanged, and Track B remains BLOCKED.
