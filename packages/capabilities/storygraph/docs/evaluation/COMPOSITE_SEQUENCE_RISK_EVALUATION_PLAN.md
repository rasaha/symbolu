# Composite Sequence-Risk — Evaluation Plan

This plan defines how the Composite Capability & Sequence-Risk Analyzer will be
measured. **No benchmark values are reported here.** Metrics that require a
labeled evaluation corpus — which does not exist in-repo — are marked
**`NOT RUN`**. Metrics measurable from the built-in *illustrative* scenarios are
labeled as such and are explicitly **not** a benchmark.

The runnable harness is `ugence_storygraph/evaluation/harness.py`
(`python3 -m ugence_storygraph.cli eval`). The results template with all
population metrics pre-marked `NOT RUN` is
`ugence_storygraph/evaluation/results/eval_results_template.json`.

## 1. What a real corpus must contain

To move any population metric off `NOT RUN`, a corpus MUST provide:

- event streams labeled at the **assembly** level as `harmful` / `benign`;
- for harmful streams, the event index of **recipe completion** (for lead-time);
- coverage of the structural cases in §3 (cross-session, multi-actor, look-alikes,
  approvals, duplicates/retries, multi-tenant);
- the ontology + recipe versions the labels were authored against.

Without this, reporting a rate would be fabrication.

## 2. Metric definitions

| Metric | Definition | Status |
|--------|------------|--------|
| True-positive rate | escalated harmful assemblies / harmful assemblies | **NOT RUN** (no corpus) |
| False-escalation rate | escalated benign assemblies / benign assemblies | **NOT RUN** (no corpus) |
| Miss rate | harmful assemblies never escalated / harmful assemblies | **NOT RUN** (no corpus) |
| Mean events before escalation | mean event count until first `ESCALATE` | measured (illustrative only) |
| Escalation lead time before completion | events between first `ESCALATE` and labeled completion | **NOT RUN** (needs completion labels) |
| Cross-session detection rate | detected / harmful assemblies spanning ≥2 correlations | **NOT RUN** (no corpus) |
| Multi-actor detection rate | detected / harmful assemblies with ≥2 actors | **NOT RUN** (no corpus) |
| Duplicate sensitivity | duplicates suppressed under injected duplicates | measured (illustrative only) |
| State-memory growth | tenants × assemblies × instances retained | measured (illustrative only) |
| Runtime per event | wall-clock per event on a controlled host | **NOT RUN** (excluded from replay path) |
| Determinism across repeated runs | identical finding digests across N replays | measured — **PASS** on illustrative |
| Explanation completeness | fraction of findings with a non-empty explanation | measured (illustrative only) |

## 3. Structural coverage (from the deterministic test suite)

The 20 scenarios in `tests/test_analyzer.py` establish *behavioral* correctness
(detection AND non-detection) but are **not** a statistical corpus: true harmful
sequence; benign look-alike; authorized security test; out-of-order; long-and-slow;
cross-session; multi-actor; human+agent; interleaved workflows; duplicates;
idempotency retries; multi-tenant isolation; unknown/unencoded threat; renamed
tools (capability metadata); expired vs. valid approval; ambiguous linkage;
bounded-state unavailable; recipe-version change mid-case; policy binding.

## 4. Threats to validity

- **Recipe coverage bias.** True/false rates only bind to *encoded* recipes;
  unknown composites are misses by construction (an honest limitation, §13 of the
  spec). A corpus must include out-of-recipe harmful streams to size the blind
  spot.
- **Label authoring against the recipes under test** would inflate TPR; labels
  MUST be authored independently of the recipe library.
- **Entity-linkage sensitivity.** Detection depends on the configured
  `AssemblyKeySpec`; evaluation MUST fix and report the spec set.

## 5. Phase-2 update — synthetic corpus + evidence discipline

A deterministic 25-family adversarial synthetic corpus now exists
(`ugence_storygraph/evaluation/corpus.py`) with independent labels, hard
benign look-alikes, dev/calibration/**final** splits, a manifest, and a
pre-evaluation freeze. The harness (`cli eval`) computes metrics broken down by
family and split, each carrying an evidence-discipline label (§17 of the spec):

- **`Measured — synthetic corpus`**: true-positive rate (encoded), false-escalation
  rate, miss rate, precision, recall (encoded), unknown-threat detection (expected
  ≈ 0), mean events before escalation, alerts/1,000 events, incorrect
  benign-neutralization rate.
- **`Measured — unit/integration test`**: determinism across replay.
- **`REQUIRES ENTERPRISE DATA`**: escalation lead time before completion,
  alerts/tenant-day, peak state/tenant.
- **`NOT RUN`**: runtime/event, entity-linkage error rate (needs labeled linkage
  ground truth).

Synthetic-corpus numbers are **not** enterprise performance and **not**
unknown-threat coverage. The `final` split must not be used to tune recipes,
linkage, decay, thresholds, or benign exclusions; it is enumerated in the freeze
(`cli freeze`) so it can be held out.

## 6. Current evidence-based verdict

Behavioral correctness on the encoded recipes and the structural scenarios is
demonstrated and deterministic; the synthetic corpus is measured and labeled.
**All enterprise/live-population accuracy metrics remain `NOT RUN` /
`REQUIRES ENTERPRISE DATA`.** No claim of real-world detection accuracy is made.
Verdict: `CONTINUE — synthetic evaluation only` (see
`SHADOW_PILOT_REPORT_TEMPLATE.md`).
