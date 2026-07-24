# BCVF Brochure — Evidence Audit

*An engineering verification of the quantitative claims in `AUTONOMOUS_ROBOTICS_VC_BRIEF.md` (v1.3) and
`AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` (v0.7) against the **current** codebase. Every "VERIFIED" number below
was re-measured by running the committed code in this session; documentation was not accepted as evidence.
No production code or evaluation artifact was modified; no historical result was altered.*

*Measurement environment: this repository at HEAD, Python 3 + NumPy 2.4.6, CPU-only. Absolute timing is
hardware-dependent — see the latency caveat.*

---

## 1. Executive Summary

The BCVF robotics brochure's **core safety-and-baseline claims reproduce exactly from the current code**,
while several **framing and status claims are superseded by the repository's own later work**, and a few
figures are **stale or environment-dependent**.

**Reproduced by direct measurement (strong):**
- The baseline shootout's false-attribution result — **BCVF 0.000 vs EKF 1.115 vs Majority 16.667 on
  constant-bias**, and **EKF misses the heavy-quadratic outlier (hit-rate 0.000 vs BCVF/Majority 1.000)** —
  matches the brochure to three decimals.
- The characterization grid — **1,560 cells (26 configs × 60 seeds), 0% FPR, 0% FNR, per-config Wilson 95%
  CI lower bound ≥ 0.90 (measured min 0.9398), 0 configs below floor** — matches the brochure's
  certification-grade claim.
- **Pure-NumPy, CPU-only** implementation — confirmed (no torch/CUDA/GPU dependency in the kernel).
- Test suite: **1,118 of 1,122 pass**; the 4 failures are host-speed-dependent timing benchmarks + one
  environment-driven SBOM snapshot — none in the kernel, grid, or shootout.

**Superseded by the repository's own later evidence (must not be published as-is):**
- The **"Lemma 1 invariance is a certifiable safety property"** framing. The implementation audit states it
  is a *noiseless idealization* that protects a **harmful** error class and therefore "must **not** be
  described as a safety property."
- The positioning of **BCVF as the primary / value-adding trust mechanism.** The incremental-value study
  demoted BCVF to an *optional, off-by-default* feature; standalone it "meets the `BCVF_NO_INCREMENTAL_VALUE`
  bar," and its only real edge (latency) is "fully recoverable" by a deterministic baseline.

**Stale or environment-dependent:**
- The **"8–19× faster per tick"** multiplier and the absolute per-tick microsecond figures are
  hardware-dependent; on this machine the measured spread is ~7× (vs Majority) to ~22× (vs EKF).
- The **"1320-cell"** grid figure is stale in the brochure body and safety-case docs — the current code
  produces **1,560** cells.

**Overall recommendation:** the brochure should be **re-scoped**, not merely re-numbered. The defensible
story is a *specific, measured advantage against EKF/Majority-Vote arbitrators on a synthetic
characterization grid* — **not** a general safety property and **not** primary-mechanism superiority over a
deterministic innovation/EWMA baseline (which the repo shows BCVF loses to).

---

## 2. Architecture Evolution Summary (Step 1)

There is no artifact literally named "BCVF 2.0"; the term maps to the repository's **Robotics V2 / PTR-V2 /
DRDC** redesign, which is documented but, by explicit decision, **not yet reflected in the brochure**
(`ROBOTICS_V2_MIGRATION_PLAN.md`: "No edit to the VC brief until a real-sensor pilot supports the
reposition").

**What changed.**
- **Action selection:** the BCVF forward/backward-consistency Lagrangian action scorer is **replaced** by a
  Deterministic Robotics Decision Controller (DRDC), a non-compensatory constrained selector
  (`ACP_MIGRATION_FROM_BCVF.md`: `formulas/bcvf.py` → *REMOVE from action path*).
- **Predictor reliability:** the primary detector becomes **PTR-V2** — innovation + EWMA/CUSUM + freshness
  with states TRUSTED/DEGRADED/SUSPECT/ABSTAIN. BCVF's 2nd-order disagreement math survives **only** as an
  optional, off-by-default latency-reducer.
- **Naming:** "BCVF stops being a product name and becomes a feature name" (`ROBOTICS_V2_MIGRATION_PLAN.md`).

**What is entirely new.** PTR-V2 detector, DRDC selector + `NO_SAFE_ACTION` path, and ActionGate-style
evidence/state binding, commit-time revalidation, and hash-chained trace.

**What is mathematically unchanged.** The Lemma 1 invariance itself (constant/linear-drift disagreement →
zero 2nd-order cost) is still true *as math* and still reproduces empirically (Section 3). What changed is
its **interpretation**: the implementation audit reclassifies it as *not* a safety property.

---

## 3. Verification Table — Every Brochure Metric (Steps 3 & 7)

*Status ∈ {VERIFIED, PARTIALLY VERIFIED, OUTDATED, NOT REPRODUCIBLE, SUPERSEDED}. Confidence is for the
audit's determination, not the vendor's claim.*

| # | Brochure claim | Measured / found this session | Status | Evidence (file · how) | Confidence |
|---|---|---|---|---|---|
| 1 | False-attribution, constant-bias: **BCVF 0.0 / EKF 1.1 / Majority 16.7** | BCVF **0.000** / EKF **1.115** / Majority **16.667** (N=30) | **VERIFIED** | `baselines/shootout.run_shootout` executed | High |
| 2 | False-attribution, linear-drift: **BCVF 0.000 / EKF 0.5 / Majority 4.1** | BCVF **0.000** / EKF **0.541** / Majority **4.083** | **VERIFIED** | shootout run | High |
| 3 | **"Zero false-attribution"** (as an unscoped headline) | BCVF **0.114 on `noise_floor`** (fires on benign high-variance) | **PARTIALLY VERIFIED** | shootout run | High |
| 4 | EKF misses heavy-quadratic **outlier: hit 0.0 vs BCVF/Majority 1.0** | EKF **0.000**, BCVF **1.000**, Majority **1.000** | **VERIFIED** | shootout attribution-hit | High |
| 5 | **8–19× faster per tick** than EKF / Majority | vs EKF **~18–22×**, vs Majority **~7–9×** (combined ~7–22×) on this CPU | **PARTIALLY VERIFIED** (hardware-dependent) | shootout per-tick µs | High (that it is env-dependent) |
| 6 | Absolute latency **≈3.7 µs (BCVF) / ≈70 µs (EKF) / ≈28 µs (Majority)** | BCVF **~7 µs** / EKF **~140 µs** / Majority **~55 µs** on this CPU | **NOT REPRODUCIBLE** (machine-specific) | shootout per-tick µs | High |
| 7 | Characterization grid **1,560 cells, 8 families × 26 configs** | `run_primary_grid()` → **1,560 cells, 26 configs × 60 seeds** | **VERIFIED** | `characterization/sweep` executed | High |
| 8 | Grid **1320 cells (22 configs × 60)** (brochure body + safety-case docs) | Current code produces **1,560**; "1320" is stale | **OUTDATED** | code returns 1560; docstrings/SOTIF docs still say 1320 | High |
| 9 | **0% FPR / 0% FNR** across the primary grid | FPR **0.0**, FNR **0.0** | **VERIFIED** | `summarize_grid` | High |
| 10 | Per-config **Wilson 95% CI lower bound ≥ 0.90**, min **≈0.940** | min CI lower bound **0.9398**, z=1.96, floor 0.90, **0** below floor | **VERIFIED** | `summarize_grid` | High |
| 11 | Adversarial-family pass rate | adversarial_pass_rate **1.0** (240 adversarial cells) | **VERIFIED** | `summarize_grid` | High |
| 12 | **Pure-NumPy, CPU, ms/tick**, no torch/ROS dependency | No torch/CUDA/GPU/JAX imports in kernel; NumPy present | **VERIFIED** (impl); "ms/tick" is env-dependent | `grep` of `core.py`/`bcvf_arbitrator.py`/`formulas/bcvf.py` | High |
| 13 | Lemma 1 invariance = **exactly zero** trust signal on constant/linear-drift | Empirically holds (constant/linear false-attr 0.000) | **VERIFIED (as math)** | shootout | High |
| 14 | Lemma 1 invariance framed as a **certifiable safety property** | Impl audit: "must **not** be described as a safety property" (protects a *harmful* class; noiseless idealization) | **SUPERSEDED** | `ROBOTICS_BCVF_IMPLEMENTATION_AUDIT.md` | High |
| 15 | BCVF is the **primary / value-adding** trust mechanism | Incremental-value study: standalone meets `BCVF_NO_INCREMENTAL_VALUE`; demoted to optional off-by-default; latency edge "fully recoverable" | **SUPERSEDED** | `ROBOTICS_BCVF_INCREMENTAL_VALUE_RESULTS.md` | High |
| 16 | Consumer-V2 chatter-immunity as a value prop | Measured **0.6%** reduction; promotion gate **FAIL**; "V2 not promoted" | **SUPERSEDED** | `v2_promotion_decision` doc | High |
| 17 | Pilot: `S3_map_error_accel`, **N=21, p=0.0072**, catastrophe 14.3% vs 23.8%, deviation 1.79 m vs 4.30 m | Not re-run this session (pilot runner is heavier; requires scenario harness) | **NOT VERIFIED (not re-run)** | pilot runner exists (`pilot/runner.py`) | n/a — needs rerun |
| 18 | Test suite (brochure states **1117**, also 751, also 221) | **1,122 collected; 1,118 passed, 4 failed.** The 4 are host-speed-dependent timing benchmarks (`test_batch_timing_under_50ms`, 2× `test_planner_timing_*`) + one SBOM snapshot mismatch (env numpy version) — none in the kernel/grid/shootout | **PARTIALLY VERIFIED** (count ≈ 1117; brochure's 751/221 are stale/inconsistent) | full `pytest` run | High |
| 19 | LLM-transfer null: **AUC ≈ 0.48–0.53** (honest null, not a product) | Not re-run; brochure already presents as a null | **NOT VERIFIED (not re-run)** — honest-null claim is safe to keep | brochure caveat | n/a |

---

## 4. Newly Discovered BCVF 2.0 Metrics (Step 4)

Measurements present in the current code/repo that are **stronger or more honest** than some brochure
figures and could replace them:

- **Grid is larger than the brochure body states** — the *current* certification grid is **1,560 cells (26
  configs × 60 seeds)** with **0% FPR / 0% FNR** and **min Wilson-95% CI lower bound 0.9398** (measured).
  This is the number to cite; drop "1,320."
- **Speedup vs EKF is larger than advertised on modern CPUs** — measured **~18–22× vs EKF** (brochure said
  8–19× combined). But it is **hardware-dependent** and should be published as a *range measured on stated
  hardware*, never as a fixed multiplier.
- **Deterministic-baseline comparison (the honest headline)** — the incremental-value study's numbers
  (deterministic baseline recall 1.00 / FA 0.04 / common-mode 0.00 vs BCVF standalone 0.90 / 0.67 / 0.86;
  BCVF wins **only** detection delay) are the most diligence-relevant figures in the repo and are currently
  **absent from the brochure**. Publishing them (as the reason BCVF is an *optional latency feature*) would
  be more defensible than the current primary-mechanism framing.

---

## 5. What Changed — Old vs Current (Step 5)

| Metric | Old brochure | Current repository | Status | Recommendation |
|---|---|---|---|---|
| Characterization grid size | 1,320 cells (also 1,560 in v0.7 footer) | **1,560 cells (26×60)** measured | Update | Standardize on 1,560; remove 1,320 everywhere |
| FPR / FNR | 0% / 0% | **0.0 / 0.0** measured | Keep | Keep (with "synthetic grid" scope) |
| Wilson CI floor / min | ≥0.90 / ≈0.940 | **0.90 / 0.9398** measured | Keep | Keep |
| False-attr (constant-bias) | 0.0 / 1.1 / 16.7 | **0.000 / 1.115 / 16.667** | Keep | Keep (scoped to Lemma-1-invariant families) |
| Speedup | 8–19× | **~7–22× (env-dependent)** | Re-scope | Publish as "single-digit to ~20×, on stated hardware" |
| Absolute latency | ≈3.7 µs BCVF | **~7 µs on this CPU** | Remove/qualify | Do not publish a fixed µs figure |
| Lemma 1 = safety property | Yes | **No** (audit reclassifies) | Remove framing | Describe as an invariance, not a safety guarantee |
| BCVF = primary mechanism | Yes | **Optional feature** (demoted) | Re-scope | Reposition as optional latency feature |
| Consumer-V2 chatter value | Implied benefit | **0.6%, gate FAIL** | Remove | Drop as a value prop |
| Test count | 1117 / 751 / 221 | **1,122 collected** | Update | Use one current, measured number |

---

## 6. Evidence-Readiness Categorization (Step 6)

- **Production-grade evidence:** *none.* Every number is internal CI on synthetic / realistic-noise
  predictors. The brochure already says this ("no production deployment yet"; "every number is internal").
- **Internal measured evidence (reproduced this session):** false-attribution shootout (#1–4), grid FPR/FNR
  + Wilson CI + cell count (#7,9,10,11), CPU/NumPy implementation (#12).
- **Mathematical proof:** Lemma 1 invariance (true as math; empirically reproduced) — but *not* a safety
  property.
- **Simulation only:** all shootout / grid / pilot results (synthetic SE(2), no real sensor).
- **Projection / roadmap:** hardware-accelerated kernel; 50/100 Hz rate feasibility; adversarial-grid
  expansions beyond what the primary grid covers.
- **No supporting evidence (in current repo):** any real-sensor, third-party, or production-latency claim.

---

## 7. Final Recommendation (Step 7)

### ✅ Safe to publish today (measured, current, correctly scoped)
- Baseline-shootout false-attribution vs **EKF and Majority-Vote arbitrators** on the synthetic grid:
  **BCVF 0.000 vs EKF 1.115 vs Majority 16.667 (constant-bias); EKF misses the outlier (0.000 vs 1.000).**
  *Scope it to Lemma-1-invariant disagreement families.*
- Characterization grid: **1,560 cells, 0% FPR, 0% FNR, per-config Wilson-95% CI ≥ 0.90 (min 0.9398)** — on
  a **synthetic** grid.
- **Pure-NumPy, CPU-only** reference implementation.
- The Lemma 1 invariance **as a mathematical property** (zero 2nd-order cost on constant/linear drift).
- All of the above **only** alongside the existing honest-scope caveats ("synthetic; internal CI; no
  production deployment").

### ♻️ Needs re-running before publishing (probably true, not re-measured here)
- Pilot statistics (**N=21, p=0.0072/0.0312**, catastrophe and lateral-deviation figures) — re-run
  `pilot/runner.py` and reconcile the two different p-values the two briefs attach to the same scenario.
- **Speedup multiplier and any latency figure** — re-run on the *target deployment hardware* and publish as
  a measured range on stated hardware, never a fixed number.
- **Test-suite pass count** — measured this session: **1,122 collected, 1,118 passed, 4 failed** (the 4 are
  host-speed-dependent timing benchmarks + one env-driven SBOM snapshot; the characterization, baseline, and
  core suites are fully green: 124 + 15 passed). If publishing a test number, use **"1,118 passing (4
  host/env-dependent perf/snapshot tests excluded)"** on stated hardware, and drop the inconsistent
  751/221 figures.

### ❌ Remove (cannot be defended)
- The word **"safety property"** applied to the Lemma 1 invariance (repo audit forbids it).
- Any claim that **BCVF is the primary trust mechanism or adds standalone incremental value** — the repo
  demoted it to an optional, off-by-default feature and shows a deterministic baseline matches or beats it
  on every metric except detection delay.
- The **Consumer-V2 chatter-reduction** value proposition (measured 0.6%, promotion gate failed).
- The **"1,320-cell"** figure (superseded by 1,560) and any **fixed absolute-latency** number.
- The unscoped phrase **"zero false attribution"** without the "on Lemma-1-invariant disagreement"
  qualifier (BCVF is 0.114 on the benign `noise_floor` family).

---

## Evidence Discipline Note

Every "VERIFIED" figure was produced by executing committed code in this session (`run_shootout`,
`run_primary_grid` + `summarize_grid`) and reading the result, not by trusting documentation. Where a number
was not re-run (pilot, LLM-null), it is marked **NOT VERIFIED (not re-run)** rather than assumed. Where the
repository's own later work contradicts a brochure framing, the brochure claim is marked **SUPERSEDED** with
the source. Absolute timing is reported as hardware-dependent. When in doubt, this audit recommends removing
a claim rather than preserving it.
