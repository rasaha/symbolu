# B1.4 Vṛtti-Native Propensity Dimension Spec

## 1. Scope and non-rescue rule

Specifies whether a **vṛtti-native** propensity test is possible — testing the frozen varṇa glossary on **its
own native terms** (mental/spiritual tendencies), not dictionary meaning and not social register.
Dimension/spec memo only: no implementation, no models, no judges, no scoring, **no EVIDENCE_FREEZE**. It does
**not** reopen B1.1/B1.2/B1.3 as positive evidence, authorize scoring, or claim validation. No
`VRITTI_PROPENSITY_SIGNAL` / `PROPENSITY_MODULATION_SIGNAL` / `LLM_PROPENSITY_FIELD_DISCRIMINATION` /
`LIMITED_GENERATION_UTILITY` / `MAPPING_FIDELITY_SIGNAL` / ontology / Sanskrit / semantic-truth / Track-B claim.
**Structure, not validated meaning.**

## 2. Why register-field closed

The frozen varṇa glossary barely maps to formality/intimacy/domesticity/warmth (4–5 gloss hits / 68). Those
are **social-register / babbling / convention** properties (father/papa, mother/mama), largely explained by
frequency, acquisition, and etymology — **not** the native target of the glossary. That version is closed.

## 3. Native vṛtti hypothesis

Varṇa propensities are **vṛtti-like mental/spiritual tendencies** — not denotation, not register. Candidate
dimensions (all present in the frozen glosses): **grasping↔release, attachment↔non-attachment,
agitation↔steadiness, striving↔surrender, ego-inflation↔humility, possession↔offering,
judgment/pride↔clarity/equanimity, binding↔liberation, reactivity↔restraint, compulsion↔freedom.** These
are the dimensions the glossary *actually* encodes (empirically the best-grounded axes: potency/activity/
dependency/hardness were the register-proxy shadows of these).

## 4. Dimension source

Derived **only** from the frozen varṇa glossary (binding/liberating pole text). **No** dictionary meaning, **no**
WordNet, **no** post-hoc word examples, **no** tuning to judge outputs. Dimension definitions must be **frozen
before any test**. (This makes the *predictor* side clean — but note §6: the *ground-truth* side is the problem,
not the predictor side.)

## 5. Candidate test objects

- **A. Isolated English words** — weak: assigning a word an external vṛtti value requires inferring from its
  *meaning* (father→authority→"ego"?), which is semantic leakage, not varṇa. No clean vṛtti ground truth.
- **B. Sanskrit words** — closer to the tradition, but semantics + doctrinal interpretation leak, and it
  invites Sanskrit-privilege framing. Ground truth still doctrinal.
- **C. Phrases / Gita ślokas** — most natural for vṛtti modulation, but **maximal** subjectivity and doctrine
  leakage; the interpreter's reading *is* the ground truth (circular). Least testable (flagged repeatedly).
- **D. Pseudowords** — clean of meaning, but a naive rater's vṛtti impression of a pseudoword is a **sound
  impression** = the **acoustic (annamaya) level** the hypothesis explicitly disowned; it would test
  sound-symbolism, not vṛtti-ontology.

**No candidate object supplies a word-level vṛtti ground truth that is both non-circular and actually about
vṛtti** (rather than meaning-inference or acoustic impression). This is the crux (§6).

## 6. External ground-truth problem (the crux)

*What is the correct vṛtti profile of "father," "duty," "surrender," or a śloka?* For this test to be
non-circular, that answer must come from a source **other than Symbol-U's own varṇa glossary**, and be
**inter-subjectively convergent**. Assessment of candidate sources:

- **Blind naive LLM/human ratings** — "how much *grasping* does the word *father* carry?" is not a linguistic
  property people converge on; answers are either meaning-inferred (leakage) or idiosyncratic (low agreement).
  Not a clean ground truth.
- **Cross-tradition trained raters** — they learned the doctrine → **circular**.
- **Commentarial categories** — usable only if they **predate and are independent of** Symbol-U's mapping; if
  chosen to match the varṇa glossary → **circular**.
- **Affect/personality norms** — measure *valence/arousal/dominance*, an **affective** space, **not vṛtti**;
  wrong target.

**Strong (honest) prior:** the only reliable assigner of word-level vṛtti profiles appears to be **Symbol-U's
own mapping — which is the thing under test** → the test risks being **circular by construction**. Whether
*any* independent, convergent, genuinely-vṛtti ground truth exists is the unresolved question that gates
everything (§12).

## 7. Order-sensitivity problem

**scrambled ≈ real (cosine 0.967)** is a dimension-**independent** blocker that carries into the vṛtti test.
Any vṛtti test must first show **real order/role composition differs from scrambled without post-hoc tuning**.
The arc's repeated scrambled-ties (B1.1; §B1.3 pre-check) make this a high bar. **If order stays inoperative,
`STOP_NOW`** regardless of the ground-truth outcome.

## 8. Possible fair test designs (each with its fate)

- **Option 1 — pseudoword vṛtti ratings:** Symbol-U predicts vṛtti profile from form; raters rate pseudowords;
  beat scrambled/random/generic sound-symbolism. *Fate:* rater impressions of pseudowords are **acoustic**, so
  a hit = sound-symbolism, not vṛtti-ontology.
- **Option 2 — śloka modulation:** fixed commentarial anchor; real vs scrambled/deranged/random vṛtti profile;
  judges rate vṛtti modulation. *Fate:* the anchor's vṛtti field is the commentator's **interpretation** →
  doctrine-leakage/circularity; style controls needed; least testable.
- **Option 3 — commentary classification:** predict externally-defined vṛtti themes. *Fate:* valid **only** if
  the theme set is independent of Symbol-U; high circularity risk otherwise.

## 9. Controls required

real · scrambled · deranged · random · no-varṇa neutral · generic sound-symbolism baseline; style/length/
fluency matching if prose is used; blinded judges if judges are used.

## 10. Success criteria (future test)

real vṛtti profile beats **scrambled, deranged, random, and no-varṇa**; survives **style** controls; is **not**
generic sound-symbolism; judge agreement above threshold; (ślokas) real improves vṛtti modulation of a fixed
anchor above controls. **Only allowed future label: `VRITTI_PROPENSITY_SIGNAL`** (after EVIDENCE_FREEZE).

## 11. Kill criteria

STOP if: **no external/non-circular ground truth exists**; scrambled ≈ real; deranged = real; random = real;
judges prefer poetic prose; **categories are drawn from Symbol-U and then used to validate Symbol-U**; or the
effect appears only for post-hoc hand-selected examples.

## 12. Decision

```
DECISION: VRITTI_PROPENSITY_GROUND_TRUTH_UNRESOLVED_NEEDS_ADJUDICATION
```

The **dimensions are specifiable** from the frozen glossary (that side is clean). But the **ground truth** —
an independent, convergent, genuinely-vṛtti target to predict — is **unresolved and looks likely absent**: every
candidate source is either circular (Symbol-U / trained raters / matched commentary), off-target (affect norms,
acoustic pseudoword impressions), or meaning-leaking (English/Sanskrit word inference). `…SPECIFIABLE_NEEDS_TEST_
DESIGN` **overstates** (you cannot design a valid test without a non-circular ground truth). `…NOT_EMPIRICALLY_
TESTABLE_STOP_NOW` may be the true endpoint, but declaring it now would be an **over-broad universal** on the
same pattern I've had to walk back before — a dedicated adjudication should first check specific candidate
ground-truth sources exhaustively. Hence **ground-truth unresolved, needs adjudication** — with an **honest
heavy lean toward closure**, since the leading conclusion is that no non-circular vṛtti ground truth exists and
order remains inoperative.

## 13. Next gate

```
next gate: B1_4_VRITTI_GROUND_TRUTH_ADJUDICATION
```

(Exhaustively examine whether ANY independent, convergent, genuinely-vṛtti word-level ground truth exists —
predating and independent of Symbol-U. If none → `VARNA_LINE_CLOSURE_MEMO`. If one plausibly exists **and**
order can be made non-circularly operative → `B1_4_VRITTI_TEST_DESIGN_SPEC`.)

## 14. Final status block

```
document:                    B1.4 vṛtti-native propensity DIMENSION spec (dimension spec only; nothing run)
decision:                    VRITTI_PROPENSITY_GROUND_TRUTH_UNRESOLVED_NEEDS_ADJUDICATION
vṛtti dimensions:            specifiable from frozen glossary (grasping↔release, striving↔surrender, ego↔humility, binding↔liberation, …)
ground truth:                UNRESOLVED — likely absent/circular (crux); no non-circular, convergent, genuinely-vṛtti word target found
order sensitivity:           scrambled ≈ real (0.967) — generalizes; must be non-circularly operative or STOP_NOW
ran models / judges / scoring: NO
EVIDENCE_FREEZE:             NONE
social/register field:       CLOSED
B1.1 verdict:                UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
B1.2 / B1.3 prior:           UNCHANGED (not rescued)
VRITTI_PROPENSITY_SIGNAL / PROPENSITY_MODULATION_SIGNAL / LLM_PROPENSITY_FIELD_DISCRIMINATION: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                   B1_4_VRITTI_GROUND_TRUTH_ADJUDICATION (else VARNA_LINE_CLOSURE_MEMO)
```

**Structure, not validated meaning.** The vṛtti dimensions are specifiable on the glossary's own terms, but
the test rests on an external vṛtti ground truth that appears to be absent or circular, and on an
order-sensitivity that has never been operative; both must be adjudicated before any test design, with the
honest leading expectation being closure. Nothing was run or scored, no prior result changed, Track B remains
BLOCKED.
