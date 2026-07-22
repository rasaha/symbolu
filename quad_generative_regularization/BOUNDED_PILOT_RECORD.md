# Bounded Quad — Scale (α) Pilot Record

Per the bounded-experiment spec §3. One seed (seed 0), the frozen model/data/optimizer, the
Quad-native auxiliary (BD-D configuration, λ=1.0, τ=1.0), 2500 steps. Only `α ∈ {2, 4, 8}` were
tried; no larger search. One α is frozen before the three-seed experiment.

## Bounded formulation piloted

```
q_i = W_q·LN(h_i) ,  k_j = W_k·LN(h_j)
q̂_i = q_i / (‖q_i‖₂ + ε) ,  k̂_j = k_j / (‖k_j‖₂ + ε)     (ε = 1e-6, per head)
S^Q_bounded_{i,j} = α · ⟨q̂_i, k̂_j⟩          ∈ [−α, α]   (same causal mask + candidate softmax after)
```

α is a fixed, non-learnable scalar. No learnable temperature or logit scale is added (spec §2).

## Pilot outcomes (seed 0)

| α | in-dist acc | candidate entropy | Quad margin | internal select acc | `|S^Q|≤α` | verdict |
|--:|---:|---:|---:|---:|:--:|---|
| 2 | 0.965 | 0.815 | 2.27 | 1.000 | ✓ | learns; very soft; acc margin thin |
| **4** | **1.000** | **0.150** | **4.79** | **1.000** | ✓ | **learns reliably; entropy well above 0** |
| 8 | 1.000 | 0.008 | 8.50 | 1.000 | ✓ | learns but **entropy ≈ collapse** |

(Uniform-over-candidates entropy is ln 4 = 1.386.)

## Frozen selection: **α = 4**

Applying the pre-registered selection priority (§3):

1. **learns the primary task reliably** — α=8 and α=4 reach 100%; α=2 reaches only 0.965 (a thin
   margin over the 0.95 all-seeds criterion), so α=2 is *not* the reliably-learning choice.
2. **lowest scale reaching the threshold** *reliably* — α=4 is the lowest scale that hits 100%
   (α=2 is marginal).
3. **avoids near-zero candidate entropy** — α=8 fails this (entropy 0.008 ≈ the very collapse the
   experiment targets); α=4 keeps entropy at 0.150 — two orders of magnitude above D-full's
   ~0.000 and clearly bounded away from zero.
4. **no numerical instability** — all three stable; `|S^Q| ≤ α` holds for every α.

α = 4 is therefore the lowest scale that simultaneously (i) reliably learns the task to 100% and
(ii) keeps candidate entropy well away from zero. α = 8 is rejected for re-collapsing entropy;
α = 2 is rejected as an unreliable-accuracy boundary case (kept as a documented alternative).
**α is frozen at 4 for the three-seed experiment and is not re-tuned per arm.**
