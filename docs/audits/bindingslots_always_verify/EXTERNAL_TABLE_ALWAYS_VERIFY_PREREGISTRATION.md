# PHASE-FREE EXTERNAL TABLE COVERAGE AND ALWAYS-VERIFY OPERATIONAL EVALUATION

**DRAFT PREREGISTRATION — for approval. Nothing here is executed.** No new training, no model
evaluation, no optimizer steps, no final-cohort inference, no coverage experiments, no threshold
sweeps, no K1. This document corrects the scientific and architectural problems in the earlier
external-fallback proposal. It **always** preserves, in any later experiment,
`BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` and `KDA_VALIDATION_BLOCKED`.

## 5. Frozen conclusions (preserved without reinterpretation)

- The external ephemeral table was reliable under the evaluated conditions (T0 = 1.000; zero
  cross-session/cross-tenant leakage; correct TTL/deletion; complete provenance; ~0.006 ms isolated
  table reads; no model change).
- The confidence-only hybrid trigger **failed** its frozen gates (F1 0.842 vs T0 1.000; failure-
  detection recall 0.80; 95 confidently-wrong reads missed).
- Neural confidence is **not** equivalent to retrieval correctness; confidently-wrong BindingSlots
  reads exist.
- BindingSlots neural routing **remains unresolved**; KDA validation **remains blocked**; no neural-
  routing intervention has been selected.

## 6. Correct scientific framing

Under the current benchmark **every relevant fact was written to the table**, so **V100 always-verify
is expected to be reliability-equivalent to T0 table-only**. V100 must **not** be described as a
table-avoiding fast path, a latency optimization, a selective fallback, proof that BindingSlots
routing works, or proof of verification without a table read. **V100 reads the table on every query.**
Its distinct purpose is to evaluate end-to-end verification behavior, disagreement/correction
semantics, provenance, write-coverage dependence, complete request-path latency, missing-record
behavior, table-unavailability behavior, lifecycle/isolation integrity, and operational cost relative
to M0 and T0.

## 7. Proposed arms

- **M0 — frozen neural-only baseline.** Frozen BindingSlots inference; no table read; no model change;
  no training; no new confidence/routing logic. Reuses the reproduced frozen B0 states (seeds 28–32),
  exactly as in the merged fallback phase; deterministic reproduction must match committed B0.
- **T0 — table-only ceiling.** Deterministic table lookup for every query; return only a valid current
  record; **abstain** when none exists.
- **F0 — frozen confidence-trigger comparator.** Reuse the **exact** trigger + thresholds from PR
  #1346 (`prob_min=0.1, margin_min=0.05, entropy_max=1.0`, calibration hash `7421fbfb…`). **No
  recalibration, no retuning.** Historical comparator only; not selectable.
- **V100 — always verify, 100% write coverage.** For every query: (1) run the frozen neural path; (2)
  read the table; (3) compare neural result to the current record; (4) agree → `verified-agreement`;
  (5) disagree → return the table value as `verified-correction`; (6) no valid record → apply the
  preregistered missing-record policy; (7) attach provenance + version to every verified return.
  **Explicitly: at 100% coverage V100 provides no table-read reduction relative to T0.**
- **K1 — OMITTED.** The key-consistency feasibility analysis returns
  `KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE` (no legitimate non-oracle, non-circular, table-avoiding
  identity signal exists for content-addressed slots; the only valid check reduces to V100). K1 is
  therefore not an executable arm.

## 8. Controlled write-coverage stress (optional arms V75 / V50)

Partial-coverage arms at ≈75% and ≈50% **legitimate** write coverage. Coverage omissions must be
selected **deterministically, at write time, before final evaluation**, and **independently** of
future queries, neural confidence, answer correctness, evaluator labels, and example difficulty.
Proposed mechanism: a **frozen hash-based inclusion rule** over legitimate write-event identifiers,
e.g. `include_write(event_id) := (sha256(event_id) mod 100) < COVERAGE_PCT`, with `COVERAGE_PCT ∈
{100,75,50}` frozen before evaluation and mechanically reproducible. **Records are never removed based
on observed model failures.**

## 9. Missing-record policies (for partial coverage)

- **Policy A — fail-closed abstention.** Return no answer; mark `unverified-no-record`; preserve
  correctness among returned verified answers; accept reduced availability.
- **Policy B — explicitly unverified neural return.** Return the neural result with an `unverified`
  status; never classify it as verified; measure its accuracy **separately**; never merge verified and
  unverified accuracy into one headline.

**Decision to resolve before execution:** whether to compare both policies or select one.
`APPROVAL_REQUIRED_BEFORE_EXECUTION`. A silent unverified-as-verified return is prohibited; fail closed
whenever verification status cannot be established.

## 10. Key-consistency feasibility gate

See `KEY_CONSISTENCY_FEASIBILITY_ANALYSIS.md`. Verdict `KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE`; K1 is
omitted. No slot-index→entity sidecar may be built to enable K1. Any consistency check that requires a
per-query table read is classified as always-verify, not a selective hybrid.

## 11. Required measurements (full request path)

- **Reliability/availability:** total accuracy; verified-answer accuracy; unverified-neural accuracy;
  incorrect-return rate; abstention rate; answer-availability rate; unresolved-failure rate; correction
  count; disagreement count; provenance completeness. Keep these categories **separate**: verified
  correct, verified agreement, verified correction, unverified-neural correct, unverified-neural
  incorrect, abstained, unavailable-due-to-system-failure.
- **Detection/correction:** confidently-wrong reads (total / detected / missed); neural–table
  disagreements; corrections performed / incorrect / unnecessary; F0 precision & recall; V100 correction
  recall.
- **Coverage:** intended vs realized write-coverage %; records written / omitted by the frozen rule;
  queries with / without valid records; accuracy conditional on coverage; availability conditional on
  coverage.
- **Storage/table ops:** writes/session; reads/query; bytes written; peak table size; write latency;
  read latency; cleanup latency; session-completion cleanup; restart persistence (if in the backend
  contract).
- **End-to-end performance:** p50/p95/p99 **end-to-end request latency**; neural-inference latency;
  verification-comparison overhead; table-read latency; (de)serialization overhead; provenance-
  construction overhead; overhead relative to M0 and to T0. **The 0.006 ms isolated table-read figure
  must not substitute for end-to-end latency.**
- **Integrity:** cross-session / cross-tenant leakage; stale-version / expired / deleted returns;
  incorrect-version selection; missing provenance; table-unavailable, write-failure, malformed-record
  behavior; concurrent-session; process-restart; cleanup-after-completion.

## 12. Required lifecycle scenarios

Successful write/read; missing write; partial write coverage; duplicate write; overwrite; version
increment; stale version; current version; expired; deleted; wrong session; wrong tenant; concurrent
sessions; table unavailable; table read timeout; table write failure; malformed metadata; incomplete
provenance; process restart; cleanup after completion. **Fail closed whenever verification status
cannot be established.**

## 13. Proposed success criteria (frozen thresholds proposed for approval)

**V100 reliability gates (proposed frozen):** accuracy within **0.1 pp** of T0; **zero** incorrect
verified returns; **100%** detection of neural/table disagreements; **100%** provenance completeness;
zero cross-session/cross-tenant leakage; zero stale/expired/deleted returns; table-unavailable →
abstain; no model-state change; no optimizer steps; deterministic replay succeeds.

**Operational gates (proposed, values `APPROVAL_REQUIRED_BEFORE_EXECUTION`):** p95 end-to-end latency
`APPROVAL_REQUIRED_BEFORE_EXECUTION`; p99 end-to-end latency `APPROVAL_REQUIRED_BEFORE_EXECUTION`; max
verification overhead vs T0 `APPROVAL_REQUIRED_BEFORE_EXECUTION`; max storage/session
`APPROVAL_REQUIRED_BEFORE_EXECUTION`; max cleanup latency `APPROVAL_REQUIRED_BEFORE_EXECUTION`;
acceptable write-failure rate `APPROVAL_REQUIRED_BEFORE_EXECUTION`. No commercially meaningful ceiling
is invented without justification.

**Partial-coverage gates:** separate reliability from availability. Fail-closed: verified incorrect-
return rate must remain **zero**; lower coverage may raise abstention; abstention is **not** an
incorrect answer. Unverified-return: report verified and unverified outcomes separately; do not claim
table-level reliability for unverified outputs; freeze an acceptable unverified-error ceiling before
execution (`APPROVAL_REQUIRED_BEFORE_EXECUTION`).

## 14. Interpretation boundaries

A successful V100 result supports **only**: "the external ephemeral table can verify or correct neural
retrievals with deterministic provenance when the relevant record has been written, remains valid, and
the table is available." It does **not** support: routing solved; the neural path independently
reliable; verification avoids a table read; always-verify faster than table-only; external memory
improving neural learning; the table as a production system of record; production readiness; KDA
readiness. Partial-coverage results must keep correctness, verified correctness, unverified accuracy,
availability, and abstention **separate** — never one headline metric.

## 15. Restrictions

Prohibited: confidence-threshold tuning; neural training; optimizer steps; routing-objective changes;
slot-count changes; address-temperature changes; sparsity changes; new read heads; architecture
changes; base-recipe redesign; Phase; KDA; MLA; external production databases; production customer
data; answer-label or evaluator-slot leakage.

## 16. Proposed verdict vocabulary (each maps mechanically to frozen gates)

`ALWAYS_VERIFY_OPERATIONALLY_QUALIFIED` · `ALWAYS_VERIFY_RELIABLE_OPERATIONAL_COST_UNRESOLVED` ·
`ALWAYS_VERIFY_RELIABLE_OPERATIONAL_GATE_FAILED` · `PARTIAL_COVERAGE_FAIL_CLOSED_QUALIFIED` ·
`PARTIAL_COVERAGE_RELIABILITY_AVAILABILITY_TRADEOFF` · `EXTERNAL_TABLE_COVERAGE_INSUFFICIENT` ·
`KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE` · `KEY_CONSISTENCY_FEASIBILITY_INCONCLUSIVE` ·
`EXTERNAL_VERIFICATION_PROTOCOL_VIOLATED` · `EXTERNAL_VERIFICATION_INTEGRITY_FAILED` ·
`EXTERNAL_VERIFICATION_RESOURCE_BLOCKED`. **Always also emit** `BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`
and `KDA_VALIDATION_BLOCKED`. Proposed mapping: all V100 reliability gates pass **and** all
(to-be-approved) operational gates pass → `ALWAYS_VERIFY_OPERATIONALLY_QUALIFIED`; reliability passes but
operational thresholds are unset → `…_OPERATIONAL_COST_UNRESOLVED`; reliability passes but an approved
operational gate fails → `…_OPERATIONAL_GATE_FAILED`; partial-coverage fail-closed keeps zero verified-
incorrect → `PARTIAL_COVERAGE_FAIL_CLOSED_QUALIFIED`; else the tradeoff/insufficient/violation verdicts.

## 17. Unresolved decisions requiring approval before execution

1. **Operational latency/storage/cleanup/write-failure ceilings** — all `APPROVAL_REQUIRED_BEFORE_EXECUTION`; no defensible numeric ceiling exists without a real end-to-end latency measurement of the target backend.
2. **Missing-record policy** — compare Policy A and Policy B, or select one before execution?
3. **Partial-coverage arms** — run V75/V50, or V100 only in the first pass?
4. **End-to-end latency methodology** — which backend/serialization/provenance path counts as "end-to-end" (the SQLite reference vs a target deployment)?
5. **Unverified-error ceiling** (Policy B, partial coverage) — numeric value.

Until these are approved, no execution begins. The draft proposes structure and gates only.
