# BindingSlots external ephemeral fallback — execution report

**Primary verdict: `EXTERNAL_TABLE_RELIABILITY_VERIFIED_HYBRID_TRIGGER_FAILED`**
**Always co-emitted: `BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.**

System-reliability evaluation only. BindingSlots training/architecture/routing/weights were not
modified; the model was used for inference only (no optimizer step, no weight change — verified). This
does **not** claim to solve neural routing, and KDA cannot be unblocked by this phase.

## Setup

- Legitimate lookup key = the entity id present in the query; stored value = the observed fact written
  at write time (not a label/oracle) — `lookup_key_proof.json`.
- Trigger `low_top1_prob OR low_top1_margin OR high_entropy`, thresholds **frozen from the calibration
  cohort only** (R0 s24 clean + H2 s23 collapsed): `prob_min=0.1, margin_min=0.05, entropy_max=1.0`
  (calibration recall 1.0, fp 0.14; hash `7421fbfb…`). Not swept on the eval seeds.
- Final cohort = fresh B0 seeds 28–32, reproduced deterministically (B0 == frozen `run_h2`); **every
  reproduction matched the committed B0 evidence**.

## Reliability (M0 / T0 / F1)

| seed | M0 (BindingSlots) | T0 (table) | F1 (hybrid) | fallback invoked | rescued |
|---|---|---|---|---|---|
| 28 | 0.992 | 1.000 | 0.992 | 8 | 0 |
| 29 | 0.000 | 1.000 | 0.883 | 106 | 106 |
| 30 | 0.000 | 1.000 | 0.492 | 59 | 59 |
| 31 | 0.017 | 1.000 | 0.842 | 101 | 99 |
| 32 | 0.033 | 1.000 | 1.000 | 120 | 116 |
| **agg** | **0.208** | **1.000** | **0.842** | 0.657/query | rescue 0.800 |

## The external table itself is reliable

`T0 = 1.000`, and every reliability/lifecycle gate passes: **zero** cross-session and cross-tenant
leakage; expired and deleted records never returned; latest/stale version selection correct;
provenance on **every** fallback (1.000); structured abstention (never a fabricated result) when the
table is unavailable; p95 read latency **0.006 ms** (ceiling 50 ms); BindingSlots byte-identical when
fallback disabled; **no model weight/gradient change**. See `isolation_tests.json`, `integrity_report.json`.

## Why the hybrid trigger failed the gate

Trigger confusion over 600 queries: **tp 380, fp 14, tn 111, fn 95** → **recall 0.80**, precision
0.964. The trigger rarely fires unnecessarily (high precision) but **misses 95 confidently-wrong
failures** — cases where the model routes to the wrong slot with *high* top-1 probability / low
entropy, so the confidence signal does not flag them (concentrated on seed 30: only 59/120 failures
triggered). Those unrescued failures leave F1 (0.842) **15.8 pp below T0 (1.000)**, failing:
- gate 1 (F1 within 1 pp of T0): **FAIL**;
- gate 2 (≥90% of failures rescued): **FAIL** (80%).

Every other gate — incorrect-fallback ≤1% (**0.00%**, the table never returns a wrong answer), zero
leakage, expiry/deletion, provenance, byte-identical-disabled, no-weight-change, p95 latency — passes.

## Interpretation (conservative)

- The external ephemeral table is a **reliable, auditable, isolated, low-overhead recovery store**
  (T0 ceiling verified; all isolation/lifecycle/provenance/latency gates pass).
- The **confidence-triggered hybrid** as specified does **not** reach the operational gate, because
  neural routing confidence ≠ correctness: some failures are *confident*, and the trigger cannot see
  them from read-distribution signals alone.
- This supports only: BindingSlots may remain the fast path with the table as a deterministic recovery
  layer **when a reliable failure detector exists** — which the pure confidence trigger is not here.
  It does **not** support solved routing, reliable neural memory, KDA readiness, or production/DB readiness.

## Next-step recommendation (named, not implemented)

The bottleneck is failure *detection*, not the table. Two directions, each its own phase:
1. **Always-verify (V0/T0 posture):** read the table on every query (full reliability at one table
   read per query, p95 ~0.006 ms here) — trades the fast-path optimization for guaranteed recovery.
2. **A stronger, still-runtime failure detector** (e.g. a key-consistency check between the queried
   entity and the retrieved content) to catch confidently-wrong reads the confidence trigger misses.
External databases, production data, and any neural-routing change remain out of scope. Nothing is
implemented here; KDA remains blocked and neural routing remains unresolved.
