# Preregistration — BindingSlots External Ephemeral Memory Fallback Evaluation

**System-reliability evaluation, NOT a neural BindingSlots repair. BindingSlots training,
architecture, routing, slot tensors, coefficients and weights are NOT modified. The phase always
emits `BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` and `KDA_VALIDATION_BLOCKED`, and never claims to solve
neural routing.** Machine-readable mirror: `preregistration.json`.

## Question
Can a session-scoped external temporary-memory table recover BindingSlots retrieval failures with
deterministic identity, isolation, provenance and bounded overhead, while BindingSlots remains the
normal fast path?

## Prerequisite (verified — `prerequisite_audit.json`)
PR #1345 merged (`6e4ba3e8`); verdict `NO_BINDINGSLOTS_INTERVENTION_SELECTED`/`KDA_VALIDATION_BLOCKED`;
conclusions from #1344/#1345 confirmed; inherited tests+verifier pass; tree clean.

## Lookup-key legitimacy (`lookup_key_proof.json`)
Key = entity id token present in the query. Stored value = the observed fact value (written at write
time), not a hidden label, correct slot index, or oracle. No benchmark redesign.

## Table (`table_schema.json`, `lifecycle_policy.json`)
SQLite reference backend; explicit fact records only; PK `(session_id, tenant_id, memory_key, version)`;
TTL 3600 s; auto-versioning; soft deletion; per-episode sessions; never stores tensors/gradients/labels.

## Write / query semantics
Write: ordinary BindingSlots write unchanged **plus** an independent explicit fact-record write. Query:
BindingSlots inference → frozen trigger from runtime signals **only** → if false return BindingSlots,
if true deterministic table lookup with provenance. The table is never consulted before the trigger.

## Trigger (`trigger_thresholds.json`, frozen from calibration)
`fallback = low_top1_prob OR low_top1_margin OR high_entropy`, thresholds grid-searched on the
calibration cohort (R0 s24 clean, H2 s23 collapsed — merged evidence) only, recorded with a
calibration hash; never swept on the final cohort.

## Arms
M0 (BindingSlots only), T0 (table only — reliability ceiling, not a neural result), F1 (confidence-
triggered hybrid), V0 (always-verify diagnostic; non-selectable).

## Final cohort
Fresh B0 seeds 28–32 from PR #1345; no checkpoints → B0 (== frozen `run_h2`) reproduced
deterministically and checked against committed B0 evidence; inference-only; no seed replacement.

## Frozen success gates (F1, all required — `fallback_gates.py`)
(1) F1 within 1 pp of T0; (2) ≥90% of M0 failures rescued; (3) incorrect fallback ≤1%; (4) zero
cross-session leakage; (5) zero cross-tenant leakage; (6) expired/deleted never returned; (7)
provenance on every fallback; (8) BindingSlots byte-identical when fallback disabled; (9) no
weight/gradient change; (10) p95 latency ≤ 0.050 s. Gates frozen here, not after results.

## Verdict + always co-emit `BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` + `KDA_VALIDATION_BLOCKED`;
if F1 passes, also `INDEPENDENT_SYSTEM_CONFIRMATION_REQUIRED`. Interpretation supports only a hybrid
reliability layer — not solved routing, reliable neural memory, KDA readiness, or production/DB readiness.
