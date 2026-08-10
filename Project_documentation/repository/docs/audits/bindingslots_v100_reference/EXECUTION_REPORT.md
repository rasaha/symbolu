# V100 always-verify reference-backend characterization — execution report

**Primary verdict: `ALWAYS_VERIFY_RELIABILITY_VERIFIED_OPERATIONAL_COST_UNRESOLVED`**
**Always co-emitted: `KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE` · `BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`KDA_VALIDATION_BLOCKED`.** The forbidden verdict `ALWAYS_VERIFY_OPERATIONALLY_QUALIFIED` was **not**
emitted (no deployment ceiling approved this phase).

System-level reliability characterization of the SQLite reference backend under always-verify. **Not a
neural-routing intervention.** BindingSlots training/architecture/routing/weights were not modified; the
model was used for inference only (verified: params byte-identical before/after eval, zero eval
optimizer steps). Does **not** solve neural routing; KDA remains blocked.

## Cohort & reproduction
Frozen seeds **28–32**, 120 examples each, **600 queries** — identical to PR #1346. Each seed's frozen
B0 state (== `run_h2`, byte-identical) was reconstructed deterministically and **accepted only on
trajectory equality (`needle_by_dist` + `ppl`) vs the committed B0 evidence**; all five matched. M0 was
**byte-identical to the merged fallback baseline** on every seed.

## Arms (approved scope only; V75/V50/K1 not run)

| seed | M0 (neural) | T0 (table) | F0 (frozen trigger) | V100 (always-verify) | V100 reads |
|---|---|---|---|---|---|
| 28 | 0.992 | 1.000 | — | 1.000 | 120 |
| 29 | 0.000 | 1.000 | — | 1.000 | 120 |
| 30 | 0.000 | 1.000 | — | 1.000 | 120 |
| 31 | 0.017 | 1.000 | — | 1.000 | 120 |
| 32 | 0.033 | 1.000 | — | 1.000 | 120 |
| **agg** | **0.208** | **1.000** | **0.842** | **1.000** | **600 (= n)** |

## V100 reliability categories (each of 600 queries in exactly one)
`verified_agreement_correct` **125** · `verified_correction_correct` **475** · `verified_return_incorrect`
**0** · all `abstained_*` **0** · `system_failure` **0**. Answer availability **1.000**; abstention
**0.000**; provenance completeness **1.000**; incorrect verified returns **0**; disagreements **475**,
all corrected (**475** corrections, **0** incorrect corrections); **exactly one table read per query**
(600 total).

At 100% legitimate write coverage V100 is **reliability-equivalent to T0** (both 1.000) and provides **no
table-read reduction** — it reads the table on every query and adds neural-inference cost on top. It is
**not** a table-avoiding fast path or a latency optimization.

## F0 comparator (frozen PR #1346 trigger, no recalibration)
Reproduces the merged fallback result exactly: accuracy **0.842**, failure-detection **recall 0.80**,
**precision 0.964**, **95 confidently-wrong reads missed**. Historical comparator only; not selectable.
Confirms again that neural confidence ≠ retrieval correctness.

## Hard gates — 17/17 pass
Accuracy within 0.1 pp of T0 (0.0) · incorrect verified = 0 · incorrect corrections = 0 · 100% of
disagreements detected (475/475) · every valid-record disagreement corrected · provenance 100% ·
cross-session leakage 0 · cross-tenant leakage 0 · stale/expired/deleted/incorrect-version returns 0 ·
table-unavailable abstains · injected read/write failures fail closed · no model-state change (params
unchanged + 0 eval optimizer steps) · deterministic replay succeeds · cleanup leaves 0 live session
rows · exactly one read per V100 query. All lifecycle/isolation scenarios pass (`isolation_tests.json`,
`integrity_report.json`).

## End-to-end latency (characterization only; non-deterministic; no ceiling approved)
Full request paths incl. serialization (per-seed p50):

| path | p50 | p95 |
|---|---|---|
| **V100 query** (neural + lookup + compare + classify + provenance + serialize) | **≈15.9 ms** | ≈18–22 ms |
| **T0 table-only** (lookup + validate + provenance + serialize) | **≈0.023 ms** | ≈0.03–0.045 ms |
| **write-path** (receipt + validate + serialize + commit + provenance) | **≈0.012 ms** | — |

The V100 path is dominated by neural inference (~15.8 ms of ~15.9 ms) and is **~680× the T0 path** —
concrete confirmation that always-verify is not a latency advantage, and that the isolated ~0.006 ms
table read must not stand in for end-to-end cost. Because no deployment-specific operational ceiling is
approved, these are recorded as characterization metrics only and the qualified verdict is not emitted.

## Interpretation (conservative)
Supports **only**: the external ephemeral table can verify or correct frozen neural retrievals with
deterministic provenance when the relevant record has been written, remains valid, and the reference
table is available. Does **not** support: routing solved; neural retrieval independently reliable;
verification avoids a table read; V100 faster than T0; V100 production-ready; the SQLite reference ==
enterprise deployment latency; external memory improving neural learning; KDA readiness. See
`LIMITATIONS.md`.
