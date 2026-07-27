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

## 4. Main study — focus Top-1 by variant × distance (mode B_annealed, 3-seed mean)

| variant | d64 | d128 | d256 | d512 | d1024 | d2048 | d4096 |
|---|---:|---:|---:|---:|---:|---:|---:|
| V1 (frozen) | 0.911 | 0.993 | 0.998 | 0.828 | 0.658 | 0.548 | 0.474 |
| **V2-S (frozen)** | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** | **0.938** |
| V3-B (write only) | 1.000 | 1.000 | 1.000 | 1.000 | 0.999 | 0.544 | — |
| V3-AB (retention+write) | 0.995 | 0.952 | 0.819 | 0.609 | 0.438 | 0.383 | — |
| V3-ABC (retention+write+read) | 0.999 | 0.998 | 0.958 | 0.792 | 0.433 | 0.318 | 0.378 |

Controls (shuffled/random state) are at chance (~0.05–0.08) for every variant and distance —
the state genuinely contains the focus identity; nothing is a probe shortcut. Full per-seed
values: `results/aggregate.json`, `results/raw/*.json`.

**Reading:** V2-S dominates (perfect through 2048, 0.938 at 4096). V3-B (fixed γ=0.999,
no rotation) holds to 1024 then decays (fixed γ<1). Adding input-dependent retention/rotation
(V3-AB, V3-ABC) degrades earlier and further — **the more input-dependent transition dynamics
are added, the worse long-range retention becomes.**

## 5. §16 acceptance evaluation (V3-ABC, the nominated primary variant)

| # | criterion | result | met |
|---|---|---|:--:|
| 16.1 | Phase-state decode − shuffled/random ≥ 0.20 | +0.72 (d512), +0.36 (d1024), +0.24 (d2048) | ✅ |
| 16.2 | selective readout ≥ recurrent state | selective < state everywhere (readout is a lossy D-dim projection) | ❌ |
| 16.3 | relevance F1 ≥ V2-S+0.10 or ≥0.70 | 0.40–0.44 ≈ V2-S (0.42–0.45); ≪0.70 | ❌ |
| 16.4 | materially above V1 through 2K | V3-ABC − V1 = −0.04/−0.23/−0.23 at 512/1024/2048 (below V1) | ❌ |
| 16.6 | annealed ≥ 80% of supervised | B/A = 1.65 at d2048 (both mediocre; annealing not worse) | ✅ |
| 16.7 | no write-all/write-none collapse | write ~0.28, no collapse | ✅ |
| 16.8 | ablating A_t/B_t/C_t → predicted loss | confirmed (see §6) | ✅ |
| 16.9 | streaming equivalence ≤1e-6 | ~2e-7 | ✅ |
| 16.10 | bounded state, O(N) | 768 B/head-bank, O(N) (see §8) | ✅ |

The "strongest success" bar (V3-ABC Phase-only Top-1 ≥0.70 through 2K) is **not met**
(0.32 at d2048). V3-ABC is a valid streaming selective SSM whose state provably holds the
focus (16.1/16.8/16.9/16.10), but it does **not** beat V1 at long range and is far below V2-S.

## 6. §14 causal ablations (V3-ABC, eval-time overrides, d512, seed 0)

| override | state Top-1 | reading |
|---|---:|---|
| baseline | 0.506 | trained V3-ABC |
| **omega_zero** | **0.823** | removing rotation *recovers* +0.32 — ω_t is actively destroying decode |
| A_fixed (γ=const, ω=0) | 0.780 | fixing the whole transition helps |
| A_shuffled | 0.094 | scrambling A_t across examples → chance (A_t matters) |
| gamma_fixed (ω kept) | 0.463 | fixing γ alone does **not** help — ω still scrambles |
| B_forced_zero | 0.066 | nothing written → chance (write necessary) |
| B_forced_one (dense) | 0.389 | dense write dilutes vs selective (selective write helps) |
| C_forced_zero | state 0.506 / sel 0.066 | C_t gates only the readout, never the state |
| write_only (isolate) | 0.780 | selective write alone is the best-performing configuration |

The ablation is unambiguous: **input-dependent rotation ω_t is the failure source**;
selective write is necessary and beats dense write; C_t is inert on the state.

## 7. §15 dynamics (V3-ABC, seed 0)

γ per head [0.9999, 0.9997, 0.9973, 0.9999] (horizons 373–9367 — retention *does* learn long
memory); write rate per head [0.42, 0.24, 0.16, 0.31], mean 0.28 (selective, no collapse);
read rate [0.99, 0.96, 0.92, 0.97] (C_t ≈ pass-through); **`omega_abs_mean = 2.30`** (near the
π ceiling — the rotation is large and input-varying); state norm per head [70, 11, 3, 22]
(persistent-accumulation growth under γ≈1 — decode stays bounded via the detached normalizer).
No inactive/identical heads. The one flagged pathology (`state_explosion`) is expected
persistent growth, not divergence.

## 8. 2×2 transition ablation (§the requested experiment) — isolating γ_t vs ω_t

Write gate, curriculum, parameter budget (25,744 each), data, seeds, state size, and readout
held **identical**; cells differ only in the transition. 3-seed mean state Top-1:

| cell | d256 | d512 | d1024 | d2048 | d4096 |
|---|---:|---:|---:|---:|---:|
| **B** (γ=1, ω=0) | 1.000 | 1.000 | 1.000 | **1.000** | 0.983 |
| **B+γ** (γ_t, ω=0) | 1.000 | 1.000 | 1.000 | **0.998** | 0.330 |
| **B+ω** (γ=1, ω_t) | 0.986 | 0.899 | 0.596 | **0.423** | 0.286 |
| **AB** (γ_t, ω_t) | 0.819 | 0.609 | 0.438 | **0.383** | 0.380 |
| V2-S (reference) | 1.000 | 1.000 | 1.000 | 1.000 | 0.938 |

Transition dynamics at d2048 (3-seed mean):

| cell | eff γ | accumulated rotation (turns) | phase-alignment cos | cue retention→probe | state norm |
|---|---:|---:|---:|---:|---:|
| B | 1.0000 | 0.0 | +1.00 | 1.000 | 17.9 |
| B+γ | 0.9997 | 0.0 | +1.00 | 0.547 | 15.5 |
| B+ω | 1.0000 | 380.1 | +0.03 | 1.000 | 28.0 |
| AB | 0.9974 | 288.2 | +0.03 | 0.126 | 9.8 |

**Interpretation (applying the specified rules):**
- **B+γ ≈ B** (both 1.000 through 2048): dynamic decay γ_t provides **no measurable benefit on
  this pure-persistence task** — and at 4096 it *hurts* (0.330 vs 0.983) because the learned
  γ≈0.9997 decays the cue to ~55% retention by 2048. It is *not generally useless*; it simply
  yields no gain here and slightly harms at extreme distance.
- **B+ω < B** (0.423 vs 1.000 at 2048): **token-dependent rotation is harmful** — ~380
  accumulated turns of rotation drive phase alignment to ~0.03 and collapse decode.
- **AB < B+γ**: **recurrent rotation cancels/destroys usable retention** — AB is the worst cell.
- Both no-rotation cells (B, B+γ) **match V2-S** (~1.0 through 2048), confirming the winning
  mechanism is **selective write + γ=1 persistence**.

## 9. §18 resources & frozen guarantee

| variant | params | state bytes (B=1) | tokens/s | O(N) latency 2N/N |
|---|---:|---:|---:|---:|
| V1 | 24,704 | 768 | 515,056 | 1.95 |
| V2-S | 24,964 | 768 | 518,820 | 2.10 |
| V3-B/AB/ABC | 25,744 | 768 | ~150–165k | 1.7–3.2 |

All variants: bounded state independent of N, no N×N, no unbounded cache. V3 is ~3× slower on
CPU (sequential chunk-carry loops) but remains O(N). **Frozen guarantee:** after all v3 work,
`FREEZE OK`, `98 passed`, and v1 (`99b5255f…`) / v2-S (`4d8d1f8d…`) source hashes unchanged.

## 20. Final block

- **Frozen baselines:** Phase v1 and v2 remain unchanged (hashes verified).
- **Best variant:** **none of the V3 variants** beats V2-S; among V3, write-only V3-B is best.
- **Input-dependent retention (A_t):** **no measurable gain on this pure-persistence task**
  (B+γ ≈ B through 2048; slight harm at 4096). Not generally useless — simply no benefit here.
- **Selective write (B_t):** the effective mechanism — necessary (forcing B=0 → chance) and
  superior to dense writing (forcing B=1 → 0.389). It is what V2-S already provides.
- **Selective read (C_t):** **does not change state information** — provably inert on the state
  (C ablations leave state decode at 0.506), pass-through after retuning; only gates the readout.
- **Phase-state focus decoding:** V3-ABC 0.79/0.43/0.32 at 512/1024/2048 (≫ controls) but below
  V1 at ≥1024; V2-S = 1.000 through 2048.
- **Selective-readout focus decoding:** below the recurrent state at every distance (lossy
  projection); §16.2 not met.
- **Distance stability:** V2-S stable to 4096 (0.938); every input-dependent-transition variant
  degrades with distance.
- **Distractor robustness:** consistent with the distance results (raw in `aggregate.json`).
- **Annealed-supervision retention:** V3-ABC B/A = 1.65 at d2048 (annealing not worse than full
  supervision — both mediocre).
- **Ablation causality:** **supported** — ω_zero recovers +0.32, A_shuffled → chance, B=0 →
  chance, C inert on state.
- **Streaming & complexity:** bounded state (768 B/head-bank), O(N), streaming equivalence ~2e-7.
- **Verdict:** **Phase v3 does NOT operate as a superior learnable selective complex
  state-space memory on this task.** The single decisive mechanism is *selective write*; the
  novel v3 additions — token-dependent complex rotation ω_t (harmful) and input-dependent decay
  γ_t (no gain) — do not help, and C_t is inert. **V2-S (`S_t = S_{t-1} + B_t(k_t⊙v_t)`) is
  retained as the winning recurrence; recurrent rotation ω_t is retired.**
- **Next permitted step:** **autonomous selective-write learning** — determine whether the
  validated V2-S write gate B_t can be learned *without* permanent gate supervision. Do **not**
  proceed to selective read, multi-bank, slots, hard eviction, or quadratic attention until an
  autonomous or supervision-annealed gate passes its acceptance gate.
<!-- END GENERATED RESULTS -->
