# §15.13 Phase 4 — Continuation-inertia probe (result)

_Schema version: `15.13`._  
_Model: `Qwen/Qwen2.5-7B-Instruct`; benchmark: `truthfulqa_mc`; layer used: -1 (final); hidden dim: `3584`; max_new_tokens: 64 (greedy); NLI scorer: `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`._

## Cascade verdict (mechanical readout)

**Label:** `NO_MATERIAL_SIGNAL_IN_INERTIA`

**Rationale:** NO_MATERIAL: direction held (auc_inertia = 0.630 ≥ 0.5), but neither STRONG nor PARTIAL conditions met. ΔAUC vs chance = +0.130; ΔAUC vs R_sim = +0.259 (auc_sim = 0.371).

| metric | value |
|---|---|
| auc_inertia (AUC(−R_inertia, y)) | 0.6300 |
| auc_sim    (AUC(−R_sim,     y)) | 0.3706 |
| ΔAUC vs chance (0.5) | +0.1300 |
| ΔAUC vs R_sim         | +0.2593 |
| direction held (auc_inertia ≥ 0.5) | **yes** |

## Probe details

- N stimuli: 100 (correct: 22, wrong: 78; observed accuracy = 0.220)
- auc_inertia = **0.6300** (ΔAUC vs chance: +0.1300; ΔAUC vs R_sim: +0.2593)
- auc_sim     = 0.3706 (R_sim comparator baseline)
- direction held (auc_inertia ≥ 0.5): **yes**
- R_inertia distribution (per-stimulus, fp64):
  - min:    -1.1464
  - median: -0.9943
  - mean:   -0.9921
  - std:    0.0684
  - max:    -0.8066
- R_sim distribution (per-stimulus, fp64):
  - min:    +0.4475
  - median: +0.6422
  - mean:   +0.6328
  - std:    0.0836
  - max:    +0.7663
- |T_A| (decoded R_A token count) per stimulus: min 28, mean 63.2, max 64 (MAX_NEW_TOKENS = 64; Risk-6 disclosure)

## Selective-prediction operating points (disclosure only)

These κ@α operating points report what the −R_inertia abstention score achieves at the pinned alphas (0.35, 0.50, 0.75) under the N_MIN=10 eligibility floor. They are reported for transparency and do NOT enter the §15.13 cascade decision.

| α | τ* | κ@α | coverage | cond. acc. | n_admitted | eligible |
|---|----|-----|----------|------------|------------|----------|
| 0.35 | 1.0618 | 0.170 | 0.170 | 0.353 | 17 | yes |
| 0.50 | — | 0.000 | 0.000 | — | 0 | no |
| 0.75 | — | 0.000 | 0.000 | — | 0 | no |

At α_primary = 0.50: κ@α = 0.000; τ* = —.

## Pinned configuration (§15.13 §0.8-binding)

- **Model:** `Qwen/Qwen2.5-7B-Instruct`; layer `-1` (final layer only); hidden dim `3584`.
- **Benchmark:** `truthfulqa_mc` (single benchmark for v1; HaluEval is a v2 follow-up only if v1 shows signal).
- **Pairing rule:** `(Q_A_idx, Q_B_idx) = (i, (i + 50) mod 100) for i in 0..99` (100 unique pairs; each question appears once as Q_A and once as Q_B).
- **Pinned formula:** `R_inertia = cos(s_t, r_A) − cos(s_t, q_B)`.
- **Comparator baseline:** `R_sim = cos(q_A, q_B)`.
- **Direction convention:** lower R_inertia predicts correct (BCVF-faithful); test statistic AUC(-R_inertia, y).
- **Decoding:** greedy (temperature 0.0); `max_new_tokens = 64`.
- **Per-stimulus extraction protocol (3 forward passes):**
  - Pass 1: `[SYS][USER]Q_A[ASSISTANT]_` → greedy decode → extract `q_A` (last-token, layer −1, pre-decode) + `r_A` (mean over decoded assistant token positions, layer −1).
  - Pass 2: `[SYS][USER]Q_A[ASSISTANT]r_A_text[USER]Q_B[ASSISTANT]_` → greedy decode → extract `s_t` (last-token, layer −1, pre-decode at second `[ASSISTANT]` tag); decode Q_B response for NLI label scoring.
  - Pass 3: `[SYS][USER]Q_B[ASSISTANT]_` → forward only → extract `q_B` (last-token, layer −1).
  - Pass 1's verbatim `r_a_text` is spliced into Pass 2's prompt (Risk-3 mitigation: byte-identical R_A across passes).
- **NLI scoring (y label):** `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` via the §13.10 `label_correctness` helper (premise = Q_B + response; hypotheses = Q_B + each candidate; y = entails(gold) AND NOT entails(any distractor)).
- **Cascade thresholds:** STRONG AUC ≥ 0.75 AND ΔAUC ≥ +0.05 vs BOTH chance and R_sim; PARTIAL AUC ≥ 0.66 AND ΔAUC > 0 vs BOTH; otherwise NO_MATERIAL. Direction gate: auc_inertia < 0.5 → NO_MATERIAL automatic.
- **Selective-prediction:** alphas (0.35, 0.5, 0.75); primary alpha = 0.5; floor N_MIN = 10; disclosure only — does NOT enter cascade.

## Caveats (§0.8-disclosed)

- **One mechanism within the multi-turn class.** §15.13 tests ONE instantiation of continuation inertia: the pinned R_inertia formula at layer −1, on TruthfulQA-MC, with the +50 same-family pairing rule. A null result rules out THIS instantiation; H1 (state coherence) and H2 (intent competition) remain in the open-but-untested column for future top-level §0.X work.
- **Direction is pinned BCVF-faithful (lower R_inertia predicts correct).** A failure of the direction gate is a hypothesis failure (NO_MATERIAL automatic), not a sign-flip opportunity. Mirrors §15.11's enforcement.
- **R_sim controls for topical-overlap confound.** R_inertia must beat R_sim by the cascade margin to clear STRONG/PARTIAL; if same-family pairing is too topically clustered to separate inertia from topic similarity, the dual-comparator cascade lands NO_MATERIAL.
- **N = 100 stimuli.** AUC standard error at AUC ≈ 0.66 with N=100 is ~0.05–0.06; cascade bands at 0.66 and 0.75 are hit/miss-able by sampling noise. Mirrors §15.10/§15.11 power constraint.
- **Single model size: Qwen2.5-7B-Instruct.** Does not speak to scaling at 13B / 32B / 70B.
- **Greedy refusals.** Hedged or refusal Q_B responses score as non-entailment under §13.10 NLI semantics. If the model refuses more on Q_B questions where it is stuck on R_A, that is treated as genuine signal, not noise (Risk 2 disclosure).
- **|T_A| variability.** Pass 1 may emit an end token before MAX_NEW_TOKENS = 64; r_A pooling averages only over actually-generated non-end token positions (Risk 6 disclosure). The |T_A| distribution is reported in section 3.
- **NLI cost.** DeBERTa-v3-base-mnli-fever-anli is loaded for y label scoring; ~5 GB peak memory + ~2 min wall time at N=100 (Risk 8 disclosure).
- **No bootstrap CIs in v1.** Mirrors §15.10/§15.11; v1 reports point estimates against pinned bands.
- **Inherited from §15.10:** prompt-format vs §13.10 labelling regime (pinned chat-template `Qwen/Qwen2.5-7B-Instruct` regardless of §13.10's `Q: ... A:` raw-text labelling); question-text source (dump field if present, else HF dataset by `q_idx`).
- **Inherited from §15.11:** sklearn `penalty` FutureWarning filter installed precautionarily even though §15.13 uses only `roc_auc_score`.

## Cross-phase comparison (disclosure only)

| phase | mechanism class | verdict | this row modifies |
|---|---|---|---|
| §15.10 (Phase 1) | supervised linear (single-turn) | `PARTIAL_SIGNAL_IN_Z` | no |
| §15.11 (Phase 2) | layer-wise phase coherence (single-turn) | `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE` | no |
| §15.12 (Phase 3) | synthesis + closure | sealed (closure outcome pending implementation) | no |
| §15.13 (Phase 4) | continuation inertia (multi-turn) | `NO_MATERIAL_SIGNAL_IN_INERTIA` | n/a (this row is the result) |

This subsection is disclosure only and does not enter any phase's cascade decision. Each phase's verdict is an independent §0.8-binding mechanical readout; §15.13 does not reopen any prior phase.

## Audit-trail integrity

This result is a mechanical readout of the §15.13 cascade applied to per-stimulus R_inertia + R_sim cosines computed from Qwen-7B's last-layer hidden states across the three pinned forward passes. Per §0.8 discipline, the cascade label is binding regardless of any post-hoc interpretation.

§15.13 does not modify any §13/§14/§15.x verdict-of-record. The §13.9 hold remains binding. The §6.1 N=21 autonomy result is preserved. §15.10 PARTIAL_SIGNAL_IN_Z is preserved. §15.11 NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE is preserved. §15.12 closure is preserved. §15.13 is a fresh top-level §0.X testing a different mechanism class (multi-turn continuation inertia); its outcome is independent of the four single-turn canonical mechanism classes covered by §15.10 / §15.11 / §15.12.

The interpretation firewall scanned this document for 44 Class-3 forbidden statements before write. Detection would have triggered INTERPRETATION_VIOLATION (exit 4) without writing. The cascade verdict above is the binding §15.13 readout.
