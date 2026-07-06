# B1.2 Propensity-Mismatch Review

## 1. Scope and non-rescue rule

Reviews whether B1.2 failed partly because it tested varṇa output as **dictionary-meaning prediction**, while
the intended theory treats varṇa mappings as **propensities/modulators**, not meanings. Mismatch review only:
no implementation, no models, no B1.2 rerun, no scoring. It does **not** overturn the B1.2 failures, claim
B1.2 succeeded, authorize a new run, or change any B1.1/B1.2/B1.3 verdict; and makes no
`LIMITED_GENERATION_UTILITY` / `MAPPING_FIDELITY_SIGNAL` / ontology / Sanskrit / semantic-truth / Track-B
claim. **Structure, not validated meaning.**

## 2. The object B1.2 actually tested

- `V(word)` = varṇa-derived prediction; `G(word)` = dictionary-derived differential answer key.
- Test = does `V(word)` **align with** `G(word)` better than controls?
- This implicitly treats the varṇa output as if it **should match dictionary meaning** — a
  meaning-**prediction** framing.

## 3. The corrected theoretical object (propensity)

- **Layer 1** = varṇa/sound skeleton. **Layer 2** = dictionary meaning anchor. **Layer 3** =
  **propensity/modulation** applied to that anchor.
- On this reading, varṇa mappings are **not literal dictionary meanings**; they are tendencies/textures that
  **modulate** the fixed dictionary anchor.
- **Father example:** dictionary meaning = male parent, ancestor, lineage source. Varṇa *propensity* might be
  pressure / boundary / force / transmission / guidance / protection — **not** the definition of father, but a
  proposed *texture* of the father role.

## 4. Why this matters (the type-mismatch point)

Comparing a **propensity profile** directly to a **dictionary meaning** is a **type mismatch** — like
comparing *weather* to an *address*: related, not the same object. So B1.2's direct `V↔G` alignment was, on
the intended theory, **structurally misaligned**: it demanded the modulator reproduce the anchor. **This
critique of B1.2's specific direct-match design is valid.**

## 5. What B1.2 still validly showed (unchanged)

- **Prose path:** V-prose and G-prose were **style-separable** (powered R3 ba 0.70, CI [0.5929, 0.7929]).
- **Feature-space path:** the blind bridge-gloss V projection into external semantic features was
  **generic/control-equivalent** (V_real→G_target 0.5194 ≈ off-target 0.5147; top-1 0.014 = chance;
  V_deranged ≈ V_real; V_random ≥ V_real).
- These remain **valid for the B1.2 design**. The mismatch review does **not** erase them.

## 6. What B1.2 did not directly test

- It did not ask whether a varṇa **propensity profile coherently modulates a fixed dictionary anchor** in a
  discriminative, judge-blind task of the form: *father + real-father-varṇa-propensity* vs *father +
  deranged/scrambled/random/sound-neighbor propensity*.
- It did not define or test a `PROPENSITY_MODULATION_SIGNAL`.

## 7. Candidate future-only label

**`PROPENSITY_MODULATION_SIGNAL`** — *given a fixed dictionary anchor, the real varṇa-derived propensity
profile modulates that anchor more coherently, specifically, and discriminatively than scrambled, deranged,
random, and sound-neighbor propensity profiles.* It is **not earned**, would require a **new preregistered
design**, is **not** `MAPPING_FIDELITY_SIGNAL`, and is **not** `LIMITED_GENERATION_UTILITY`.

## 8. Controls required under a propensity framing

Per target anchor, compare: target + **real** varṇa propensity; + **scrambled**; + **deranged** (another
word's); + **random**; + **varṇa-near / semantic-far** (sound-neighbor); + **semantic-near** (if relevant); +
**no-varṇa / neutral** baseline. *(father: father + {father / scrambled-father / another-word / feather-farther-foster / neutral} propensity.)*

## 9. Success criteria (future design)

Real propensity preferred over scrambled/deranged/random/no-varṇa; **not** merely more poetic; **specific** to
the anchor; **varṇa-near/semantic-far must not win on sound**; deranged and random must **drop**; judges blind
to arm labels; **style/register matched** across arms. Only allowed positive: `PROPENSITY_MODULATION_SIGNAL`.

## 10. Kill criteria (future design)

STOP if: deranged ≈ real; scrambled ≈ real; random/no-varṇa ≈ real; varṇa-near unrelated word wins; the real
profile is generic enough to fit many anchors; the result depends on poetic style; judges can identify
arm/source by style; or propensity language is hand-polished per word.

## 11. Does this reopen B1.2?

**No — not as B1.2 evidence.** It explains a possible theory/design mismatch and could support *scoping* a new
B1.4 / B1.3-v2 propensity design **if the team chooses**. It **cannot** retroactively make B1.2 positive.

## 12. Decision — and the hard honest caveat

```
DECISION: PROPENSITY_MISMATCH_PARTIAL_BUT_CURRENT_NULL_STANDS
```

The type-mismatch point is **partially valid for B1.2's direct-match framing** — but it does **not** open a
promising untested path, for three convergent reasons:

- **The propensity question is largely what B1.1 already tested.** B1.1's A arm *was* "word + its own varṇa
  bridge (a propensity/texture) used to condition generation," compared against **deranged / scrambled /
  random** varṇa conditioning. That **is** "does the real propensity modulate more coherently than a wrong
  one" — and it returned `RANDOM_OR_SCRAMBLED_MATCHES` (A did not beat R_deranged/R_domain/R_same).
- **`V_deranged ≈ V_real` is propensity-level, inventory-independent evidence.** Another word's varṇa
  *profile* fit the target's dictionary content as well as the target's own — which is exactly the propensity
  claim, and it is null.
- **ρ≈0 (B1.3) undercuts propensity too.** If propensities were word-specific, varṇa-near words would carry
  related propensities → some semantic lift; the nearest-varṇa semantic lift is 0.010 (≈0).

So "propensity" is a **vaguer** object than "meaning" — easier to produce false positives, harder to falsify —
and the specific, falsifiable version of it has already been substantially tested and found null. The mismatch
is a fair critique of B1.2's *framing*, not a resurrection of the hypothesis. `…_CONFIRMED_NEW_DESIGN_REQUIRED`
overstates the promise; `…_NOT_MATERIAL_CLOSE_LINE` understates the valid conceptual point. **Partial, current
null stands.**

## 13. Recommended next gate

```
next gate: VARNA_LINE_CLOSURE_MEMO
```

A propensity-modulation `B1.4` **could** be scoped if the team chooses, but it is **not recommended**: it
would relitigate a close cousin of B1.1's already-null test, must overcome `V_deranged ≈ V_real` and ρ≈0, and
could only ever earn the narrow `PROPENSITY_MODULATION_SIGNAL`. The honest default is closure. (The parallel
B1.3 thread remains at `B1_3_VARNA_TO_FEATURE_RULE_ADJUDICATION`; both live threads point toward the same
consolidation.)

## 14. Final status block

```
document:                   B1.2 PROPENSITY-MISMATCH review (review only; nothing run)
decision:                   PROPENSITY_MISMATCH_PARTIAL_BUT_CURRENT_NULL_STANDS
type-mismatch critique:     valid for B1.2's direct-match framing; does NOT reopen B1.2
propensity question:        substantially = B1.1's question → already null; undercut by V_deranged≈V_real, ρ≈0
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
B1.2 failures:              REMAIN VALID (prose style-tell 0.70; feature-space triviality)
B1.3 Gate-5:                REMAINS VALID for the raw-varṇa distance design (now HIGH_RISK pending adjudication)
LIMITED_GENERATION_UTILITY: NOT earned
MAPPING_FIDELITY_SIGNAL:    NOT earned
PROPENSITY_MODULATION_SIGNAL: NOT earned
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
EVIDENCE_FREEZE:            NONE
next gate:                  VARNA_LINE_CLOSURE_MEMO
```

**Structure, not validated meaning.** The propensity reframing is a fair critique of B1.2's direct-match
design but points to a question B1.1 already answered null; no prior verdict changes, nothing is rescued or
claimed as evidence, and the honest default is closure.
