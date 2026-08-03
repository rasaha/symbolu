# Five-Seed Holdout Validation — Results & Verdict

**Date:** 2026-08-03 · Run `fiveseed_run1` (torch 2.13.0, CPU fp32, 4 threads, holdout seeds 3–7,
1200 steps). Pre-registration `25c48a19` (frozen before training). Data:
[`../artifacts/five_seed_results_run1.json`](../artifacts/five_seed_results_run1.json) ·
[`../artifacts/five_seed_classification_run1.json`](../artifacts/five_seed_classification_run1.json)

## Verdict: `PARTIALLY_STABLE` → `NOT_READY_FOR_KDA_VALIDATION`

The Phase-free bounded-slot **S** architecture forms the beyond-window retrieval circuit in **only
3 of 5 new holdout seeds** — **below** the pre-registered `≥ 4/5` stability bar. The optimistic
3-seed reading (seeds 0–2: all 3 formed) **did not replicate** on unseen seeds. When the circuit
forms it is real, large, and causally slot-dependent; but **formation is unreliable (~60%)**, so the
architecture is **not** stable enough to preserve for KDA validation yet.

## needle@d96 (holdout seeds 3–7; chance ≈ 0.02)

| seed | A | A+ | **S** | S−A+ | forming? |
|---|---|---|---|---|---|
| 3 | 0.017 | 0.017 | **0.000** | −0.017 | **no** |
| 4 | 0.000 | 0.000 | **0.283** | +0.283 | yes |
| 5 | 0.000 | 0.000 | **0.408** | +0.408 | yes |
| 6 | 0.017 | 0.017 | **0.075** | +0.058 | yes (marginal) |
| 7 | 0.000 | 0.000 | **0.042** | +0.042 | **no** |

**Forming: 3/5** (seeds 4, 5, 6). mean(S−A+) = **0.155**, median = **0.058**, S>A+ in **4/5**.

## Gate-by-gate (pre-registered)

| Gate | Result |
|---|---|
| Parameter match (\|S−A+\|/S ≤ 0.05%) | **PASS** (S 2000104 vs A+ 2000392) |
| **Primary stability (≥4/5 form; mean≥0.080; median≥0.050; win≥4/5)** | **FAIL** — only **3/5 form** (mean 0.155 ✓, median 0.058 ✓, win 4/5 ✓, but forming-count fails) |
| Causal (every forming seed: slots-off + rand-addr collapse) | **PASS** — seeds 4/5/6 all collapse (baseline→≤0.017) |
| PPL quality (mean S ≤ 1.20× A+; ≤2/5 exceed by 25%) | **PASS** — mean PPL S **117.8** < A+ **139.8** (S is *better*) |
| Parameter control (S beats A+, not just A) | **PASS** |
| Context distance (d16 no regression; ≥3 forming positive at d220) | **PASS** (d16 ok; 3 forming positive at d220) |
| Complexity (no N×N; bounded state ⟂ N) | **PASS** (per `neural_complexity_probe.json`) |

**The single failing gate is the primary stability gate (forming count 3/5 < 4/5).** Every other
gate passes — the effect, *when present*, is causal, structural, quality-preserving, and
distance-robust. The problem is **reliability of formation**, not the nature of the effect.

## Causal ablations (forming seeds)

| seed | baseline | slots_off | rand_addr | shuffle | write_gate_zero |
|---|---|---|---|---|---|
| 4 | 0.283 | 0.000 | 0.000 | 0.033 | 0.000 |
| 5 | 0.408 | 0.000 | 0.000 | 0.000 | 0.000 |
| 6 | 0.075 | 0.017 | 0.017 | 0.017 | 0.017 |

All three forming seeds collapse under slots-off and randomized-address — the gain is caused by the
learned addressable slot memory, not incidental capacity.

## Failure-mode analysis (seeds 3, 7 did not form)

Aggregate slot diagnostics **do not distinguish** forming from non-forming seeds — write-gate means
(e.g. non-forming S3 `[0.03, 0.77, 0.83, 0.87]` vs forming S4 `[0.10, 0.57, 0.72, 0.90]`) and slot
utilization entropy (~3.1–3.46 of ln 32 ≈ 3.47) are similar across all seeds. The slots are written
and used in every seed; the failure is that the **read/routing circuit does not consistently learn to
retrieve** under some initializations. This points to an **optimization / initialization
sensitivity**, not a dead-slot or gate-collapse pathology — the right next step is failure analysis
(e.g. init/LR/warmup sensitivity, longer training, or a formation-stabilizing objective), **not** KDA
composition or packaging.

## Relational (non-gate)

binding k=2 **EMERGING** by the pre-registered threshold (5/5 above chance, mean 0.070) — **but weak**
(only ~0.05 above chance 0.02); supersession / source / multi-hop **AT_CHANCE**. Treat binding as a
*hint*, not a validated capability; it needs its own study. No single-seed promotion.

## Supplementary (not the verdict)

- **Previously observed seeds 0–2 (frozen):** S 0.075 / 0.250 / 0.200 (3/3 formed).
- **Combined 0–7 (descriptive):** formed in **6/8** seeds (~75%) — consistent with "real but
  unstable." The formal verdict remains the holdout **3/5**.

## Maturity & readiness

- **Phase-free S slots:** `PROVISIONALLY_SUPPORTED` (3-seed) → **`PARTIALLY_STABLE` (5-seed holdout)**.
- **Single-fact retrieval:** real and causal *when it forms*, but **not reliably reproducible** at
  this scale/seed budget.
- **Readiness: `NOT_READY_FOR_KDA_VALIDATION`.** Per the stop condition, the next step is **failure
  analysis** of the ~40% non-forming seeds, **before** any KDA or packaging work.
