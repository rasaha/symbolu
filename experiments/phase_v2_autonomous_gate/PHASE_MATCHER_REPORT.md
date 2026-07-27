# Explicit focus↔event matcher study

Isolates **semantic matching before memory writing** on the frozen V2-S recurrence. The
question from the autonomous-gate pilot: the token-only gate preserves the focus cue but a
focus-conditioned gate only reached relevant-vs-distractor AUROC ≈ 0.62 (COND-MLP). Can an
explicit learned similarity function raise discrimination toward ≥ 0.70 **without changing the
recurrence**, and does the gain depend causally on the focus summary?

**Recurrence (frozen, unchanged):** `S_t = S_{t-1} + B_t(k_t⊙v_t)`, γ=1, ω=0, one persistent
bank, no C_t, no slots, no quadratic attention. Only the gate that produces B_t changes.

## Method

- **Matcher gates** (`matcher_gate.py`): project focus summary and event into a shared
  LayerNorm'd comparison space `z_f = LN(W_f f_t)`, `z_h = LN(W_h h_t)`; **cosine**
  `s = cos(z_f,z_h)/τ` or **bilinear** `s = z_fᵀ M z_h`. Two-stage gate splits event detection
  from relevance: `B_t = σ(W_e h_t)·σ(a·s+b)`. `f_t` is the causal header-captured summary (rep
  at the cue position) — no oracle match bit, no future query, no target label at inference.
- **Losses** (`matcher_losses.py`): pairwise ranking on `s` (primary), event-vs-filler BCE
  (secondary), write-budget, and a focus↔event alignment term.
- **Hard negatives** (`hard_dataset.py`): a frequency-matched repeated distractor entity so
  only focus-identity-match (not frequency/recency/format) separates relevant from distractor.
- **Discipline**: the pilot COND-MLP (AUROC ≈ 0.62) is preserved as the frozen baseline; the
  matchers are added as new arms. 2-seed pilot selects the candidate; a 3-seed hard-negative
  confirmation with causal controls decides promotion.

## Pilot (2 seeds) — candidate selection

| arm | AUROC | d2048 | d4096 |
|---|---:|---:|---:|
| token | 0.498 | 0.89 | 0.75 |
| COND-MLP (baseline) | 0.620 | 1.00 | 1.00 |
| cosine | 0.796 | 0.99 | 0.98 |
| bilinear | 0.830 | 1.00 | 0.99 |
| **bilinear+hard** | **0.837** | 1.00 | 1.00 |

Candidate = **bilinear+hard** (highest, most stable AUROC). Full table incl. losing arms:
`results/matcher_tables.md`, `results/matcher_pilot_aggregate.json`.

## Confirmation (3 seeds, hard negatives) — the decisive run

| arm | AUROC | hard AUROC | win-rate | d2048 state | d4096 state | wr rel/ord/hard/fill |
|---|---:|---:|---:|---:|---:|---:|
| token | 0.502 | 0.502 | 0.502 | 0.912 | 0.737 | 0.60/0.60/0.60/0.33 |
| COND-MLP | 0.607 | 0.608 | 0.608 | **1.000** | **1.000** | 0.08/0.00/0.00/0.00 |
| bilinear+hard | **0.803** | **0.804** | **0.804** | 0.986 | 0.988 | 0.77/0.39/0.39/0.10 |

Per-seed bilinear+hard AUROC 0.845 / 0.829 / 0.736 (min 0.736); d4096 0.993 / 1.000 / 0.970.

### Causal summary controls — the matcher is genuine, not a shortcut

| control | bilinear+hard hard-AUROC |
|---|---:|
| intact | 0.804 |
| focus summary removed | 0.508 |
| focus summary shuffled | 0.518 |
| random focus summary | 0.493 |

**causal_delta = 0.804 − 0.506 = +0.298.** The advantage collapses to chance without the correct
focus summary → genuine focus-event matching. (The 2-seed *focus-removed margin* red flag,
+0.36/+0.57, was an artifact of the raw-margin metric under a degenerate constant summary; the
AUROC-based controls resolve it.)

## Promotion decision

Discrimination criteria all pass (AUROC ≥ 0.70 every seed, hard AUROC ≥ 0.65, positive
rel−hard margin, win-rate ≥ 0.70, relevant-write > hard-write, controls eliminate the
advantage). **Not promoted**, because two downstream criteria fail:
- **hard false-write does not improve** over COND-MLP (0.39 vs 0.00),
- **d4096 decode is marginally worse** (0.988 vs 1.000).

The memory task is **already saturated**: COND-MLP decodes perfectly (1.000) by writing
essentially only the cue (write rates ≈ 0.08/0.00/0.00). Better relevance discrimination
therefore buys no downstream benefit here and costs extra writes on hard negatives. The
matcher's contribution is real and causal at the *discrimination* level; coupling it to a
*downstream* gain is the unresolved next problem. bilinear+hard **passed** the causal controls,
so the cosine fallback was not required.

## §11 Final report block

- **Frozen recurrence:** V2-S, γ=1, ω=0 (one persistent bank, no C_t/slots/quadratic).
- **Frozen matcher baseline:** COND-MLP (AUROC 0.61, decode 1.000).
- **Best explicit matcher:** bilinear+hard.
- **Overall AUROC:** 0.803 (min 0.736 across 3 seeds) vs COND-MLP 0.607.
- **Hard-negative AUROC:** 0.804 (min 0.738).
- **Paired relevant−hard-negative margin:** positive every seed (raw score +39.9; win-rate 0.804).
- **Paired win rate:** 0.804.
- **Relevant write rate:** 0.77.
- **Hard-negative write rate:** 0.39 (vs COND-MLP 0.00 — matcher writes more).
- **Long-distance decode:** d2048 0.986, d4096 0.988 (COND-MLP 1.000/1.000).
- **Focus-summary controls:** **pass** (removed 0.508, shuffled 0.518, random 0.493; causal_delta +0.298).
- **Matcher causality:** **supported** — discrimination depends causally on the focus summary.
- **Complexity:** bounded O(N), state 768 B, recurrence unchanged.
- **Explicit focus-event matching:** **validated as causal discrimination** (AUROC 0.62 → 0.80),
  but **not** as a downstream improvement (decode already saturated; write coupling unresolved).
- **Next permitted step:** **gate calibration / write-coupling on a non-saturated memory task** —
  the matcher's validated relevance score must be shown to improve downstream recall where writes
  actually matter (COND-MLP's perfect decode here leaves no headroom). Do **not** promote
  bilinear+hard into slots / consolidation / quadratic on the strength of discrimination alone;
  do not run further similarity-function sweeps (cosine ≈ bilinear causally; bilinear wins raw
  discrimination). If a non-saturated task still shows no downstream gain from better
  discrimination, move to contrastive focus-event representation learning.

## Frozen guarantee

Frozen Phase v1 (`99b5255f…`) and v2-S (`4d8d1f8d…`) byte-identical; `FREEZE OK`; 98/98.
Recurrence, γ, ω, state size, banks, readout, slots, quadratic attention all unchanged.

Artifacts: `matcher_gate.py, matcher_losses.py, hard_dataset.py, matcher_train.py,
matcher_study.py, matcher_confirm.py`; `results/{matcher_pilot_raw/, matcher_confirmation_raw/,
matcher_pilot_aggregate.json, matcher_confirmation_aggregate.json, matcher_tables.md}`;
`PHASE_MATCHER_MANIFEST.json`.
