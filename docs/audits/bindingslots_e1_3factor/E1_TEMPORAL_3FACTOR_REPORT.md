# E1 latest-state three-factor factorial — execution report

**Primary verdict: `T4_FACTORIAL_NO_INTERVENTION_SELECTED`** (selected cell: none).
**Co-emitted / preserved:** `E1_TEMPORAL_TRANSFER_PARTIAL` · `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`
· `KDA_VALIDATION_BLOCKED`. No transfer-validation or KDA-unblocking verdict is emitted.

Minimal, non-oracle, capacity-fixed **learnable** factors do **not** recover the T4 latest-state shortfall
on the temporal family — individually or in any combination. Only F1 (learned null gating) produces a
positive effect, and it is below the required margin and far below the absolute bar.

## 1. Design (as preregistered in PR #1357, executed after protocol lock)
One full **2³ = 8-cell factorial** (`000` reference · `100` F1 · `010` F2 · `001` F3 · `110` · `101` ·
`011` · `111`) over **one shared fresh reserved cohort per seed**, fresh reserved seeds **7140–7144**
(train 74, dev 740–742; all mechanically disjoint from every prior program seed). Every cell shares
identical task instances, per-seed training batches, the frozen **C1** recipe (D=64, 1200 steps, τ=0.07,
batch 48, lr 1e-3, 1500 train episodes, ~32 keys/episode), base architecture, and evaluation logic. The
eight cells differ **only** in which minimal factor side-heads are enabled.

### Factors (minimal, query-conditioned, non-oracle; base capacity unchanged)
| Factor | Mechanism | Added params | No-oracle guarantee |
|---|---|---|---|
| **F1** null gating | learned correction to the **null** score from the query repr + summary stats of the real-candidate scores | **+569** | never reads match/answer |
| **F2** entity retrieval | low-rank learned entity-matching residual (query proj · key proj), applied to all real candidates | **+1041** | never reads evaluator entity identity |
| **F3** temporal ranking | query-conditioned "does recency matter" gate × learned score of the candidate's own position-token embedding, applied to all real candidates | **+131** | never reads the ground-truth latest index / metadata |

Base params 22 528 unchanged across all cells; added params per cell 0–1741. Factor output gains are
zero-initialised (each cell starts identical to `000` and must **learn** its effect). No embedding-dim,
depth, step, lr, or temperature change → **no cell is capacity-confounded**.

### Metric conventions
- **T4 accuracy (gated)** = null-**inclusive** correct-latest = P(argmax over the K real keys + null =
  target). This is the honest end-to-end addressing decision (abstention counts as a miss) and is the
  metric the three factors are designed to move. The null-**excluded** addressing_top1 is also reported.
- Inherited **T1/T2/T3/T6/T7/T9** gate on the inherited null-**excluded** addressing_top1 (regression
  guards). **T5** is reported diagnostic-only and excluded from every gate, the selection, and the verdict.

## 2. Result (reserved seeds 7140–7144; 150 episodes/split)
| cell | factors | added | T4 null-incl (mean) | worst-seed | Δ vs 000 | T4 null-excl addr | seeds passing all primary |
|---|---|---|---|---|---|---|---|
| 000 | — | 0 | 0.588 | 0.533 | — | 0.796 | 0/5 |
| 100 | F1 | 569 | **0.623** | 0.560 | **+0.035** | 0.777 | 0/5 |
| 010 | F2 | 1041 | 0.577 | 0.533 | −0.011 | 0.784 | 0/5 |
| 001 | F3 | 131 | 0.589 | 0.533 | +0.001 | 0.788 | 0/5 |
| 110 | F1+F2 | 1610 | 0.615 | 0.560 | +0.027 | 0.765 | 0/5 |
| 101 | F1+F3 | 700 | 0.620 | 0.560 | +0.032 | 0.773 | 0/5 |
| 011 | F2+F3 | 1172 | 0.580 | 0.540 | −0.008 | 0.781 | 0/5 |
| 111 | all | 1741 | 0.612 | 0.560 | +0.024 | 0.761 | 0/5 |

**No cell reaches T4 ≥ 0.85, none improves the reference by ≥ 0.05, and 0/5 seeds clear all primary gates
in every cell.** Therefore no cell qualifies and **no intervention is selected**. (The mechanical
selection rule — fewest factors → lowest params → highest worst-seed T4 → highest mean T4 — is moot with an
empty qualifying set.)

## 3. Factorial main effects and interactions (on T4 null-inclusive)
| term | F1 | F2 | F3 | F1×F2 | F1×F3 | F2×F3 | F1×F2×F3 |
|---|---|---|---|---|---|---|---|
| effect | **+0.034** | −0.009 | −0.000 | **+0.001** | −0.002 | +0.000 | −0.000 |

Only **F1** has a positive main effect. On the underlying components, F1 reduces the abstention
(null-selection) rate by **−0.059** — the mechanism works as intended — but simultaneously nudges
wrong-entity (+0.010) and right-entity-wrong-older (+0.015) up as suppressed abstentions are re-exposed as
addressing errors, so the net T4 gain is only +0.034. F2 and F3 leave their targeted components essentially
unchanged (baseline wrong-entity is already only 0.029 and right-older only 0.081, so there is little room),
and both slightly **lower** null-excluded addressing (000: 0.796 → 111: 0.761).

**The pre-flagged F1×F2 interaction does not reproduce (+0.001).** The strong interaction in the *oracle*
counterfactual diagnostics (PR #1356: D2 correct-entity-but-null-allowed recovered 1.4% vs D3
correct-entity+null-suppressed 68%) depended on **oracle** entity identity. Minimal **learnable** entity
retrieval (F2) cannot supply that entity selection, so the interaction that the oracle exposed is not
achievable by these learnable factors. This is an important boundary: an oracle-measured ceiling is not, by
itself, evidence that a learnable mechanism can reach it.

## 4. Why 0.85 is out of reach here (mechanistic account)
Cell 000 partition on T4 (reserved mean): correct-latest 0.588, **abstention 0.301**, wrong-entity 0.029,
right-entity-wrong-older 0.081; correct-entity 0.669. Two ceilings bound the minimal factors:
1. **Abstention (~0.30)** is the largest component; F1 removes only ~0.06 of it under the no-match
   false-accept constraint (FA ≤ 0.30 held throughout).
2. A **residual addressing ceiling** — even null-**excluded**, baseline addressing is ~0.80 and the F2/F3
   residuals do not lift it (they slightly lower it). Reaching a null-inclusive 0.85 would require pushing
   null-excluded addressing above 0.85 **and** near-perfect abstention; the minimal learnable factors do
   neither.

## 5. Integrity
- **Determinism:** byte-identical param-hash replay (cell 111, seed 7140). Runtime **oracle-equivariance**
  holds (permuting candidate order permutes scores identically; null invariant) — candidate order carries
  no target signal.
- **Leakage / no-oracle:** full inherited temporal suite passes (no answer in keys, no status in queries,
  no exact identifier overlap, disjoint pools, unseen eval identities, lexical + global-latest heuristic at
  chance, no external-table import) **plus** the AST + signature proof that `E1F.scores/forward` receive
  only `(key_tokens, query_tokens, tau)` and no factor forward references any ground-truth / evaluator /
  metadata identifier.
- **No post-dev tuning:** the seven factor/harness source files' sha256 recorded at protocol lock are
  verified unchanged before the final run. Development fixtures were used only for
  correctness/determinism/activity/leakage/budget — no architecture search, no per-cell tuning, no
  gate-setting (gates are the GIVEN numbers).
- Frozen `experiments/phase_lc/results/abc.json` (`b31989a3…`) unchanged; prior evidence untouched.

## 6. Interpretation boundaries
This non-recovery supports **only** that these minimal, capacity-fixed, non-oracle learnable factors did
not recover the T4 latest-state shortfall within the bounded factorial on the temporal family. It does
**not** establish that no learnable mechanism could (a larger-capacity or differently-structured mechanism
is untested and out of scope here), and it does **not** weaken any prior result. `E1_TEMPORAL_TRANSFER_PARTIAL`
stands; the original BindingSlots neural-routing question remains unresolved; **KDA stays blocked**; the
external-table reliability path is unaffected. T5 predecessor/successor (~0.35 across all cells) is reported
for completeness only and did not enter any gate, the selection, or the verdict.

## 7. Evidence
`experiments/bindingslots_e1_3factor/results/`: `protocol_lock.json`, `dev_report.json`,
`final_per_seed.json` (full per-cell/seed/split table + param hashes + factor activity),
`factorial_analysis.json` (gates, effects, interactions, selection, verdict), `final_report.json`.
Torch-free tests: `tests/test_factor_gates.py` (11/11). CI: `.github/workflows/bindingslots-e1-3factor-ci.yml`.
