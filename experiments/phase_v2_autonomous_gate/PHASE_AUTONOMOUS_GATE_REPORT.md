# Autonomous Selective-Write Learning — pilot report

Separately-gated study on the retained recurrence `S_t = S_{t-1} + B_t(k_t⊙v_t)` (γ=1, ω=0,
no C_t, single persistent bank, per-head gates, bounded O(N) streaming). The frozen v2-S core
(`symbolu.phase_v2_experimental.SelectivePhaseV2`) is used **unmodified**; the write gate is
driven through its existing `gate_override` hook. Frozen Phase v1 and v2-S are untouched.

Per the review plan, **go/no-go pilots were run before any full study.** Short distances
(d64–d512) saturate at 1.0 and do not discriminate, so all go/no-go metrics are read at
**d2048 / d4096** (2 seeds, reduced-but-meaningful budget).

## Two separate claims

### Claim 1 — token-only cue preservation: **VALIDATED**

Can a token-only gate `B_t = σ(W h_t)` autonomously store the distinct focus header and
suppress filler, with no permanent supervision?

| arm | d2048 state Top-1 | d4096 state Top-1 | header−filler write | write rate | control |
|---|---:|---:|---:|---:|---:|
| A supervised-teacher | 0.889 | 0.751 | +0.228 | 0.41 | 0.064 |
| B annealed→0 | **0.999** | **0.950** | +0.142 | 0.35 | 0.065 |
| F e2e-scratch | 0.978 | 0.851 | +0.182 | 0.37 | 0.061 |

- **The supervised teacher is not an upper bound** — annealed and scratch match or exceed it.
  Autonomous end-to-end training learns focus-header-vs-filler selectivity on its own
  (positive header−filler margin for every arm), and permanent gate supervision is slightly
  *harmful* (its BCE target tries to write distractor events too, diluting the bank).
- **Causal** (teacher, d2048, baseline 0.891): `remove_focus_header` → 0.249,
  `shuffle_focus_identity` → 0.060 (chance), `gate_force_zero` → 0.066 (chance),
  `gate_random_matched` → 0.331. Decode genuinely depends on the focus header and on writing.
- `gate_shuffle_examples` → 0.923 (≈ baseline): a no-op **by construction** — a token-only
  gate is an example-independent token-type policy (write cue/events, skip filler), so
  permuting it across examples changes nothing. This is a structural property, not a failure.

**Conclusion:** token-only autonomous focus-cue preservation is viable. The previous
teacher−scratch launch criterion is invalid for this task (scratch already succeeds).

### Claim 2 — focus-conditioned event selection: **PASSES the gate**

Can a causal focus-conditioned gate `B_t = σ(MLP([h_t, f_t, h_t⊙f_t, |h_t−f_t|]))` — with
`f_t` = the causal cue summary (rep at the header position), **no oracle match bit, no future
query, no target label at inference** — distinguish a later focus-matching event from
otherwise-identical distractor events? Paired within-example comparison (matched by design):

| gate | rel−distr margin (mean, 2 seeds) | standardized margin | AUROC (rel vs distr) | d2048 | d4096 |
|---|---:|---:|---:|---:|---:|
| token-only | +0.002 | +0.01 | 0.502 | 0.89 | 0.75 |
| **focus-conditioned** | **+0.106** | **+0.63** | **0.620** | **1.000** | **1.000** |

Causal controls on the conditioned gate (margin must vanish when the true focus signal is
destroyed):

| control | margin s0 | margin s1 |
|---|---:|---:|
| intact | +0.106 | +0.105 |
| focus header removed | +0.000 | +0.001 |
| focus summary shuffled (across examples) | +0.005 | +0.000 |
| random focus summary | +0.000 | +0.000 |

The margin collapses to ~0 whenever the causal focus summary is removed or scrambled — the
selection depends on **meaningful focus information, not sparsity or regularization**. (The
`shuffle_focus_identity` mutate left the margin unchanged because it relabels only the probe
target, not the cue token the gate reads — the other three controls are the decisive ones.)

**Acceptance (§ conditioned gate), 2 seeds:** margin > 0 (both) ✅; AUROC materially above 0.5
(0.62) ✅; shuffled/removed focus eliminates the margin ✅; long-distance state decode above
controls (1.000 vs ~0.06) ✅ → **conditioned gate PASSES.** Preferred bar (AUROC ≥ 0.70) not
yet reached (0.62); standardized margin ≥ 0.20 (0.63) ✅, d2048 ≥ 0.80 ✅, d4096 ≥ 0.60 ✅.

## Structural scope statement

This experiment tests **autonomous focus-cue preservation** (Claim 1) and **causal
focus-conditioned relevance selection** (Claim 2). A token-only gate preserves the cue but
**does not** identify which later record matches the distant focus; only the focus-conditioned
gate does. Token-only cue preservation must **not** be used to justify slots, consolidation,
retention ranking, or quadratic relevance guidance.

## §7 verdict

- **Long-distance teacher upper bound:** *invalid* — scratch/annealed match or exceed the
  supervised teacher; cue preservation is autonomous.
- **Token-only autonomous gate:** *preserves focus cue* (validated, causal).
- **Focus-conditioned gate:** *separates relevant events* (paired margin +0.106, AUROC 0.62,
  controls eliminate it).
- **Structural scope:** *focus-conditioned relevance selection* is learnable causally (beyond
  cue preservation).
- **Full study:** *launch authorized* (condition B passed). The focus-conditioned gate is the
  candidate for the later relevance-routing experiment. Downstream integration (memory refresh,
  consolidation, soft protection, slots, quadratic) remains **blocked** until the full study /
  relevance-routing gate is passed.

## Complexity & frozen guarantee

Bounded state (768 B / head-bank, independent of N), O(N) streaming, no N×N, no unbounded
cache. Frozen v1 (`99b5255f…`) and v2-S (`4d8d1f8d…`) byte-identical; `FREEZE OK`; 98/98.

Artifacts: `config.py, teacher.py, student_gate.py, train.py, annealing.py, distillation.py,
future_relevance.py, contrastive_gate.py, ablations.py, distance_eval.py, dynamics_analysis.py,
resource_audit.py, run_study.py, pilot.py, conditioned_analysis.py, run_pilots.py`,
`results/pilots.json`, `results/conditioned_analysis.json`.
