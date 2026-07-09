# B1.4b — 10-Word Layer-Trace Diagnostic

**Status:** Diagnostic / debug trace only (docs-only artifact). **Not validation, not an evidence run, not a
semantic claim.**
**Governed by:** `PREREG_B1_4B_L1_L2_L3_OPERATOR_INTERACTION.md`, `B1_4B_IMPLEMENTATION_PLAN.md`,
`B1_4B_REAL_DATA_PREP_AND_FREEZE_PLAN.md`. Synthetic harness ref: `458fb1e`.
**No independent Y used. No semantic validation. No evidence freeze. Track B remains blocked.**
**Structure, not validated meaning.**

---

## 1. Purpose

This is a **10-word layer-trace diagnostic**: it shows *mechanically* how B1.4b would carry a handful of
repo-local words through **L1** (frozen operators) and **L2** (F-3 interaction features), and *where* an **L3**
decoder/probe would attach — **stopping there**, because no independent frozen target `Y` exists. It is a
pipeline-validity / debug trace. It performs **no** semantic validation, declares **no**
`L1_L2_L3_ATTRIBUTE_SIGNAL`, and is **not** proof of meaning. The F-3 numbers below are trace outputs, not
evidence.

---

## 2. Sample selection

- **Source:** `experiments/primitive_sequence_recovery/frozen/word_list.json` (repo-local, already present).
- **Selection rule (no cherry-picking):** the **first 10 non-excluded entries** in file order (`exclude_flag ==
  false`), i.e. `w000`–`w009`. Deterministic, not chosen for expected success or failure.
- **Selection is automatic** (first-10-in-order), not manual.
- The 10: `kāla, lobha, moha, kāma, krodha, bhaya, prema, jala, agni, vāyu`.

**Decomposition note (important):** the **frozen Stage A operator layer** (`symbolu_neural/structural_v1`) is
keyed to a **14-grapheme chart** (`p b t d k g s z m n r l a i`). This trace therefore decomposes each **romanized
spelling** through the real `structural_v1.decompose()` (read-only) — it does **not** use the list's
`varna_sequence` tokens (which are multi-character varṇas outside the chart). Characters absent from the chart
(diacritics, and consonants like `h, y, v, j`, vowels `o, e, u`) are **dropped with explicit warnings** (no
silent fallback). This is a faithful trace of the *actual* frozen operator layer and honestly surfaces that
layer's limited coverage.

---

## 3. Layer definitions

- **L1 — frozen operator sequence** `M_σ = expm(Σ_j f_{σ,j} G_j)` (orthogonal 4×4; Stage A; read-only).
- **L2 — F-3 operator-interaction / commutator latent** (adjacent-commutator magnitudes + non-commutativity;
  no norm/magnitude state features).
- **L3 — decoder/probe interpretation** (`y = D(z)`), separate from F.
- **Validation** requires an **independent frozen `Y`**, which is **currently absent** (coverage audit:
  `Y_SOURCE_METADATA_UNAVAILABLE`). Without it, no L3 verdict is possible.

---

## 4. Per-word trace table

Real trace via `structural_v1` (read-only). `kept` = chart units retained; `dropped` = characters not in the
frozen chart. F-3 = (comm-mean, comm-max, non-commutativity).

| word | varṇa_seq (list) | chart units (kept) | dropped | L1 | L2 | L3 | F-3 (cm / cx / nonc) | notes |
|---|---|---|---|---|---|---|---|---|
| kāla | ka-la | k-l-a | ā | L1_TRACE_OK | L2_F3_TRACE_OK | L3_BLOCKED_NO_Y | 1.576 / 1.985 / 2.578 | 1 diacritic dropped |
| lobha | la-bha | l-b-a | o,h | L1_TRACE_OK | L2_F3_TRACE_OK | L3_BLOCKED_NO_Y | 3.371 / 3.598 / 1.367 | 2 chars dropped |
| moha | ma-ha | m-a | o,h | L1_TRACE_OK | L2_F3_TRACE_OK | L3_BLOCKED_NO_Y | 3.023 / 3.023 / 3.023 | reduced to 2 units |
| kāma | ka-ma | k-m-a | ā | L1_TRACE_OK | L2_F3_TRACE_OK | L3_BLOCKED_NO_Y | 2.385 / 3.023 / 0.573 | 1 diacritic dropped |
| krodha | ka-ra-dha | k-r-d-a | o,h | L1_TRACE_OK | L2_F3_TRACE_OK | L3_BLOCKED_NO_Y | 3.019 / 3.877 / 2.737 | 2 chars dropped |
| bhaya | bha-ya | b-a-a | h,y | L1_TRACE_OK | L2_F3_TRACE_OK | L3_BLOCKED_NO_Y | 1.799 / 3.598 / 1.661 | 2 chars dropped |
| prema | pa-ra-ma | p-r-m-a | e | L1_TRACE_OK | L2_F3_TRACE_OK | L3_BLOCKED_NO_Y | 2.287 / 3.023 / 3.594 | 1 char dropped |
| jala | ja-la | a-l-a | j | L1_TRACE_OK | L2_F3_TRACE_OK | L3_BLOCKED_NO_Y | 1.985 / 1.985 / **0.000** | palindrome a-l-a → reversal-symmetry (§8) |
| agni | ga-na | a-g-n-i | — | L1_TRACE_OK | L2_F3_TRACE_OK | L3_BLOCKED_NO_Y | 2.132 / 3.184 / 2.881 | full coverage (no drops) |
| vāyu | va-ya | *(empty)* | v,ā,y,u | **L1_TRACE_FAIL** | **L2_F3_TRACE_FAIL** | L3_BLOCKED_NO_Y | — | all 4 chars off-chart → empty sequence |

---

## 5. Layer 1 analysis

L1 is a **pipeline-validity check only**. 9/10 words decompose to a non-empty chart-unit sequence and map to the
frozen orthogonal operators (verified `M M^T = I`) → `L1_TRACE_OK`. **`vāyu` fails** (`L1_TRACE_FAIL`): all four
of its characters (`v, ā, y, u`) are outside the frozen 14-grapheme chart, so `decompose()` returns an **empty**
sequence — correctly, via the layer's no-silent-fallback rule. This is a **coverage** outcome, not a semantic
one. Note also the substantial **character dropping** across the sample (diacritics and `h, y, v, j, o, e, u`):
the trace is faithful to the real operator layer, and that layer covers only 14 graphemes — a real limitation to
carry into any freeze.

---

## 6. Layer 2 analysis

For the 9 L1-OK words, F-3 interaction features **compute** (`L2_F3_TRACE_OK`): adjacent-commutator magnitudes
and the ordered-vs-reversed non-commutativity distance are finite and non-degenerate (except where structure
makes them zero, see below). `vāyu` has no units, so F-3 cannot be formed (`L2_F3_TRACE_FAIL`).

**Known limitation surfaced live:** `jala` → kept units `a-l-a`, a **palindrome**, so the ordered product equals
the reversed product and **non-commutativity = 0.000**. This is a concrete instance of the recorded
reversal-symmetry limitation (§8): the current F-3 summaries cannot distinguish a sequence from its reverse.

---

## 7. Layer 3 analysis

**L3 cannot produce a validation verdict.** With no independent frozen `Y`, there is nothing to predict or score
against; every word is `L3_BLOCKED_NO_Y`. The trace only shows **where** a decoder/probe `D` would attach — it
would consume the L2 latent `z` (the F-3 vector) and map it toward attribute predictions — but that map is
neither fit nor evaluated here. No decoder is run; no fit-to-target is computed; no label beyond the pipeline
trace is emitted.

---

## 8. Reversal-symmetry limitation (recorded)

The current F-3 magnitude summaries are **invariant to full sequence reversal**: `‖[a,b]‖ = ‖[b,a]‖` and
`‖prod − rprod‖` is symmetric, so a sequence and its exact reversal map to identical F-3 features. The `jala`
(`a-l-a`) row above, with non-commutativity `0.000`, is a live demonstration. **Non-reversal order sensitivity
remains** (the other rows have non-zero, order-dependent values). Any oriented/signed extension that would break
this symmetry must be **separately pre-registered** and cannot be added post-hoc.

---

## 9. Pass/fail criteria

- **PIPELINE_PASS** — L1 and L2 traces succeed (non-empty decomposition, orthogonal operators, computable F-3);
  semantic validation is **blocked** (no `Y`).
- **PIPELINE_FAIL** — decomposition, operator trace, or F-3 trace fails.
- **VALIDATION_BLOCKED_NO_Y** — no independent frozen `Y`, so **no** semantic pass/fail is possible for any word.

---

## 10. Per-word verdicts

| word | verdict |
|---|---|
| kāla | PIPELINE_PASS_VALIDATION_BLOCKED_NO_Y |
| lobha | PIPELINE_PASS_VALIDATION_BLOCKED_NO_Y |
| moha | PIPELINE_PASS_VALIDATION_BLOCKED_NO_Y |
| kāma | PIPELINE_PASS_VALIDATION_BLOCKED_NO_Y |
| krodha | PIPELINE_PASS_VALIDATION_BLOCKED_NO_Y |
| bhaya | PIPELINE_PASS_VALIDATION_BLOCKED_NO_Y |
| prema | PIPELINE_PASS_VALIDATION_BLOCKED_NO_Y |
| jala | PIPELINE_PASS_VALIDATION_BLOCKED_NO_Y |
| agni | PIPELINE_PASS_VALIDATION_BLOCKED_NO_Y |
| **vāyu** | **PIPELINE_FAIL_DECOMPOSITION** |

Tally: **9 × PIPELINE_PASS_VALIDATION_BLOCKED_NO_Y**, **1 × PIPELINE_FAIL_DECOMPOSITION**. No word reaches a
semantic verdict (all `VALIDATION_BLOCKED_NO_Y`).

---

## 11. Overall verdict

**`TEN_WORD_PIPELINE_TRACE_PASS_VALIDATION_BLOCKED_NO_Y`.**

The diagnostic itself succeeded: the pipeline traced 9/10 words cleanly through L1 and L2, and **correctly
flagged** the 1 decomposition failure (`vāyu`) rather than coercing it — exactly the intended behavior. Semantic
validation is uniformly **blocked** for the absence of an independent frozen `Y`. Recorded caveats: (a) 1/10
decomposition failure and heavy character-dropping reflect the frozen 14-grapheme chart's limited coverage; (b)
the F-3 reversal-symmetry limitation is live (`jala`). **None of this is evidence of meaning**, and no
`L1_L2_L3_ATTRIBUTE_SIGNAL` / `ONTOLOGICAL_SIGNAL` is declared.

---

## 12. Boundary statement

> B1.4b 10-word layer trace completed. Pipeline traced only. No independent Y used. No semantic validation
> performed. No evidence freeze declared. Track B remains blocked. Structure, not validated meaning.
