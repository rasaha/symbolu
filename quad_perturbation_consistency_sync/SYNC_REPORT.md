# Perturbation-Consistent Quad Retrieval — Final Report

**Track:** `quad_perturbation_consistency_sync/` (separate; imports `qgr` read-only; prior Quad track
and conclusions unmodified). **Compute:** CPU-only. **Data:** `RESULTS_SYNC/`.
**Decision:** **SYNC_MATCHES_BD_A** — the null hypothesis is **not rejected**.

> Falsification study. Bar = **BD-A (task-only)**. Success required BD-Sync to *strictly and
> significantly exceed* BD-A while passing both guardrails. It did not. No USE, phase,
> cross-head/-layer synchronization, routing, gating, entropy/temperature penalties, teacher
> forcing, or inference-time component was used.

## 1. Protocol

See `PROTOCOL.md` (pre-registered). Bounded Quad (α=4), λ_sync=0.5 (pilot), 2500 steps, 5 seeds.
Label-free consistency `L_sync = mean_h JS(A_h(x), sg(A_h(x̃)))` over canonical pair-bucket
retrieval distributions; x̃ is a semantic-equivalent perturbation (pair permutation / positional
filler / inserted distractors) preserving every query→value relation. 8/8 track tests pass.

## 2. Generalization comparison (5 seeds)

| arm | in-dist | hard-cond gen (mean±sd) | OOD suite | entropy | x-head diversity |
|---|---:|---:|---:|---:|---:|
| **BD-A** (bar) | 0.986 | **0.634 ± 0.015** | 0.842 | 1.23 | 0.012 |
| BD-D (labelled aux) | 0.526 | 0.126 ± 0.015 | 0.152 | 0.51 | 0.010 |
| **BD-Sync** | 0.990 | **0.607 ± 0.021** | 0.817 | 0.94 | 0.191 |
| BD-Sync-Early | 0.991 | 0.632 ± 0.023 | 0.851 | 1.10 | 0.063 |
| Shuffled-Pair | 0.966 | 0.626 ± 0.023 | 0.800 | 1.38 | 0.000 |

Per-condition (mean): longer-context — BD-A 0.830, BD-Sync **0.761**, BD-Sync-Early 0.822,
Shuffled 0.846; higher-distractor — all ≈0.51–0.54; two-systems — all ≈0.51–0.54.

**BD-Sync does not exceed BD-A** — it is marginally *below* on the primary generalization score
and on the OOD suite, and clearly below on longer-context. BD-Sync-Early (minimal intervention)
sits essentially on BD-A. Training curves and the grouped-bar comparison: `RESULTS_SYNC/plots/`.

## 3. Statistical significance (primary criterion)

Paired per-seed differences (BD-Sync − BD-A) on the hard-condition generalization score:
`[+0.005, −0.018, −0.056, −0.021, −0.044]`, **mean −0.027**, **1/5 seeds favor BD-Sync**. Exact
paired sign-permutation test (2⁵=32 flips): **p = 0.125** (not significant; and the point
estimate is negative). The improvement required to reject the null is absent.

## 4. Shuffled-pair control — no semantic-consistency-specific effect

Pairing each x with an **unrelated** sample's perturbation (Shuffled-Pair) yields gen **0.626**,
statistically indistinguishable from — indeed slightly above — BD-Sync's 0.607. Whatever small
effect the consistency term has is **not** attributable to semantic consistency; it is at most
generic regularization. This is decisive against the mechanism the hypothesis proposed.

## 5. Progressive-perturbation degradation (the mechanistic crux)

Retrieval distribution drift (JS) by stage 0→5 (seed 0):

| arm | s0 | s1 | s2 | s3 | s4 | s5 |
|---|---:|---:|---:|---:|---:|---:|
| BD-A | 0.00 | 0.10 | 0.045 | 0.272 | 0.096 | 0.287 |
| **BD-Sync** | 0.00 | 0.015 | 0.002 | **0.189** | 0.018 | **0.201** |
| BD-Sync-Early | 0.00 | 0.083 | 0.008 | 0.239 | 0.038 | 0.225 |
| Shuffled-Pair | 0.00 | 0.084 | 0.001 | 0.252 | 0.026 | 0.272 |

**The consistency objective worked as intended:** BD-Sync's retrieval is measurably *more stable*
under every perturbation stage (drift 0.201 vs BD-A's 0.287 at the hardest stage). **Yet its task
generalization did not improve.** Increasing retrieval invariance — exactly what the hypothesis
prescribed — did **not** move generalization. Retrieval stability is therefore **not the causal
bottleneck** for MQAR generalization at this configuration.

## 6. Causal verification (Guardrail 1 — PASS)

Zeroing the attention (Quad retrieval) collapses every arm to chance; BD-Sync clean 0.996 →
attention-zeroed 0.088 (retained 0.088 ≪ 0.40). Quad retrieval remains the causal binding
pathway under the consistency objective — no other pathway took over. `plots/causal_guardrail.png`.

## 7. Entropy & diversity (Guardrail 2 — PASS)

BD-Sync entropy 0.94 (not collapsed), cross-head diversity 0.191, head specialization 0.658 —
**healthy, no collapse, no identical heads.** Notably the consistency objective *raised* head
diversity and specialization above BD-A (0.191 vs 0.012; 0.658 vs 0.300) while dropping head-mean
selection accuracy to 0.05 — it reorganized attention toward more diverse, less head-mean-selective
heads. Shuffled-Pair drove diversity to 0.000 (near-identical heads) yet still generalized (0.626),
**decoupling head-organization metrics from generalization**. Both BD-Sync and BD-Sync-Early stay
inside healthy bounds; no arm is rejected on G2.

## 8. Failure-case analysis

BD-Sync's only material loss vs BD-A is **longer-context** (0.761 vs 0.830). Mechanistically, the
consistency term equalizes the query's pair-bucket distribution across perturbations that include
positional shifts; this appears to slightly *reduce* the model's use of position-specific cues
that BD-A exploits for length generalization — i.e. the invariance pressure trades a little
length-generalization for stability that the task did not need. On higher-distractor and
two-systems, BD-Sync is within noise of BD-A. No guardrail failure or instability occurred; the
failure is simply *absence of benefit*, plus a small length-generalization cost.

## 9. Final mechanistic interpretation

The hypothesis was: *the generalization failure is insufficient retrieval invariance, and a
consistency objective will fix it.* The data **falsify the premise**:

1. The objective **did** increase retrieval invariance (lower drift at every stage) and changed
   attention organization (more diverse heads) — so it is doing real work, not inert.
2. Generalization **did not** improve (matched, marginally below BD-A; p = 0.125).
3. The **shuffled-pair** control matches BD-Sync — no semantic-consistency-specific effect.

Therefore retrieval-distribution stability is **correlated with the intervention but not causal
for generalization**: task-only learning (BD-A) already discovers a retrieval organization whose
generalization is as good as — or better than — anything the consistency objective produces.
This is consistent with, and extends, the whole program's finding: **the less we shape the Quad
retrieval, the better it generalizes.** BD-A > BD-Sync ≥ Shuffled-Pair ≫ BD-D (labelled aux). The
ordering by amount of retrieval shaping is monotone with *harm*.

## 10. Recommendation — should perturbation-consistency replace explicit Quad aux supervision?

**No — and more importantly, neither auxiliary is warranted.** Perturbation-consistency is
clearly preferable to the labelled Quad auxiliary (BD-Sync 0.607 vs BD-D 0.126; it preserves
binding and health where BD-D collapses them), so *if one were forced to choose between the two
auxiliaries*, consistency wins decisively. But the correct baseline is **BD-A (task-only)**, and
BD-Sync does not beat it. The evidence says: **do not add a retrieval-shaping auxiliary at all**;
task loss on the bounded architecture already yields the best-generalizing retrieval. Research
effort is better spent on the retrieval's *parameterization/architecture* (which the causal track
localized as the seat of binding) than on any training-time objective that shapes the retrieval
distribution — labelled or consistency-based.

## Decision — **SYNC_MATCHES_BD_A**

BD-Sync preserves reliable in-distribution binding, keeps Quad retrieval causal, and stays inside
healthy entropy/diversity bounds, but **does not exceed BD-A** on generalization (mean −0.027,
p = 0.125, 1/5 seeds). The null hypothesis — task-only learning already finds the best retrieval
organization — **stands**.

## Reproduce

```bash
pip install -r ../quad_generative_regularization/requirements.txt
OMP_NUM_THREADS=4 python -m pytest tests/ -q
OMP_NUM_THREADS=4 python run_sync.py --threads 4     # -> RESULTS_SYNC/
```
