# B1.4b′ — 10-Sample Three-Layer Diagnostic

**Status:** Diagnostic / debug trace only (docs-only). **Not an evidence run. No decoder trained, no baselines,
no scoring, no freeze.**
**Governed by:** `b1_4b_prime_prepare_mcrae_y.py` + manifest (`23968c4`), `stage_a_prime_coverage.py`
(`8d4b097`, read-only), `B1_4B_PRIME_EVIDENCE_RUN_PREFREEZE_REVIEW.md` (`869e9ae`).
**No raw McRae data committed. No private Y committed. No meaning validated. Original B1.4b remains blocked.
Track B remains blocked. Structure, not validated meaning.**

---

## 1. Purpose

This is a **10-sample three-layer diagnostic**: it shows, for 10 retained McRae concepts, that the B1.4b′ data
plumbing is populated end-to-end — `L1` Stage A′ phoneme/operator path, `L2` F-3 interaction latent, `L3`
prepared McRae `Y` target attaches. It is **not evidence**: it trains no decoder, runs no baselines, and makes
no semantic claim. Only **derived summaries** (counts, magnitudes) are reported — **no raw McRae feature
names/values** (Terms of Use).

---

## 2. Sample selection rule

- **Deterministic, non-cherry-picked:** a **fixed-seed** sample (`numpy.default_rng(0)`, 10 draws without
  replacement) from the **sorted 521 retained concept list** (the private, untracked concept list from
  `23968c4`).
- **Retained concepts only** — the 20 excluded concepts (18 homograph members + `cloak`/`clock`) are **not** in
  the retained list and cannot be drawn.
- **No cherry-picking for F-3 success** — the seed was fixed in advance; the sample was not adjusted after
  seeing F-3 outputs.
- **Word types are approximate manual descriptors** added for readability only — **not** taken from any McRae
  semantic field.
- **Raw McRae data not committed**; only counts/derived summaries appear here.

Sampled concepts: `apron, barn, bench, canoe, corkscrew, cushion, lemon, pen, sledgehammer, spinach`.

---

## 3. Layer definitions

- **L1 — Stage A′ phoneme normalization + operator sequence:** `word → phonemes (A_PRIME_EN) → M_σ = expm(Σ_j
  f_{σ,j} G_j)` (orthogonal 4×4; Stage A′ module, not frozen Stage A).
- **L2 — F-3 operator-interaction latent:** adjacent-commutator magnitudes (count, mean, max) + ordered-vs-
  reversed non-commutativity. Diagnostic only.
- **L3 — McRae `Y` target availability:** whether a prepared `Y` row (binary 242-dim attribute vector) attaches
  for the concept, and how many features are active. **Not** semantic validation.

---

## 4. Per-sample three-layer table

F-3 reported as (commutator count / mean / max / non-commutativity); all operators verified finite + orthogonal.
`activeY` = number of active (=1) attribute features in the concept's `Y` row (a derived count — **no feature
names/values shown**).

| concept | approx. type* | L1 phonemes | L1 ops | L1 | F-3 (n / mean / max / nonc) | L2 | Y present | activeY / dim | L3 | overall |
|---|---|---|---|---|---|---|---|---|---|---|
| apron | clothing | a-p-r-o-n | 5 | OK | 4 / 1.595 / 1.970 / 1.128 | OK | yes | 8 / 242 | OK | POPULATED |
| barn | structure | b-a-r-n | 4 | OK | 3 / 1.964 / 3.598 / 2.276 | OK | yes | 7 / 242 | OK | POPULATED |
| bench | furniture | b-e-n-ch | 4 | OK | 3 / 1.367 / 2.257 / 2.826 | OK | yes | 7 / 242 | OK | POPULATED |
| canoe | vehicle | k-a-n-o-e | 5 | OK | 4 / 2.497 / 3.492 / 0.655 | OK | yes | 6 / 242 | OK | POPULATED |
| corkscrew | tool | k-o-r-k-s-k-r-e-w | 9 | OK | 8 / 1.997 / 3.589 / 2.719 | OK | yes | 3 / 242 | OK | POPULATED |
| cushion | household | k-u-sh-i-o-n | 6 | OK | 5 / 2.817 / 3.725 / 0.494 | OK | yes | 8 / 242 | OK | POPULATED |
| lemon | food/plant | l-e-m-o-n | 5 | OK | 4 / 1.857 / 3.041 / 1.202 | OK | yes | 10 / 242 | OK | POPULATED |
| pen | small object | p-e-n | 3 | OK | 2 / 2.337 / 3.489 / 3.775 | OK | yes | 9 / 242 | OK | POPULATED |
| sledgehammer | large tool | s-l-e-d-g-e-h-a-m-m-e-r | 12 | OK | 11 / 2.172 / 3.556 / 0.987 | OK | yes | 8 / 242 | OK | POPULATED |
| spinach | food/plant | s-p-i-n-a-ch | 6 | OK | 5 / 2.038 / 3.712 / 2.792 | OK | yes | 8 / 242 | OK | POPULATED |

\* Approximate manual descriptor for readability only — not from any McRae field.

---

## 5. Layer 1 summary

- **Fully decomposed: 10 / 10** (`flag = full`).
- **Unsupported units: 0.**
- **Operator sanity: PASS** — every operator finite, 4×4, deterministic, orthogonal (`MMᵀ=I`).
- **Normalization caveats:** none for this sample; longer words (`corkscrew` 9, `sledgehammer` 12 phonemes)
  decompose cleanly, confirming the path scales past short words.

---

## 6. Layer 2 summary

- **F-3 computable: 10 / 10** (each ≥ 2 phonemes → ≥ 1 adjacent commutator; commutator counts 2–11).
- **Zero / non-informative F-3: 0** (no palindrome/reversal-degenerate case in this sample).
- **Non-commutativity magnitude range: 0.494 … 3.775.**
- **Reversal-symmetry limitation (recorded):** F-3 magnitude summaries are invariant to full sequence reversal
  (`‖[a,b]‖=‖[b,a]‖`, `‖prod−rprod‖` symmetric); not triggered here, but stands generally.
- **No claim that L2 means anything** — these are structural numbers, not semantic content.

---

## 7. Layer 3 summary

- **`Y` vector available for all 10 samples** (each retained concept has a prepared 242-dim binary row).
- **`Y` dimensionality: 242** (fixed).
- **Active-feature count range (sample): 3 … 10.**
- **No decoder trained; no semantic correctness assessed** — only that a target row **attaches**. Raw feature
  names/values are **not** shown (Terms of Use); only per-concept active-feature **counts**.

---

## 8. What this diagnostic shows

- The full **L1 → L2 → L3 data plumbing is populated** for these 10 mixed-type samples.
- **Stage A′ can feed F-3** — phoneme/operator sequences yield finite, computable interaction features.
- **The prepared McRae `Y` attaches as the Layer-3 target** — every sampled concept has a well-formed 242-dim
  attribute row.

Overall: the pipeline is wired end-to-end for inspection.

---

## 9. What this diagnostic does NOT show

- **Not** that F-3 predicts `Y`.
- **Not** that F-3 beats the phonological baseline (or any baseline — none were run).
- **Not** semantic validation.
- **No** `L1_L2_L3_ATTRIBUTE_SIGNAL`.
- **No** ontology / meaning proof, **no** `ONTOLOGICAL_SIGNAL`, **no** semantic-success claim.

Populated plumbing ≠ signal. The decisive comparison (F-3 vs phonology, at matched decoder capacity) is
deliberately **not** performed here.

---

## 10. Diagnostic labels

- **`B1_4B_PRIME_10_SAMPLE_L1_POPULATED`** — 10/10 decomposed + operator-sane. ✓
- **`B1_4B_PRIME_10_SAMPLE_L2_POPULATED`** — 10/10 F-3 computable, finite, non-degenerate. ✓
- **`B1_4B_PRIME_10_SAMPLE_L3_Y_ATTACHED`** — 10/10 `Y` rows attach (dim 242). ✓
- **`B1_4B_PRIME_10_SAMPLE_DIAGNOSTIC_COMPLETE`** — all three layers populated for the sample. ✓

(No `B1_4B_PRIME_10_SAMPLE_DIAGNOSTIC_FAIL`.)

---

## 11. Next gate

The next **formal** step remains the **evidence-run pre-freeze review** (`869e9ae`), currently
`B1_4B_PRIME_PREFREEZE_BLOCKED_BASELINES` — i.e. implement the run harness (F-3 extractor + 8 matched-capacity
baselines + concept-level-CV decoder + scorer), synthetic-test it, then re-review — **not** a semantic run. This
diagnostic changes nothing about that gate; it only confirms the data plumbing.

---

## 12. Boundary statement

> B1.4b′ 10-sample three-layer diagnostic completed. Layers populated for sample inspection only. No decoder
> trained. No semantic validation performed. No evidence freeze declared. No raw McRae data committed. Original
> B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.
