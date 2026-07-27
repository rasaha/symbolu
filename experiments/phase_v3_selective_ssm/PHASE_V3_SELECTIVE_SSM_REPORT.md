<!-- RESULTS SECTIONS (§3 numbers, §16 endpoints, §20 final block) are filled from
     results/aggregate.json after the study completes. Fixed sections are written first. -->

# Phase v3 — a selective complex state-space memory

**Hypothesis (§0):** Phase becomes a usable long-range state-memory mechanism when
retention (A_t), writing (B_t) and reading (C_t) are all input-dependent, while preserving
causal streaming, bounded state, complex Phase dynamics, and O(N) execution.

Phase v3 is implemented as a **separately versioned** package `symbolu/phase_v3_experimental`.
Frozen Phase v1 (`symbolu/lightweight_phase`) and the completed Phase v2-S
(`symbolu/phase_v2_experimental`) are **not modified**; any v3 failure leaves them
byte-identical.

## 1. Frozen baseline

| item | value |
|---|---|
| branch | `claude/frozen-phase-transformer-diag-jzabnu` |
| git commit (baseline) | `956a3e8` |
| Phase v1 source hash (`phase_core.py`) | `99b5255f0bb20b066d8ad9087dcae54e624927e3b9f1c41f7f68128050afa806` |
| Phase v2-S source hash (`selective_phase.py`) | `4d8d1f8dac1e711d2b4c35dcbdf72570685b38f206e92b1353d364de03ce0251` |
| lightweight_phase tests | **98 passed** |
| freeze verifier | **FREEZE OK** |
| Python / PyTorch | 3.11.15 / 2.13.0+cu130 |
| hardware | Linux x86_64, 4 CPU (CPU-only run) |
| working tree at baseline | clean |

All three requirements (98/98, FREEZE OK, clean tree) held at baseline and are re-verified
after v3 is added (v1/v2 hashes unchanged — see §"Frozen guarantee").

## 2. Established prior findings (carried in)

| result | finding |
|---|---|
| Phase v1 | dense, no-decay accumulation dilutes rare focus information ~1/N |
| Phase v2-S | supervised selective writes preserve the distant focus signal (γ=1 persistent bank) |
| Phase v2-S end-to-end gate | does not autonomously learn useful selectivity |
| Phase v2-S oracle retention | does not improve hard slot eviction consistently (prior gated experiment: NEGATIVE) |
| Phase v2-M | shared gate + indiscriminate bank fusion bury the persistent signal |

The unresolved problem is **not** whether selective writing can work; it is whether a Phase
layer can learn an **autonomous, content-dependent state transition, write policy, and read
policy**. Phase v3 targets exactly that.

## 3. Method

### Recurrence (§3–6)
Per head, controls are input-dependent functions of the current token h_t only (causal):

```
A_t = γ_t · e^{i·ω_t}                          (retention transition, §4)
S_t = A_t ⊙ S_{t-1} + B_t ⊙ (k_t ⊙ v_t)         (selective write, §5)
R_t = γ_t · R_{t-1} + B_t · a_k                 (amplitude accumulator; detached normalizer)
o_t = C_t ⊙ Re(q_t ⊙ S_t) / Z_t,  Z_t = clamp(a_q·R_t, ε)   (selective read, §6)
```
with `γ_t = γ_min+(γ_max-γ_min)·σ(W_γ h)`, `ω_t = ω_max·tanh(W_ω h)`, `B_t = σ(W_B h)`,
`C_t = σ(W_C h)`. Bounds: γ ∈ [0.90, 0.9999], ω ∈ [−π, π], γ initialised toward long
memory (0.999). The **phase encoding is preserved from v1/v2** (bounded phase φ=π·sin(·),
complex k/v, amplitude a_q/a_k, normalizer clamp + detachment, causal layout) — §8. Only the
state dynamics become input-dependent.

### Variants (§7)
`V1` (frozen), `V2-S` (frozen), `V3-B` (write only), `V3-AB` (retention+write),
`V3-ABC` (retention+write+read). Multi-bank `V3-ABC-M` is deferred (only after ABC succeeds).
Primary comparison: **V3-ABC vs V2-S and V1**.

### Streaming & complexity (§9)
A stable chunked selective scan (double-precision accumulation, no global cumulative-product
division) computes S and R in O(N) with state size independent of N. Verified:
`full-sequence == token-by-token == chunked` to **≤1e-6** (measured ~2e-7); scan matches a
sequential reference exactly. Tests: `symbolu/phase_v3_experimental/tests/test_streaming_equivalence.py`.

### Task (§10)
Self-contained distant-focus retention. A **distinctly-typed** focus cue `CUE_e` names one of
16 entities at position 0; a flood of filler tokens and entity `EVENT_e` (some relevant = the
focus entity, most distractors) pushes the cue far out of any local window; at the final PROBE
position the Phase state is read to recover the focus identity. This reproduces the v1 dilution
problem: dense accumulation buries the single rare cue. Model = token-embed + sinusoidal-pos +
Phase variant + linear focus head on the (selective) readout at PROBE — **no cross-token mixing
outside the Phase recurrence**, so any long-range retention must come from the Phase state.
Trained at distances ≤256; evaluated at 64…4096 (the state is a streaming SSM).

### Training (§11–12) & probes (§13)
Curriculum over increasing distance; objectives L_focus + λ(L_write + L_retention + L_read) +
L_budget + L_stability, with three supervision modes: **A** fully supervised, **B** annealed to
zero (main target), **C** end-to-end from scratch. Probes (§13): each trained variant is frozen
and identical L2-regularised probes are fit on `local / state / raw_readout / selective_readout /
local+state / shuffled_state / random_state`; shuffled and random controls are reported beside
every result. Metrics: focus Top-1/Top-K, relevance F1/AUROC, calibration (ECE).

<!-- BEGIN GENERATED RESULTS -->
_(results tables, §16 endpoint checks, §14 ablations, §15 dynamics, §18 resources, and the
§20 final block are generated from `results/aggregate.json` and inserted here.)_
<!-- END GENERATED RESULTS -->
