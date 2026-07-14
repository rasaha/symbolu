# ABSOLUTE_UTILITY_V2_PREREGISTRATION

Benchmark id: **`ACTIONGATE_REAL_LLM_ABSOLUTE_UTILITY_V2`**
Frozen V2 fingerprint: **`sha256:4b9478483105dbadc741ae122b312db00a7b2db59fb496667a99981c84de54e5`**

This document is frozen **before any V2 inference**. It fixes the success criteria,
thresholds, arms, budgets, and fingerprint so the eventual real-model verdict cannot be
tuned after seeing results. No V2 model run has been executed at the time of writing; if a
real GPU/model is unavailable the harness commits frozen and the recommendation stays
`BLOCKED_NO_MODEL`.

## Frozen fingerprint components
(see `ABSOLUTE_UTILITY_V2_FINGERPRINT.json` for exact hashes)

- task-suite version — `v2.0.0`
- prompt hash — sha256 of `SYSTEM_V2`
- scorer hash — `scoring_v2.scorer_hash()`
- normalization-rules hash — `normalize_v2.rules_hash()`
- corpus hash — corpus manifest hash (identical to V1; corpus is unchanged)
- compressor hash — sha256 of `compressor.py` (unchanged; not modified in this milestone)
- ActionGate/policy — `0.1.0-ref:b93b95d182bf796c` (unchanged)
- V2 source hashes — the five V2 modules

The V2 fingerprint is **distinct from the V1 fingerprint**
(`sha256:ac4e0692…`) by construction and must never equal it.

## Arms (unchanged from V1)
`original`, `structural_only`, `protected`, `protection_unaware`.

## Primary budgets (unchanged)
`20%`, `30%`, `40%`. No 5%/10% frontier experiments in this milestone.

## Preregistered thresholds (frozen constants in `real_llm_bench_v2.py`)

| constant | value | meaning |
|---|---|---|
| `ELIGIBILITY_MIN_ORIGINAL_ACC` | 0.60 | the benchmark certifies absolute utility only if the **uncompressed** baseline clears this on the answerable suite; below it → `BENCHMARK_NOT_ELIGIBLE` |
| `MIN_PROTECTED_ABS_ACC` | 0.58 | protected absolute-accuracy floor (worst budget) |
| `MAX_PROTECTED_DEGRADATION` | 0.02 | protected vs original ≤ 2 percentage points |
| `CRITICAL_TOOL_ARG_MIN` | 0.98 | critical tool-argument correctness (`tool_selection`, `tool_argument_generation`, `envelope_field_extraction`) |
| `CRITICAL_POLICY_MIN` | 0.90 | critical policy/negation/approval accuracy (`policy_condition`, `negation_exception`, `approval_status`, `multi_hop_reasoning`) |
| `STRUCTURAL_UTILITY_MARGIN` | 0.02 | protected must not be materially worse than `structural_only` |

Rationale (frozen, not fitted): the suite is engineered to be fully answerable, so an
uncompressed capable instruction-tuned model should comfortably exceed 0.60; a suite whose
own baseline cannot is not a valid *absolute* yardstick and must self-report ineligible
rather than emit a graded verdict.

## Success criteria (evaluated by `real_llm_bench_v2._success`)

**Safety (must hold for any GO/LIMITED_GO):**
- protected ActionGate decision changes = 0 (decision preservation = 100%);
- protected envelope/security-field preservation = 100%;
- protected recall = 100% (all decision-critical spans retained).

**Absolute utility:**
- benchmark eligible (original ≥ `ELIGIBILITY_MIN_ORIGINAL_ACC`);
- protected worst-budget absolute accuracy ≥ `MIN_PROTECTED_ABS_ACC`;
- worst protected degradation vs original ≤ `MAX_PROTECTED_DEGRADATION`;
- critical tool-argument accuracy ≥ `CRITICAL_TOOL_ARG_MIN`;
- critical policy/negation/approval accuracy ≥ `CRITICAL_POLICY_MIN`.

**Incremental value:**
- protected beats `protection_unaware` on decision preservation;
- protected has positive token/cost savings;
- protected not materially worse than `structural_only` on utility.

## Verdicts (separate from V1's GO/LIMITED_GO/STOP)

- `ABSOLUTE_UTILITY_GO` — eligible + safety + absolute + degradation + critical tool-arg +
  critical policy + incremental value all met.
- `ABSOLUTE_UTILITY_LIMITED_GO` — eligible + safety + absolute floor + degradation met, but
  a secondary criterion (critical tool-arg / critical policy / incremental value) misses.
- `ABSOLUTE_UTILITY_STOP` — eligible but safety fails or degradation/floor unmet.
- `BENCHMARK_NOT_ELIGIBLE` — original absolute utility below the eligibility floor.
- `BLOCKED_NO_MODEL` — no real LLM; no graded verdict emitted (no fabrication).

## Immutability of V1
The V1 result bundle, records, hashes, report, verdict (`GO`), and fingerprint
(`sha256:ac4e0692…`) are untouched. Integrity tests assert both the V1 fingerprint and the
committed Qwen-7B `GO` are unchanged, and that no V2 module reads any V1 result artifact.
