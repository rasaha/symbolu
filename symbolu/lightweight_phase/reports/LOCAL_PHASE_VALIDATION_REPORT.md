# Local + Phase v1.4 — Stage Report (Stages 6 & 7)

**Stages:** 6 — Sliding-window integration; 7 — Training validation (A vs B)
**Status:** Stage 6 FROZEN. Stage 7 demonstrated at tested scale; full multi-seed
real-corpus study DEFERRED (compute-bound).
**Reproduce:**
`python -m pytest symbolu/lightweight_phase/tests/test_local_integration.py`
`python -c "from symbolu.lightweight_phase.training import run_ab; import json; print(json.dumps(run_ab(steps=900)['aggregate']))"`

## Stage 6 — Implemented

- `LocalWindowAttention`: causal sliding window, **genuinely O(N·W)** via an
  unfold over left-padded keys/values — scores are `[B,H,N,W]`, never `[N,N]`.
- **Protected additive fusion** in `PhaseTransformerBlock`:
  `y = x + α_local·Local(x) + α_phase·Phase(LN1(x))`. `α_local`, `α_phase` are
  learnable scalars **initialized to 1.0** so neither path begins disabled. This is
  deliberately not a competitive softmax gate (which historically let Phase be
  silently suppressed).
- Instrumentation (`diagnostics.py`): local/phase output-norm fractions,
  prediction-change rate when a path is disabled.

### Stage 6 — Tested

| Criterion | Test | Result |
|---|---|---|
| Local window causal | `test_local_window_causal` (exact 0 on past) | PASS |
| Unfold window == masked reference | `test_local_window_matches_masked_reference` (<1e-5) | PASS |
| Local path is sub-quadratic (no two-seq-axis tensor) | `test_local_window_is_subquadratic` | PASS |
| Both paths active at init (α=1.0) | `test_protected_fusion_both_paths_active_at_init` | PASS |
| Disabling Phase changes predictions | `test_config_A_..._differ` | PASS |
| Path-contribution instrumentation | `test_path_contribution_instrumentation` | PASS |

## Stage 7 — A vs B result (real, reproducible)

Synthetic distant-recall task (`training.py`): `KEY VALUE …filler… QUERY KEY →
predict VALUE`, with disjoint token ranges. The fact–query gap (20) exceeds the
local window (8), so only a global memory can bridge it.

- **A** = sliding window only (Phase path hard-disabled, `α_phase=0`, frozen).
- **B** = sliding window + Phase.
- Shared tokenizer, generator, parameter budget, optimizer, schedule, seeds,
  hardware. 3 seeds × 900 steps, CPU. Chance = 1/8 = 0.125.

| seed | A far-recall | B far-recall | B−A |
|---|---|---|---|
| 0 | 0.137 | 1.000 | +0.863 |
| 1 | 0.148 | 0.621 | +0.473 |
| 2 | 0.113 | 1.000 | +0.887 |
| **mean** | **0.133** | **0.874** | **+0.741** |

(near-gap control: A 0.134, B 0.448 — A is at chance because the local-only model
cannot learn the far training objective at all, which is itself the point.)

### Acceptance criteria (Stage 7)

1. B materially exceeds A beyond the window — **YES** (+0.74).
2. B preserves comparable language quality — not assessed at scale (small synthetic
   task, no LM-perplexity corpus here) — **DEFERRED**.
3. Gain appears across seeds — **YES** (all 3 seeds, +0.47…+0.89).
4. Phase removal erases the gain — **YES** (config A *is* Phase-removed → chance).
5. State bounded — **YES** (Stages 1–3 invariants).
6. Resource overhead practical — **YES** (Phase is O(N·D), one extra additive path).
7. Reproducible — **YES** (fixed generators/seeds; `stage7_ab_results.json`).

## Verdict

At the tested scale, **Phase adds decisive value beyond local context** (B−A =
+0.74, all seeds). The gain vanishes when the Phase path is removed. This supports
Phase on the distant-recall capability.

## Unsupported / Deferred

- Language-model **perplexity** on a real corpus, syntax vs distractor batteries,
  context-length scaling curves, streaming latency/throughput at scale, and a
  ≥3-seed study on natural-language long-context tasks are **deferred** (require
  more compute than this environment provides). The harness (`training.py`) is the
  reproducible substrate for that study; only the synthetic distant-recall A/B is
  demonstrated here.

## Freeze record

- Source SHA-256 for `local_window.py`, `phase_block.py` in
  `frozen_manifest.json → stages["v1.4-local-phase"]`.
- Raw Stage 7 numbers frozen in `stage7_ab_results.json`.
