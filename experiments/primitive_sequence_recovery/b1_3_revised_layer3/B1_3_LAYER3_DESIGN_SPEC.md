# B1.3 Revised Layer-3 Design Spec

## 1. Scope

Specifies the **revised Layer-3 measurement object** for B1.3. Design spec only — DEVELOPMENT_FREEZE; no
evidence, no scoring, no model calls. Does not modify B1.1/B1.2 artifacts, does not rescue them, and makes no
`LIMITED_GENERATION_UTILITY` / `MAPPING_FIDELITY_SIGNAL` / ontology / Sanskrit / semantic-truth / Track-B
claim. **Structure, not validated meaning.**

## 2. The revised Layer-3 object

```
B1.2 (failed):  word → varṇa → BRIDGE PROSE → external feature vector
B1.3 (revised): word → RAW VARṆA SEQUENCE → fixed varṇa-feature contribution model → external feature vector
```

`V(word)` is now computed **directly from the raw varṇa sequence** by a **fixed contribution model** `M`:

- Decompose the word to its varṇa sequence (real G2P→varṇa, the existing bound pipeline).
- Each varṇa token — with its **pole** (binding/liberating, from the frozen `read_op` rule) and **position**
  (onset/coda/first/doubled) — contributes a fixed vector `M(varṇa, pole, position)` over the external
  feature space.
- Compose the token contributions into one `V(word)` vector by a **fixed, order-sensitive** rule (§4).

`M` is a **fixed table/kernel**, specified once, applied identically to every word — **not** prose, **not**
per-word authored, **not** derived from G. Whether such an `M` can be built **non-circularly** is the pivotal
open question, adjudicated at Gate 5.

## 3. Why bridge prose is retired as the measurement object

B1.2's bridge prose failed twice: (a) it was **style-separable** from dictionary prose (powered R3 ba 0.70),
and (b) blindly projected, it was **generic** — `V_deranged ≈ V_real`, top-1 at chance (0.014). The prose
layer added an interpretive, generic, style-laden step between the varṇa sequence and the features. B1.3
**removes** that step: the varṇa sequence maps to features **directly** through `M`, so any signal (or its
absence) is attributable to the raw sequence, not to gloss wording or style.

## 4. Representation of V and its controls

All variants use the **same** fixed model `M` and the same composition rule; they differ only in the varṇa
sequence fed in:

- **V_real(word)** — the word's real varṇa sequence, in order, poles+positions from `read_op`.
- **V_scrambled(word)** — the **same multiset** of varṇas, **order permuted** (seeded). Because composition is
  **order-sensitive** (§4a), `V_scrambled ≠ V_real` in general — fixing B1.2's order-invariance defect.
- **V_deranged(word)** — **another word's** real varṇa sequence, tested against `G(word)`.
- **V_removed / no-varṇa** — a null predictor (empty/neutral sequence) → baseline/ceiling probe.
- **V_random** — a random varṇa sequence (length-matched) from the varṇa alphabet, excluding the word's own.

**4a. Order-sensitive composition (required).** The composition rule must make order matter — e.g. a
position-weighted or n-gram/sequence-kernel combination of token contributions — so that `V_scrambled` can
diverge from `V_real`. A pure order-free sum is **forbidden** (it reproduces the B1.2 bag defect). Exact form
is fixed at Gate 5.

## 5. External G target space

`G(word)` is derived **externally** (dictionary/WordNet), independent of varṇa, in the **same feature space**
`V` maps into (chosen at Gate 4; WordNet hypernym vectors are the leading candidate — they were adequate on
the G side in B1.2). `G` never sees varṇa; `V` never sees the dictionary or `G`. Independence is the basis of
the test.

## 6. Why this is new design, not a B1.2 continuation

- The **measurement object changed** (raw-sequence contribution model, not bridge prose).
- The **order defect is fixed** (order-sensitive composition).
- **Controls are stratified** on two axes (Gate 3), unlike B1.2.
- It carries its **own** prereg + (future) EVIDENCE_FREEZE; B1.2's failures stand for B1.2's design and are
  **not** rescued.

## 7. Success-label discipline

The **only** positive label B1.3 may ever earn — and **only** after a future explicit EVIDENCE_FREEZE run that
passes all preregistered audits — is **`MAPPING_FIDELITY_SIGNAL`** (with distance-gradient qualifier).
Everything in this workplan is DEVELOPMENT and can earn **no** positive label. `LIMITED_GENERATION_UTILITY`,
ontology, Sanskrit privilege, semantic truth, and Track-B unblock remain forbidden at all times.

## 8. Status

```
document:        B1.3 revised Layer-3 DESIGN SPEC (development; nothing run)
measurement:     word → raw varṇa sequence → fixed model M → external feature vector (order-sensitive)
pivotal risk:    can M be built non-circularly (no G/dictionary/target-word lookup)? — Gate 5
B1.1 verdict:    UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
Track B:         BLOCKED
only positive:   MAPPING_FIDELITY_SIGNAL (after future EVIDENCE_FREEZE only)
EVIDENCE_FREEZE: NONE
```

**Structure, not validated meaning.**
