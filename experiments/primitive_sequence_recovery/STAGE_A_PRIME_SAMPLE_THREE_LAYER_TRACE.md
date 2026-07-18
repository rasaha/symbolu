# Stage A′ — Sample Three-Layer Trace Diagnostic

**Status:** Diagnostic / debug trace only (docs-only). **Not validation, not an evidence run, not a semantic
claim.**
**Governed by:** `stage_a_prime_coverage.py` (`8d4b097`, read-only), `PREREG_STAGE_A_PRIME_COVERAGE_ONLY.md`,
`PREREG_B1_4B_L1_L2_L3_OPERATOR_INTERACTION.md`.
**No independent Y used. No semantic validation. No evidence freeze. B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.**

---

## 1. Purpose

This is a **sample three-layer trace**: it shows *mechanically* how the Stage A′ front end feeds a B1.4b-style
path — `word → Stage A′ phoneme sequence → operator matrices → F-3 interaction features → L3 (blocked, no Y)` —
on a small deterministic sample. It performs **no** semantic validation, declares **no**
`L1_L2_L3_ATTRIBUTE_SIGNAL`, and is **not** proof of meaning. The F-3 numbers are trace outputs, not evidence.
Computed with the existing Stage A′ module (imported read-only; **not** rebuilt or modified).

---

## 2. Sample selection

- **Sanskrit (10):** the **first 10 non-excluded** entries of `frozen/word_list.json` (`spelling` field), in
  file order → `A_PRIME_SA`.
- **English (10):** the **first 10** entries of the B1.3 concrete-object candidate pool (`items[].word` **only**
  — never `dictionary_anchor` or any meaning field), in file order → `A_PRIME_EN`.
- **No cherry-picking:** first-N-in-order, automatic selection; not chosen for success or failure.

---

## 3. Layer definitions

- **L1 — Stage A′ phoneme normalization + operator sequence:** `word → phonemes` (language-aware normalizer,
  no silent fallback) → `M_σ = expm(Σ_j f_{σ,j} G_j)` (orthogonal 4×4; Stage A′ module, **not** frozen Stage A).
- **L2 — F-3 operator-interaction / commutator diagnostic features:** adjacent-commutator magnitudes
  (mean, max) + ordered-vs-reversed non-commutativity. Diagnostic only.
- **L3 — decoder/probe stage:** **blocked** — no independent frozen `Y` exists, so no verdict is possible.

---

## 4. Per-word trace table

F-3 = (comm-mean / comm-max / non-commutativity). All operators verified finite + orthogonal (`MMᵀ=I`).

| word | pool | Stage A′ phonemes | L1 | F-3 (cm / cx / nonc) | L2 | L3 | notes |
|---|---|---|---|---|---|---|---|
| kāla | SA | k-aa-l-a | OK | 2.487 / 3.492 / 1.176 | OK | BLOCKED_NO_Y | full, 0 unsupported |
| lobha | SA | l-o-b-h-a | OK | 2.657 / 3.621 / 1.792 | OK | BLOCKED_NO_Y | `o,h` now covered |
| moha | SA | m-o-h-a | OK | 2.909 / 3.041 / 3.145 | OK | BLOCKED_NO_Y | full |
| kāma | SA | k-aa-m-a | OK | 3.179 / 3.492 / 1.904 | OK | BLOCKED_NO_Y | full |
| krodha | SA | k-r-o-dh-a | OK | 1.769 / 2.047 / 1.210 | OK | BLOCKED_NO_Y | `dh` digraph |
| bhaya | SA | b-h-a-y-a | OK | 2.722 / 2.979 / 1.671 | OK | BLOCKED_NO_Y | full |
| prema | SA | p-r-e-m-a | OK | 2.038 / 3.023 / 1.865 | OK | BLOCKED_NO_Y | full |
| jala | SA | jh-a-l-a | OK | 2.498 / 3.523 / 2.906 | OK | BLOCKED_NO_Y | `j` retained → **not** a palindrome (nonc≠0) |
| agni | SA | a-g-n-i | OK | 2.132 / 3.184 / 2.881 | OK | BLOCKED_NO_Y | full |
| vāyu | SA | v-aa-y-u | OK | 2.983 / 3.253 / 2.616 | OK | BLOCKED_NO_Y | **failed frozen chart; now full** |
| chair | EN | ch-e-r | OK | 1.052 / 1.221 / 1.744 | OK | BLOCKED_NO_Y | full |
| table | EN | t-a-b-l-e | OK | 2.001 / 3.598 / 2.797 | OK | BLOCKED_NO_Y | full |
| bed | EN | b-e-d | OK | 2.895 / 3.533 / 1.520 | OK | BLOCKED_NO_Y | full |
| bench | EN | b-e-n-ch | OK | 1.367 / 2.257 / 2.826 | OK | BLOCKED_NO_Y | `ch` digraph |
| shelf | EN | sh-e-l-f | OK | 1.895 / 2.663 / 2.678 | OK | BLOCKED_NO_Y | `sh` digraph |
| cup | EN | k-u-p | OK | 2.182 / 3.725 / 0.440 | OK | BLOCKED_NO_Y | `c→k` (coverage G2P) |
| bowl | EN | b-o-l | OK | 2.849 / 3.621 / 2.193 | OK | BLOCKED_NO_Y | full |
| box | EN | b-o-k-s | OK | 3.338 / 3.621 / 2.196 | OK | BLOCKED_NO_Y | `x→k,s` |
| bottle | EN | b-o-t-t-l-e | OK | 1.286 / 3.621 / 2.345 | OK | BLOCKED_NO_Y | full |
| basket | EN | b-a-s-k-e-t | OK | 2.472 / 3.598 / 1.786 | OK | BLOCKED_NO_Y | full |

---

## 5. Layer 1 results

- **Total sampled:** 20 (10 SA + 10 EN).
- **Fully decomposed:** **20 / 20** (`flag = full`).
- **Unsupported units:** **0** across the whole sample.
- **Operator sanity:** **PASS** — every operator finite, 4×4, deterministic, orthogonal (`MMᵀ=I`).
- Note the contrast with the frozen 14-grapheme chart, where `vāyu` failed entirely and most words dropped
  characters; under Stage A′ all 20 sample words decompose fully.

---

## 6. Layer 2 results

- **F-3 computable:** **20 / 20** (every word ≥ 2 phonemes → ≥ 1 adjacent commutator).
- **Zero / non-informative interaction cases:** **0** in this sample (all non-commutativity values > 0).
- **Reversal / palindrome limitations:** **none triggered here.** Notably `jala` → `jh-a-l-a` (Stage A′ retains
  the `j` as `jh`), which is **not** a palindrome, so its non-commutativity is non-zero (2.906) — unlike the
  frozen-chart trace where `jala` → `a-l-a` (a palindrome) gave `0.000`.
- **F-3 insensitivity to exact reversal (general limitation, carried forward):** the F-3 magnitude summaries
  remain **invariant to full sequence reversal** (`‖[a,b]‖ = ‖[b,a]‖`; `‖prod − rprod‖` symmetric). No sample
  word here equals its own phoneme reverse, so none exhibits the `0.000` degeneracy — but the limitation stands
  for any word that does, and any oriented/signed extension must be separately pre-registered.

---

## 7. Layer 3 results

**L3 remains BLOCKED for all 20 samples** (`A_PRIME_L3_BLOCKED_NO_Y`): no independent frozen `Y` exists, so no
decoder/probe verdict is possible. The trace shows only **where** a decoder would attach (consuming the L2 F-3
vector); it fits nothing and scores nothing. **No output here is interpreted as meaning**, and no
`L1_L2_L3_ATTRIBUTE_SIGNAL` / `ONTOLOGICAL_SIGNAL` is declared.

---

## 8. Success criteria

- **`A_PRIME_L1_TRACE_SUCCESS`** — full decomposition (no unsupported units) + operator sanity for the word.
- **`A_PRIME_L2_F3_TRACE_SUCCESS`** — F-3 features computable (≥ 2 phonemes → ≥ 1 commutator).
- **`A_PRIME_L3_BLOCKED_NO_Y`** — no independent frozen `Y`, so L3 is (correctly) blocked.
- **`A_PRIME_TRACE_FAIL`** — decomposition, operator, or F-3 trace fails.

---

## 9. Per-word verdicts

All 20 sample words: **`A_PRIME_PIPELINE_TRACE_SUCCESS_L1_L2_ONLY`** (L1 + L2 succeed) **and**
**`A_PRIME_L3_BLOCKED_NO_Y`** (L3 blocked). No word is `A_PRIME_TRACE_FAIL_L1` / `A_PRIME_TRACE_FAIL_L2`.

| verdict | count |
|---|---|
| A_PRIME_PIPELINE_TRACE_SUCCESS_L1_L2_ONLY (+ L3 blocked) | 20 |
| A_PRIME_TRACE_FAIL_L1 | 0 |
| A_PRIME_TRACE_FAIL_L2 | 0 |

---

## 10. Overall verdict

**`A_PRIME_SAMPLE_PIPELINE_SUCCESS_BUT_SEMANTIC_BLOCKED`.**

Stage A′ mechanically feeds the B1.4b-style path end-to-end on the sample (L1 + L2 succeed for all 20 words),
but semantic validation is **uniformly blocked** for want of an independent frozen `Y`. This is a **substrate /
plumbing** success only — **not** evidence of meaning.

---

## 11. Relation to B1.4b

- This shows Stage A′ **can mechanically feed** a B1.4b′-style pipeline on samples (L1 + L2), removing the L1
  coverage wall that blocked the frozen-chart path.
- It **does not unblock** the original frozen B1.4b, and it is **not** substituted into any B1.4b/B1.4a artifact.
- A future **B1.4b′** requires a **separate pre-registration / freeze** that explicitly adopts Stage A′ as L1 —
  never a silent substitution.
- **An independent `Y` is still required** (`Y_OVERLAP_PENDING`); coverage/plumbing success does not supply it.
- The F-3 reversal-symmetry limitation is inherited and must be carried into any B1.4b′ pre-registration.

---

## 12. Boundary statement

> Stage A′ sample three-layer trace completed. Pipeline traced only. No Y matrix created. No semantic validation
> performed. No evidence freeze declared. B1.4b remains blocked. Track B remains blocked. Structure, not
> validated meaning.
