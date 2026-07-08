# B1.3 Varṇa→Field Table Risk Adjudication + Development Pre-Check

## 1. Scope and non-evidence rule

Development-only table-risk adjudication with a **non-degeneracy pre-check**. **No** LLM judges, **no** human
raters, **no** field-theory scoring, **no** EVIDENCE_FREEZE. It does not change any prior B1/B1.1/B1.2/B1.3
verdict and earns **no** positive label (`LLM_PROPENSITY_FIELD_DISCRIMINATION` / `PROPENSITY_MODULATION_SIGNAL`
/ `LIMITED_GENERATION_UTILITY` / `MAPPING_FIDELITY_SIGNAL` — none). No ontology / Sanskrit / semantic-truth /
Track-B claim. **Structure, not validated meaning.**

## 2. Table source

Authored **only** from the **frozen** varṇa glosses (`b1_1_bridge_pool_draft.json`; binding/liberating pole
text per varṇa). A **mechanical keyword→dimension lexicon** (authored from the *dimension meanings*, applied
uniformly to all 34×2 glosses) produced a per-varṇa dimension vector. **No** dictionary meaning, WordNet,
synonyms, ratings, or target-word tuning (no mother/papa examples used to set weights). **Single-coder →
flagged HIGH-RISK** (a future freeze would require blind multi-coder authoring + inter-coder agreement).

## 3. Field dimensions — and the defensibility finding

Dimensions from the measurement spec: formality, intimacy, warmth, dependency, distance, potency, activity,
hardness, sacred/institutional, domestic/personal.

**Empirical defensibility** (count of the 68 pole-glosses that touch each dimension):

| well-grounded in vṛtti | value | barely grounded (field-relevant register dims) | value |
|---|---|---|---|
| potency | 31 | warmth | 9 |
| activity | 24 | sacred/institutional | 9 |
| dependency | 14 | intimacy | **5** |
| hardness | 12 | domestic/personal | **5** |
| | | formality | **4** |
| | | distance | **4** |

**Finding:** the varṇa glosses encode **vṛtti** (striving, grasping, pride, restlessness) → they map to
**dynamic** dimensions (potency/activity), but the **register/affective** dimensions that the field-theory
hypothesis is actually about — the ones distinguishing *father/papa* (formality, intimacy, distance,
domestic/personal) — are **barely derivable** (4–5 gloss hits out of 68, i.e. mostly forced/near-empty).

## 4. Vṛtti→field mapping protocol

Mechanical keyword→dimension lexicon (fixed +/- stems per dimension), applied uniformly; documented and
reproducible. Ambiguity is high for the register dimensions (§3). **Single-coder, HIGH-RISK**; a defensible
freeze would need ≥2 blind coders with reported agreement. Several dimensions could not be mapped without
essentially inventing a vṛtti→register bridge that the glosses do not support.

## 5. Role sensitivity and composition

Per-varṇa pole/position from the frozen `read_op` rule; order-sensitive position-weighted sum (early
positions up-weighted); L2 normalization; unknown sounds dropped + logged. **Result: the intended
order-sensitivity did not materialize** (§6) — the position weighting is dominated by the per-varṇa vectors.

## 6. Non-degeneracy pre-check results (development-only)

| check | result | verdict |
|---|---|---|
| vectors non-identical (mean pairwise cosine, all forms) | **0.318** | PASS (differentiated) |
| zero-variance dimensions | **none** | PASS |
| all-zero rate | 0.014 | PASS |
| mean vector density | 0.30 | PASS (not dense-collapsed) |
| **order-sensitivity: scrambled-vs-real cosine** | **0.967** | **FAIL — effectively order-invariant (scrambled ≈ real)** |
| deranged-vs-real cosine (another word) | 0.288 | differentiated (trivially — different varṇas) |
| **pseudoword arm** | **1 of 16 built** | **FAIL — pseudowords not cmudict-g2p-able (needs grapheme g2p)** |

**Reading:** non-degeneracy across *real* words passes — but that is trivial (different words have different
varṇas). The two checks that matter **fail**: (a) **scrambled ≈ real (cos 0.967)** — varṇa **order carries
essentially nothing**, reconfirming B1.1's scrambled-tie at the field-vector level; (b) the **pseudoword
arm**, the cleanest isolation, **could not be built** through cmudict.

## 7. Pseudoword set

A 16-form controlled set was specified (matched length, hard/soft & repeated/non-repeated contrasts), but
15/16 are not in cmudict, so g2p→varṇa failed for them. A grapheme-level g2p (varna_lens roman/explicit path)
would be required — a protocol gap, not run here.

## 8/9. Pass / fail criteria applied

**Pass required:** non-trivial variance ✔, **scrambled ≠ real ✗**, random ≠ real ✔ (trivial), no all-zero ✔,
no dense collapse ✔, **order-sensitivity observable ✗**, hashable ✔. **Fail triggers hit:** *scrambled ≈ real
because composition is effectively orderless*; *vṛtti terms cannot be defensibly mapped to the chosen field
dimensions* (register dims 4–5/68).

## 10. Interpretation

Two independent, non-protocol problems surfaced, both convergent with the whole arc:

1. **Mapping not defensible for the field-relevant dimensions.** varṇa = vṛtti (spiritual tendency), not
   register/affect. The dimensions that would distinguish synonyms by *field* (formality/intimacy/distance/
   domestic) are essentially absent from the glosses. Forcing them would be inventing a bridge the ontology
   doesn't contain.
2. **Order carries nothing (scrambled ≈ real, 0.967)** — the same null the arc has hit repeatedly.

The trivially-fixable items (grapheme g2p for pseudowords; cranking the order weight) do **not** cure these —
and cranking order weighting *to pass* would be tuning. Re-scoping to **vṛtti-native** dimensions
(grasping↔release, striving↔rest) would make the mapping tautologically defensible, but (a) breaks the
field-theory premise (father/papa don't differ in grasping/striving) and (b) is not reliably rateable — so it
is not a rescue of *this* hypothesis.

## 11. Decision

```
DECISION: VARNA_FIELD_TABLE_MAPPING_NOT_DEFENSIBLE_STOP_NOW
```

The frozen varṇa glossary does **not** defensibly produce the register/affective **field dimensions** the
field-theory test requires (register dims 4–5/68), and the composition is effectively **order-invariant**
(scrambled ≈ real, 0.967). `PASS` is not earned (two core checks fail). `PROTOCOL_INSUFFICIENT_NEEDS_REVISION`
understates it — the failures are conceptual (vṛtti ≠ register-field; order carries nothing), not fixable
without either tuning or re-scoping away from the field-theory premise. `FAIL_DEGENERATE` is not the precise
label (real-word vectors are differentiated); the precise blocker is **mapping-not-defensible** compounded by
order-invariance.

## 12. Next gate

```
next gate: VARNA_LINE_CLOSURE_MEMO
```

(A vṛtti-native re-scoping could be raised as a *separate* new hypothesis, but it abandons the register-field
premise and its rateability, so it is not a continuation of this test.)

## 13. Final status block

```
document:                    B1.3 varṇa→field TABLE RISK adjudication + non-degeneracy pre-check (development only)
decision:                    VARNA_FIELD_TABLE_MAPPING_NOT_DEFENSIBLE_STOP_NOW
table source:                frozen varṇa glosses; mechanical blind keyword lexicon (single-coder HIGH-RISK)
field dims defensible?:      NO for register/affective dims (formality/intimacy/distance/domestic = 4–5 / 68);
                             only potency/activity grounded (vṛtti ≠ register-field)
non-degeneracy (real words): PASS (trivial — different varṇas → different vectors)
scrambled vs real:           cos 0.967 → order-invariant (FAIL) — reconfirms B1.1 scrambled-tie
deranged vs real:            cos 0.288 (differentiated trivially); pseudoword arm 1/16 built (FAIL: needs grapheme g2p)
ran judges / scoring:        NO
EVIDENCE_FREEZE:             NONE
B1.1 verdict:                UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
B1.2 / B1.3 prior:           UNCHANGED (not rescued)
LLM_PROPENSITY_FIELD_DISCRIMINATION / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                   VARNA_LINE_CLOSURE_MEMO
```

**Structure, not validated meaning.** The development pre-check shows the frozen varṇa glossary cannot
defensibly generate the register/affective field dimensions the field-theory test needs, and its composition
is order-invariant (scrambled ≈ real) — both convergent with every prior null. Nothing was judged or scored,
no prior result changed, Track B remains BLOCKED, and the honest next step is closure.
