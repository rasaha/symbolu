# Ablation Results (v0.1)

All numbers from `relationship_claim_validation/results/run_v0_1.json` (deterministic;
two runs byte-identical). Corpus: **48 synthetic claims**, **59 documents**.

> **Read as mechanism validation on synthetic self-authored data**, not real-world
> efficacy (`FINAL_VERDICT.md`). V4's perfect scores are by construction.

---

## 1. Per-ablation summary

| Ablation | Config | Retained | Precision | Recall | Status acc. | Det. removed | Adjudicated |
|---|---|--:|--:|--:|--:|--:|--:|
| **V0** | none (identity baseline) | 48 | 0.4167 | 1.0000 | 0.2500 | 0 | 0 |
| **V1** | deterministic only | 0 | 1.0000 | 0.0000 | 0.2083 | 5 | 0 |
| **V2** | + Judge A (advocate) | 32 | 0.6250 | 1.0000 | 0.7500 | 6 | 0 |
| **V3** | + Judge B (challenger) | 24 | 0.8333 | 1.0000 | 0.9167 | 6 | 0 |
| **V4** | + Judge C (full) | 20 | 1.0000 | 1.0000 | 1.0000 | 6 | 4 |

Confusion (retained-decision level): tp = supported preserved, fp = false
acceptance, tn = unsupported removed, fn = false removal.

| Ablation | tp | fp | tn | fn |
|---|--:|--:|--:|--:|
| V0 | 20 | 28 | 0 | 0 |
| V1 | 0 | 0 | 28 | 20 |
| V2 | 20 | 12 | 16 | 0 |
| V3 | 20 | 4 | 24 | 0 |
| V4 | 20 | 0 | 28 | 0 |

## 2. Paired vs V0 (fixes / breaks / net)

| Ablation | Fixes | Breaks | Net | Net-fix-rate | 95% CI (bootstrap) |
|---|--:|--:|--:|--:|---|
| V1 | 28 | 20 | +8 | 0.1667 | [−0.1250, 0.4167] |
| V2 | 16 | 0 | +16 | 0.3333 | [0.2083, 0.4583] |
| V3 | 24 | 0 | +24 | 0.5000 | [0.3542, 0.6458] |
| V4 | 28 | 0 | +28 | 0.5833 | [0.4375, 0.7083] |

## 3. What each component contributes (marginal reading)

- **Deterministic only (V1)** achieves precision 1.0 but recall 0.0 — it can only
  *remove* structurally invalid claims and abstains on everything else. Its net vs
  V0 is barely positive (+8) with a CI spanning 0: **deterministic checks alone are
  insufficient**, and destroy recall. This is the honest cost of abstention without
  semantic support.
- **+ Judge A (V2)** recovers recall to 1.0 and lifts precision to 0.625 and status
  accuracy to 0.75, with **0 breaks** — the advocate confirms genuinely supported
  relations. But it **cannot see contradictions**: 12 false acceptances remain.
- **+ Judge B (V3)** raises precision to 0.833 and status accuracy to 0.917, still
  **0 breaks** — the challenger removes the 8 contradicted claims. 4 false
  acceptances remain (the equally-explicit direction conflicts, which V3 resolves in
  the advocate's favor).
- **+ Judge C (V4)** raises precision and status accuracy to 1.0 by routing exactly
  those **4** equally-explicit conflicts to UNKNOWN / manual review — eliminating
  the last false acceptances. **Judge C measurably improves over two judges alone.**

## 4. Monotonic precision ladder (0 breaks from V2 onward)

`V0 0.417 → V2 0.625 → V3 0.833 → V4 1.000`, recall held at 1.0 (V2–V4). The
alternative hypothesis pattern (fixes > 0, breaks = 0) holds from V2 onward **on
this synthetic corpus**.
