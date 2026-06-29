# experiments/a_prime — A1.4 projection pipeline (engineering only)

> **Scope — ENGINEERING / PIPELINE VALIDATION ONLY.** This directory implements and validates
> the deterministic A1.4 projection `P` (per-stimulus ratings → per-phoneme `E′`, plus the
> section-4 aggregation) defined in `MILESTONE_A_PRIME_PREREGISTRATION.md` and
> `MILESTONE_A_PRIME_PREREGISTRATION_AMENDMENT_1.md`.
> It produces **no A′ result**: no semantic `Y`, no probe, no baseline, no conditional-MI
> estimator, **no inference, no PASS/FAIL/⊥**, and no downstream Milestone B–G work.
> A′ itself remains **NOT EXECUTED** — see `MILESTONE_A_PRIME_EXECUTION_STATUS.md` (no
> construct-aligned, mutually-available `E`×`Y` pairing exists with current data). This is the
> "keep the pipeline warm" de-risk option, nothing more. **structure, not validated meaning.**

## Contents
- `projection.py` — the deterministic, parameter-free projection:
  `build_incidence` (phoneme **counts**; order discarded — additive branch),
  `project_per_phoneme` (`e = X⁺ r`, Moore–Penrose; intercept solved then discarded),
  `aggregate_to_items` (section-4 {mean, sum, min, max}; uncovered phonemes → NaN, no imputation).
- `test_projection.py` — pipeline-validation tests on **synthetic** data (no third-party
  dataset required). Run as a plain script (no pytest):
  ```
  python3 experiments/a_prime/test_projection.py
  ```

## What is validated (mechanics only)
- **Determinism / bit-stability** — identical inputs → identical outputs (no randomness, no
  tuned parameters).
- **Exact recovery** of planted per-phoneme values when the additive model is identifiable
  (varied-length stimuli + singletons → full column rank).
- **Rank-deficient handling** — for constant-length stimuli the intercept is collinear with the
  count total; `pinv` returns the unique **minimum-norm** least-squares solution, deterministically,
  with residual orthogonal to the column space.
- **Aggregation correctness** — mean/sum/min/max and the uncovered→NaN rule.

All synthetic checks pass.

## Local schema-ingestion check (NOT committed)
The pipeline was additionally run **locally** against the McCormick et al. (2015) SHAPE
pseudoword file to confirm it ingests the real schema. The data is **not** redistributed here
(no reuse license was supplied) and **no rating or `E′` values are recorded**. Pipeline
diagnostics only:

| diagnostic | value |
|---|---|
| stimuli ingested | 537 |
| distinct phonemes | 22 |
| design matrix `X` | 537 × 23 (incl. intercept) |
| rank(`X`) | 21 |
| deterministic re-run | bit-identical |
| residual ⟂ column space | yes |

**Engineering note (identifiability):** on this real dataset `rank(X)=21 < 23`, i.e. the
per-phoneme estimate lives modulo a 2-dimensional null space (constant-length CVCV ⇒ intercept
collinearity, plus at least one phoneme co-occurrence collinearity). The *fitted reconstruction*
is unique; individual per-phoneme `E′` values are the **minimum-norm** representatives and are
not uniquely identified. This is a property to weigh in any future identifiability analysis — it
is **not** acted on here (no A′ run).

## Hard boundaries
- No semantic `Y`; no probe/baseline/CMI; no inference; no PASS/FAIL/⊥; no B–G work.
- No third-party data, and no `E′` values, are committed to this repository.
- Stage A (`symbolu_neural/structural_v1/`) is untouched.
