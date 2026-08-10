# Frozen-representation readout diagnostic — execution report

**Primary conclusion: `FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND`** (selected arm: none;
structural-prior-only signal: no). **Preserved:** `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`. No validation, confirmation,
eligibility, or KDA-unblocking claim is emitted.

The tested frozen readouts — learned (R1, R2) and even the structural-prior upper bound (R3) — did **not**
recover sufficient latest-state information from the frozen temporal-E1 representations.

## 1. Question and design
Does the frozen temporal E1 encoder already contain enough token-level information for latest-state
retrieval, with that information lost or blended by the existing mean-pooled read? The encoder is the merged
temporal E1 checkpoint (reconstructed at temporal final seed 6140; full param hash matches committed PR
#1354 evidence). **Every base parameter is frozen — no base optimizer step; only readout-head parameters
train.** Four arms on identical episodes/seeds, reserved seeds **7150–7154** (train 75, dev 750–752):

| arm | readout | added params | structural prior | role |
|---|---|---|---|---|
| **R0** | frozen mean pooling | 0 | no | reference (byte-identical to the existing C1 read) |
| **R1** | single additive-attention head over frozen key tokens, query-conditioned | 4 160 | no | primary learned |
| **R2** | two independent attention heads + linear proj(2d→d) | 16 576 | no | learned, must discover separation |
| **R3** | dual-head with fixed schema slot masks (entity {0,1} / temporal {2,3}) | 16 576 | **yes** | structural upper bound (never selectable; cannot alone emit PRESENT) |

T4 accuracy is **null-inclusive** correct-latest (the metric a readout must move). Improvement is measured
against **same-cohort R0** per seed. Inherited T1/T2/T3/T6/T7/T9 gate on null-excluded addressing.

## 2. Result (reserved seeds 7150–7154; 150 episodes/split)
| arm | mean T4 (null-incl) | Δ vs R0 | worst-seed T4 | null-excl addressing | seeds ≥0.75 | seeds ≥0.68 |
|---|---|---|---|---|---|---|
| R0 | 0.629 | — | 0.607 | 0.800 | 0/5 | 0/5 |
| R1 | 0.632 | +0.003 | 0.580 | 0.820 | 0/5 | 0/5 |
| R2 | 0.627 | −0.003 | 0.553 | 0.749 | 0/5 | 1/5 |
| R3 | 0.663 | +0.033 | 0.613 | 0.792 | 0/5 | 1/5 |

**No arm reaches the PRESENT bars** (mean T4 ≥ 0.75 and Δ ≥ 0.10, ≥4/5 seeds) **or the PARTIAL bars**
(mean T4 ≥ 0.68 and Δ ≥ 0.05, ≥4/5 seeds). R1/R2 (learned) are flat (+0.003 / −0.003); R3 (structural) is
the only arm with a directional effect (+0.033) but stays below the 0.68 partial floor. Since no learned arm
reaches partial and R3 does not reach the present bars, the mechanical conclusion is
**`SIGNAL_NOT_FOUND`**.

## 3. Mechanism (component means on T4)
| arm | null-rate | wrong-entity | right-entity-wrong-older | correct-entity | e2e |
|---|---|---|---|---|---|
| R0 | 0.279 | 0.027 | 0.065 | 0.695 | 0.635 |
| R1 | 0.271 | 0.015 | 0.083 | 0.715 | 0.637 |
| R2 | 0.252 | 0.021 | 0.100 | 0.727 | 0.632 |
| R3 | 0.219 | 0.021 | 0.097 | 0.760 | 0.671 |

The learned attention (R1) nudges null-excluded addressing up slightly (0.800 → 0.820) but does not convert
it into a null-inclusive gain; R2's added capacity/projection does not help (addressing 0.749). Only the
**structural-prior R3** moves the diagnosed components meaningfully — it lowers abstention (0.279 → 0.219)
and raises correct-entity (0.695 → 0.760) — yet the net T4 gain is only +0.033, far short of the bars. A
learned readout could not discover, from the frozen pooled query summary, the entity/predicate separation
that R3 is simply handed via fixed schema slots — and even that structural prior is insufficient on the
reserved cohort.

## 4. Dev → reserved: why fresh seeds mattered
On the development seeds R3 showed +0.089 (mean T4 0.704); on the reserved seeds it fell to +0.033 (0.663).
The structural effect **did not generalize** to held-out seeds. Because the gates were frozen a-priori
(from the R0 baseline + effect size, never from any readout result) and the reserved seeds were untouched
until protocol lock, this shrinkage is captured honestly rather than being locked in as a "signal."

## 5. Integrity
- **Frozen base:** every base parameter frozen; per arm/seed the frozen-base hash is unchanged and matches
  the protocol-lock value; the full encoder hash matches committed PR #1354 evidence. No base optimizer step.
- **Determinism:** byte-identical readout replay (R2, seed 7150). Runtime oracle-equivariance holds
  (candidate order carries no target signal).
- **Leakage / shortcut:** full inherited suite + AST + signature no-oracle proof over every readout forward;
  **shortcut baselines lexical 0.029 and global-latest 0.087, both ≤ 0.15** — R3's effect is structured
  retrieval, not a recency or surface-overlap shortcut.
- **No post-dev tuning:** the six frozen source hashes recorded at protocol lock are verified unchanged
  before the reserved run; dev fixtures were used only for correctness/frozen-base/determinism/activity/
  distinctness/leakage/budget. R1 vs R2 verified genuinely distinct (non-collapsed heads).
- Frozen `experiments/phase_lc/results/abc.json` (`b31989a3…`) unchanged; prior evidence untouched.

## 6. Interpretation (bounded)
`SIGNAL_NOT_FOUND` supports **only**: *the tested frozen readouts did not recover sufficient latest-state
information from the frozen temporal E1 representations.* Combined with the flat learned arms and the
non-generalizing structural arm, the evidence leans toward the frozen representations themselves lacking
enough entity/predicate/order separation for a bounded readout to exploit — which would make a **larger or
newly-trained architecture** necessary, or support a **stop** decision for the neural temporal branch. It
does **not** establish that no architecture could recover T4. `E1_TEMPORAL_TRANSFER_PARTIAL` stands; the
original BindingSlots neural-routing question remains unresolved; **KDA stays blocked**; the external-table
reliability path is unaffected. T5 (~0.38–0.44 across arms) is reported diagnostic-only and entered no gate,
selection, or conclusion. Any successor remains a separately authorized, capacity-scoped preregistration;
this diagnostic neither creates nor validates one.

## 7. Evidence
`experiments/bindingslots_e1_readout/results/`: `protocol_lock.json`, `dev_report.json`,
`final_per_seed.json` (full per-arm/seed/split table + readout hashes + frozen-base status),
`readout_analysis.json` (gates, per-arm flags, conclusion), `final_report.json`. Torch-free tests:
`tests/test_readout_gates.py` (12/12). CI: `.github/workflows/bindingslots-e1-readout-ci.yml`.
