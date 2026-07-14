# B1.12 — Development Reset & Observable Redefinition

**`DEVELOPMENT_RESET` · `EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE` ·
`NO_CONFIRMATORY_EVIDENCE_FREEZE_HAS_OCCURRED` · `G1_REOPENED_FOR_REDESIGN`.**

Controlling reset artifact. Reopens B1.12 for developmental redesign, retires the prior G1 instruments from
controlling status **without deleting or rewriting them**, and — before any new instrument is designed —
resolves whether *order* should be the tested variable at all. Remains **B1.12** (not B1.13, not B2). Docs-only;
no implementation, no run, no freeze. B1.10, B1.11, and `VARNA_AFFLICTION_RESOLUTION_TEST_PREREG_V1.md` unchanged.

**Headline decision: `STOP_B1_12_AS_THEORETICALLY_MISFRAMED`** — the ordered-composition (order-advantage)
framing is misframed relative to the frozen theory that supplies B1.12's own component content, and B1.12 has
**no independent judge-based observable** left once order is removed (its residual semantic question is the
separate Varṇa–Affliction Resolution Test). Full reasoning in §7–§9.

---

## 1. Reset status
B1.12 is reopened as an **exploratory developmental** experiment. No prior G1 instrument is controlling for the
next design. This artifact supersedes the *controlling status* (not the content) of the prior G1 designs and
their reports.

## 2. Evidence-freeze status
**No confirmatory evidence freeze has ever occurred in B1.12.** No judge/evaluator was ever run for evidence; no
evidentiary dataset exists; every prior result is a description of an instrument or a deterministic audit. B1.12
therefore remains fully open to versioned redesign.

## 3. Immutable development history (preserved; none deleted, edited, or relabeled)

| version / artifact | commit | design objective | result | why blocked / failed | remains controlling? |
|---|---|---|---|---|---|
| Base prereg (ordered varṇa composition) | `2c613f4` | frame H2: ordered composition adds word-specific info beyond bag | design | — | history only |
| V1.1 G0 constants | `6f197fd` | freeze structural G0 thresholds | frozen | — | G0 constants preserved |
| V1.2 order-distinctness correction | `7935f48` | fix `d_ord\|inv` formula | corrected | — | formula preserved |
| Candidate pool v1 | `d50fbb9` | freeze 35 attested words | frozen | — | pool preserved |
| G0 audit | `1713311` | structural distinctness gate | **G0_PASS** (6 words) | — | **structural finding preserved; does NOT force the next observable (§6)** |
| G1 opaque-ID design v1 | `9e8da86` | leakage-safe ordered opaque task | `G1_PASS_WITH_LIMITED_CLAIM` (later withdrawn) | — | non-controlling |
| G1 opaque reassessment | `bb2051e` | audit identifiability | **`G1_BLOCKED_NO_IDENTIFIABLE_TASK`** | opaque IDs give no key → order not recoverable → underdetermined (chance) | non-controlling |
| G1 semantic-component v1 | `d48ae9f` | referent-matchable ordered descriptors | **`G1_BLOCKED_DESCRIPTOR_QUALITY`** | affliction glosses, length/tier leakage | non-controlling |
| G1 semantic-component v1.2 (normalized) | `0929c51` | fix length/narrative via normalization | **`G1_BLOCKED_DESCRIPTOR_QUALITY`** | domain mismatch irreducible; leakage persists; inventory identifies word | non-controlling |
| Evidence-scope + descriptor-example reviews | `6b8e561` | audit over-claim | narrowed conclusion | (review) | non-controlling; corrections stand |

## 4. What each prior G1 failure established
- **Opaque (`bb2051e`):** a leakage-safe opaque representation preserves order but is **underdetermined** — with
  no key, distinct-token permutations are exchangeable (chance); above-chance would imply leakage/memorization.
- **Semantic v1 / v1.2 (`d48ae9f`, `0929c51`):** with the frozen binding descriptors the evaluator task becomes
  *identifiable in principle*, but the descriptors are affliction/tendency glosses (not referent descriptors),
  carry length/first-position/inventory leakage, and are generic/repetitive; blocked **before any judge use**.
- **Reviews (`6b8e561`):** instrument unsuitability was supported; theory-level claims about the Symbol-U
  mapping were **not directly tested** and were withdrawn.

## 5. What those failures did **not** establish
They did **not** establish that the Symbol-U mappings are defective or "wrong-domain"; that Symbol-U cannot
support any experiment; that ordered composition carries no information (never probed); or anything about B1.10's
mechanism. **These failures are not evidence for or against the core theory.**

## 6. G0 status under the reset
`G0_PASS` (structural order-distinctness of the six) is **preserved as a structural fact**. But it measured a
property — sequence structure — whose *semantic* relevance is exactly what §7 puts in question. Per the reset,
**G0 structural findings do not force the next semantic observable.**

## 7. Current theory statement — and a frozen contradiction that must be surfaced

Two **frozen** theoretical positions in this repository disagree about whether order carries meaning:

- **T-AFFLICTION** — `VARNA_AFFLICTION_RESOLUTION_TEST_PREREG_V1.md`, which supplies B1.12's *component content*
  (the binding-vṛtti glosses): **R5 (AND-composition)** `A(w) = a₁ ∧ a₂ ∧ … ∧ aₙ` (simultaneous conjunction);
  **R6 (no progression)** "no claim that one varṇa transforms/balances/removes another, or that **order is
  causal**." Conjunction is commutative, so **meaning is a pure function of the multiset** — two anagrams are
  semantically **identical**; **order carries zero information.** (Multiplicity *does* matter — R4 scores each
  occurrence — but multiplicity is a multiset property, not order.)
- **T-OPERATOR** — `SYMBOL_U_THEORY_V1_FREEZE.md`: `ρ(σ₁…σₙ) = M_{σₙ}∘⋯∘M_{σ₁}(s₀)`, "**order-sensitivity
  (non-commutativity) is the distinctive structural commitment**"; falsifier: "order-effects ≈ 0 →
  non-commutativity [falsified]." Here order **does** carry information — but the observable is a **latent
  reading state** under per-unit operators, **not** judge-based referent/affliction identification, and it does
  **not** use the affliction glosses.

**B1.12 conflated the two:** it used **T-AFFLICTION's content** (affliction glosses) with **T-OPERATOR's
hypothesis** (order matters). That is incoherent — T-AFFLICTION's content comes bound to T-AFFLICTION's R6, which
disclaims order.

## 8. Consistency audit against AND-composition / no-progression

1. **If order has no semantic mechanics, what would an "order advantage" mean?** Under T-AFFLICTION it would
   mean the *evaluator* is using order as a cue (a judge/linguistic artifact or leakage), **not** that the
   composition is order-sensitive — indeed a positive order effect would **contradict** R6, not support the
   mappings.
2. **Is B1.12 H2 still theoretically justified?** **No** under T-AFFLICTION (the mappings' own theory). It is
   justified only under T-OPERATOR — but that requires operator/latent-state content and instrument, not
   affliction glosses judged for referents.
3. **Does true-vs-scrambled order manipulate a property the theory claims matters?** **No** (T-AFFLICTION R6:
   order not causal). It manipulates a property the affliction theory holds **inert**.
4. **Would a null order result confirm no-progression rather than falsify the mappings?** **Yes — decisively.**
   A null is T-AFFLICTION's own prediction, so it is **uninformative** about the mappings. This is the core
   misframing: the experiment cannot fail informatively.
5. **Should B1.12 be redefined around membership / repetition / multiplicity / adjacency / acoustic grouping?**
   - *membership* and *multiplicity/repetition* are theory-valid (R5, R4) — but they are **already** the
     Varṇa–Affliction Resolution Test's variables (conjunctive coverage + occurrence-level scoring);
   - *adjacency* and *acoustic (akṣara) grouping* are positional/order-like → **inert** under R6.
   No theory-endorsed structural variable survives that is **distinct** from the affliction program.

## 9. Selected primary observable & decision

**Recommendation: none of O1–O5 yields a B1.12-distinct, theory-justified, judge-based test.**

| observable | verdict | reason |
|---|---|---|
| **O1** ordinary referent identification | reject | mappings are affliction/tendency, not referent descriptors (reviews `6b8e561`); wrong target |
| **O2** affliction-resolution fit | reject as B1.12 | this **is** the Varṇa–Affliction Resolution Test → improper merge / no independent role |
| **O3** ordered affliction-composition effect | reject | still an **order** test → inert under R6; a null confirms the theory (see §8.4) |
| **O4** inventory-only affliction fit | reject as B1.12 | multiset conjunction = the Varṇa–Affliction Resolution Test → no independent role |
| **O5** structural sequence recoverability | reject | parser/string-recognition; non-semantic; says nothing about the theory |

**Order is not theoretically justified as B1.12's tested variable** (under the affliction mappings' own R5/R6),
and every theory-valid alternative collapses into the separate affliction program. **`STOP_B1_12_AS_THEORETICALLY_
MISFRAMED`.**

## 10. Does B1.12 remain scientifically distinct? — No independent role
Once the (theoretically inert) order variable is removed, B1.12's residual semantic observable is **exactly** the
Varṇa–Affliction Resolution Test (unordered, AND-composed affliction fit, occurrence-level). Per the independence
rule, **B1.12 has no independent judge-based role.** The two studies are **not** merged here: no scoring, words,
or conclusions are imported; the affliction test remains separate and unchanged. The only way to legitimately
pursue an *order* question is under **T-OPERATOR** as a non-commutativity test on a **latent reading state** —
a different instrument and content, requiring its **own** preregistration; that is **not** a B1.12 G1 evaluator
redesign and is **not** recommended here.

## 11. Exact next design step
**No new G1 instrument is designed.** The next step is a **decision by the researcher**, not an implementation:
either (a) accept `STOP` and let the semantic question proceed within the unchanged Varṇa–Affliction Resolution
Test; or (b) if an order/non-commutativity effect is genuinely wanted, open a **separate** T-OPERATOR
latent-state preregistration (distinct experiment, distinct instrument, distinct number) — **not** under B1.12
and **not** using judge-based affliction-referent matching. Until (a) or (b) is chosen, **do not build another
order-sensitive B1.12 instrument.**

## 12. Prohibited carryovers from the failed instruments
Do not carry into any future work: the opaque-ID order task (underdetermined); the binding-affliction descriptors
as *referent* labels (domain-mismatched, leaky); the assumption that ordinary-referent identification is the
target; the assumption that order is a theory-endorsed semantic variable; the selected-six as an order-test set;
or any framing in which a **null order result** is treated as informative about the mappings. Do not import the
Varṇa–Affliction Resolution Test's words/scoring into B1.12 or vice-versa.

## 13. Readiness status
**`STOP_B1_12_AS_THEORETICALLY_MISFRAMED`** (with the finding that B1.12 has **no independent role**; the
residual observable belongs to the separate, unchanged Varṇa–Affliction Resolution Test). Not
`READY_FOR_NEW_G1_PREREGISTRATION` (an order-sensitive redesign would repeat the misframing);
not `B1_12_SCOPE_MERGED` (no silent merge is performed — the studies stay separate);
`B1_12_PAUSED_PENDING_VARNA_AFFLICTION_RESULTS` is the acceptable softer alternative if the researcher prefers to
keep B1.12 nominally open rather than stopped.

## Guardrails
Docs-only reset; new artifact only. No descriptors authored; selected six, G0, pool, parser, lexicon, scoring
unchanged; no judges, usability probe, contexts, packets, or confirmatory freeze; the Varṇa–Affliction Resolution
Test and B1.10/B1.11 untouched. Structure, not validated meaning. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`;
B1.4b′ `NULL_RETURN_BOTTOM`.
