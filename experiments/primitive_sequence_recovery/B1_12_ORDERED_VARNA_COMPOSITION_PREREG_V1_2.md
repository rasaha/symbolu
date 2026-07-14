# B1.12 — Ordered Varṇa Composition — Order-Distinctness Formula Correction (Preregistration Revision V1.2)

**Docs-only specification revision.** Narrowly scoped correction of **one** definition — the
inventory-controlled order-distinctness measure — in `B1_12_ORDERED_VARNA_COMPOSITION_PREREG_V1_1.md`. It
assembles **no** candidate pool, runs the parser on **no** candidate word, computes **no** candidate metric, and
runs **no** G0. All verification uses opaque synthetic symbols only. It does **not** edit V1.1, the original
B1.12 prereg, B1.10, or B1.11 in place.

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. Structure, not validated meaning. No
`GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no ontology / semantic-truth / Sanskrit-privilege / generation-utility
/ individual-varṇa claim. B1.4b′ remains `NULL_RETURN_BOTTOM`; B1.10 remains
`G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`; B1.11 unchanged.

**Readiness: `READY_FOR_CANDIDATE_POOL_FREEZE_AND_G0_RUN`** (unchanged from V1.1; the correction does not alter
selection semantics — see §6).

---

## 0. Incorporation by reference & scope of change

- **Base revisions (incorporated unchanged, by reference):** `B1_12_ORDERED_VARNA_COMPOSITION_PREREG.md`
  (commit `2c613f4`) and `B1_12_ORDERED_VARNA_COMPOSITION_PREREG_V1_1.md` (commit `6f197fd`). Every frozen
  constant and rule in V1.1 is **preserved verbatim** except the single item corrected here.
- **Changed (this revision only):** the definition **labelled** "inventory-controlled order-distinctness" in
  V1.1 §7 (the `o(x) = d_edit(x, sort(x))`, `τ_order = 0.34` item). This revision (a) supplies the correct
  **general pairwise** formula, (b) shows V1.1's per-word constraint is that formula's **self-case** and
  **preserves it unchanged** under a corrected name, and (c) exposes the pairwise form as a **reported G0
  diagnostic**. **No other constant changes:** `k = 6`, opaque-ID rule, length band `[2,6]`, edit-distance
  floor `τ_edit = 0.34`, endpoint cap, n-gram caps, within-set length span, repetition-profile role, pool-source
  and construction rules, curator/auditor separation, and the selection & failure rules are all **unchanged**.
- **Authoring order (auditable):** written **after** V1.1 (commit `6f197fd`) and **before** any B1.12 candidate
  word was assembled, parsed, or measured. **No computed B1.12 candidate statistic exists or was consulted.**
  The correction and its threshold handling use only opaque synthetic sequences (§3) and design constraints.

## 1. Defect found in V1.1 (what was wrong, and what was not)

V1.1 §7 labelled its order term **"inventory-controlled order-distinctness"** and defined it as the **per-word**
self-sort distance `o(x) = d_edit(x, sort(x))`, thresholded at `τ_order = 0.34`.

- **What is defective:** the label denotes a *pairwise* measure of order-specific distinctness **between two
  candidate words** after removing the difference their **inventories** already explain. `o(x)` is **not**
  pairwise and **not symmetric across a pair**: it is a per-*sequence* deviation-from-canonical-sort. On the
  five required synthetic pairs it cannot even be read as a pair measure — e.g. `o("ABC") = 0` while the pair
  `ABC` vs `CBA` is *maximally* order-distinct (§3). So as the *pairwise inventory-controlled* quantity the term
  names, V1.1 was **defective / mis-specified**.
- **What is NOT wrong:** `o(x)` is a mathematically valid **per-word self-order-informativeness** measure, and
  it equals the corrected general formula applied to `(x, sort(x))` — the identity `d_ord|inv(x, sort(x)) =
  o(x)` holds for every tested sequence (§3). Because `sort(x)` is exactly the Arm-D (unordered canonical)
  representation of `x`, `o(x)` is precisely the **Arm-A-vs-Arm-D** distance for word `x` — the guarantee that
  `Δ_inventory = Acc(A) − Acc(D)` is not structurally zero for that word. This per-word constraint is correct
  and is **preserved unchanged** (§5).

The correction therefore **adds the missing pairwise definition and fixes the label**; it does **not** discard
V1.1's per-word constraint.

## 2. Corrected formula (pairwise, principled)

For opaque-ID sequences `x, y` (repeats preserved), with `Lev` = unit-cost Levenshtein edit distance and
`sort(·)` = ascending-opaque-ID canonical form (= the Arm-D representation):

```
d_ordered(x,y)      = Lev(x, y) / max(|x|, |y|)                        # order-sensitive total difference
d_inv_forced(x,y)   = Lev(sort(x), sort(y)) / max(|x|, |y|)            # difference forced by inventory alone
d_ord|inv(x,y)      = max(0,  d_ordered(x,y) − d_inv_forced(x,y) )     # order difference BEYOND inventory
                    = max(0,  Lev(x,y) − Lev(sort(x),sort(y)) ) / max(|x|,|y|)
```

- **Range:** `[0, 1]` (since `0 ≤ Lev(sort(x),sort(y)) ≤ Lev(x,y) ≤ max(|x|,|y|)` in the non-clamped regime, and
  the `max(0, ·)` clamps the rare case where sorting increases distance).
- **Strictness direction:** **higher = more order-specific distinctness** (more of the sequences' difference is
  due to *ordering* rather than *inventory*).
- **Why this over the candidate `max(0, d_ordered − (1 − J_multiset))`:** that alternative subtracts a
  **Jaccard** inventory distance from an **edit-normalized** order distance — two different scales — producing a
  **false positive** on synthetic case 3 (reports `0.167` order signal where there is none, §3). The adopted
  formula subtracts **like-for-like edits**: the "difference already explained by inventory" is exactly the edit
  distance between the two **canonical-sorted (inventory) forms**, i.e. `Lev(sort(x), sort(y))`. This is
  dimensionally consistent, ties the control directly to **Arm D**, and gives the correct `0` on case 3.

## 3. Outcome-blind synthetic verification (opaque symbols; deterministic)

Produced by `b1_12_order_distinctness_synthetic_check.py` (committed alongside; fully enumerated, no randomness,
no candidate words). `proposed` = the candidate `max(0, d_ord − d_inv_jaccard)`; `excess` = the adopted
`d_ord|inv`; `o(x)`/`o(y)` = the V1.1 per-word self-sort metric of each sequence.

**Required cases:**

| case | x | y | d_ord | d_inv | proposed | **d_ord\|inv (excess)** | o(x) | o(y) |
|---|---|---|---|---|---|---|---|---|
| 1 same-inventory / different order | ABC | CBA | 0.667 | 0.0 | 0.667 | **0.667** | 0.0 | 0.667 |
| 2 different inventory / same pattern | ABC | DEF | 1.0 | 1.0 | 0.0 | **0.0** | 0.0 | 0.0 |
| 3 partial shared inventory + order | ABC | ACD | 0.667 | 0.5 | 0.167 | **0.0** | 0.0 | 0.0 |
| 4 repeated inventory / different order | AABC | ABAC | 0.5 | 0.0 | 0.5 | **0.5** | 0.0 | 0.5 |
| 5 identical | ABC | ABC | 0.0 | 0.0 | 0.0 | **0.0** | 0.0 | 0.0 |

`d_ord|inv` satisfies **every** required property: `0` for identical (5); **high** for same-inventory /
different-order (1: 0.667, 4: 0.5, incl. repeats); **`0`** for entirely different inventories (2); and — unlike
`proposed` — **`0`** for case 3, where the shared elements `{A,C}` keep their relative order so no order-specific
signal exists. The `o(x)`/`o(y)` columns show the V1.1 metric is per-sequence and asymmetric (it cannot rate a
pair): `o("ABC")=0` throughout even where the pair is maximally order-distinct.

**Identity (unifies V1.1 with the correction):** `d_ord|inv(x, sort(x)) == o(x)` for **all** tested sequences
(script "IDENTITY CHECK" = holds). So V1.1's per-word constraint is exactly the corrected formula's self-case.

**Order-magnitude calibration — single adjacent transposition vs full reversal (same inventory), lengths 2–6:**

| length | one adjacent swap `d_ord\|inv` | full reversal `d_ord\|inv` | separable? |
|---|---|---|---|
| 2 | 1.000 | 1.000 | no (only one non-identity permutation) |
| 3 | 0.667 | 0.667 | **no** (swap ≡ reversal at len 3) |
| 4 | 0.500 | 1.000 | yes |
| 5 | 0.400 | 0.800 | yes |
| 6 | 0.333 | 1.000 | yes |

A single adjacent transposition yields `d_ord|inv ∈ {0.333 … 0.667}` decreasing with length; a full reversal
yields up to `1.0`. **A trivial one-swap is distinguishable from substantial reordering only for length ≥ 4**;
at length ≤ 3 the metric cannot separate them (too few positions). This is a design fact recorded for
interpretation, not tuned to any candidate outcome.

## 4. Verdict

**The V1.1 order term was mis-specified as a pairwise measure but valid as a per-word one; a correction is
required.** V1.2 (a) adopts the principled pairwise `d_ord|inv` (§2), (b) preserves V1.1's per-word constraint
unchanged as the self-case (§5), (c) fixes the label, and (d) exposes the pairwise form as a reported diagnostic
(§6). No selection threshold is retained "for convenience" — see §5/§6.

## 5. Preserved per-word selection constraint (corrected name; unchanged value & scale)

- **Measure (renamed):** **per-word self-order-informativeness**
  `s(x) = d_ord|inv(x, sort(x)) = d_edit(x, sort(x))` — mathematically **identical** to V1.1's `o(x)`.
- **Threshold:** `τ_self = 0.34`, **retained by mathematical identity** with V1.1 (the self-case formula and its
  `[0,1]` normalized-edit scale are unchanged), **not** for convenience. Documented as a **design convention**:
  `0.34 > 1/3`, so a word's ordered form must differ from its own inventory-sorted (Arm-D) form by **more than a
  trivial single-position coincidence**. **Higher = stricter.**
- **Role (unchanged):** a **hard per-word selection constraint** — every selected word must satisfy
  `s(x) ≥ 0.34`. **Prevents:** selecting a word whose ordered composition ≈ its inventory form, which would make
  `Δ_inventory = Acc(A) − Acc(D)` structurally ≈ 0 for that word.

Because this is the *only* order-related **selection** constraint in V1.1 and its value/scale/role are unchanged,
**the correction does not alter which subsets pass G0.**

## 6. Pairwise measure — role as a reported diagnostic (no new gate)

- The general **pairwise** `d_ord|inv(x, y)` (§2) is computed for every selected pair and **reported** in the G0
  outputs (`pairwise_metrics.json`) as the inventory-controlled order-distinctness diagnostic.
- **It is NOT a hard per-pair selection floor**, deliberately: two words with **different inventories**
  legitimately score `d_ord|inv = 0` (case 2/3) yet are perfectly identifiable **by inventory**; requiring every
  pair to be order-separable would wrongly exclude such valid, distinguishable words. Mutual distinctness of the
  selected set remains enforced by the **unchanged** `τ_edit = 0.34` total-distinctness floor (order **or**
  inventory suffices to tell two words apart).
- This clarifies the base prereg §7.3 wording: "separable from **its own order-scramble**" = the per-word
  `s(x) ≥ 0.34` constraint (§5); "separable from **every other selected word's composition**" = the total
  `τ_edit` floor; and "the set has words whose **order (not just inventory) is separable**" is **evidenced** by
  the reported pairwise `d_ord|inv` distribution (and guaranteed per-word by `s(x)`).
- **No hard threshold is frozen for the pairwise diagnostic.** The §3 calibration values (one-swap
  `0.333–0.667`; reversal up to `1.0`; length ≤ 3 non-separable) are **design-convention interpretive
  references**, preserved by the committed synthetic script — not a candidate-tuned gate.

## 7. Threshold handling summary (per the correction mandate)

- **Corrected pairwise formula scale:** `[0, 1]`, same normalized-edit family as V1.1 — so no scale mismatch is
  introduced.
- **`τ_self = 0.34`:** retained because the per-word self-case formula is **identical** to V1.1's (mathematical
  identity, §3), not for convenience; framed as a design convention (`> 1/3`).
- **Pairwise diagnostic:** reported-only; interpretive references frozen from **outcome-blind synthetic
  enumeration** (§3), never from any candidate distribution; described as design conventions, not
  mathematically-derived optima.

## 8. Repository discipline & scope (this artifact)

Docs-only plus **one tiny synthetic verification script** (`b1_12_order_distinctness_synthetic_check.py`,
opaque symbols only). **No** parser run on candidates; **no** candidate pool assembled; **no** candidate metric;
**no** subset search; **no** G0 run; **no** G1 work, contexts, judges, generators, or runs; **no** import of the
Varṇa–Affliction Resolution Test. V1.1, the original B1.12 preregistration, B1.10, and B1.11 are **unchanged**.

## 9. Guardrails

Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no ontology /
semantic-truth / Sanskrit-privilege / generation-utility claim; no individual-varṇa attribution. **B1.4b′
remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked. Structure, not validated meaning.**
