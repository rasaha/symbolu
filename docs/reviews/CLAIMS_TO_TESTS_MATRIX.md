# Claims-to-Tests Matrix

**Date:** 2026-02-13
**Purpose:** Map every concrete product/technical claim in external-facing documents to the test suite(s) that validate it.
**Scope:** Claims sourced from `docs/INVESTOR_PITCH.md`. Tests sourced from `tests/`, `symbolu/**/tests/`, evaluation scripts.
**Update cadence:** Review after each phase merge or investor-facing doc change.

> This document exists for **alignment and audit**, not activation.
> A claim without a linked test suite is an **unvalidated assertion**.

---

## 1) Master Claims Table

Each claim is assigned a validation status:

- **VALIDATED** — Dedicated test suite exists, tests pass in CI.
- **PARTIAL** — Some tests cover the claim, but not a dedicated suite or not full-scope.
- **UNVALIDATED** — No test directly validates this claim.

### A. Complexity & Scaling

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| CS-1 | O(n) Phase Attention — Linear scaling | L9, L627 | `symbolu/ontological/test_phase_attention.py` | **VALIDATED** |
| CS-2 | State prediction: O(32) — 1,500x simpler | L553 | `symbolu/ontological/test_phase_attention.py` | **PARTIAL** |
| CS-3 | O(n) for both computation and storage | L639 | `symbolu/ontological/test_phase_attention.py` | **PARTIAL** |

**Notes:** `test_phase_attention.py` explicitly measures scaling ratios at seq_len=[128,256,512,1024,2048] and asserts phase attention ratio < standard attention ratio (O(n) vs O(n^2)). Storage O(n) is implied by the binding cache design but not directly benchmarked in a dedicated test.

### B. Determinism & Auditability

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| DA-1 | Deterministic | L31, L689 | `tests/ontology_router/test_ontological_router_r1.py` | **VALIDATED** |
| DA-2 | 100% auditable | L31 | `tests/explainability/test_telemetry_schema.py` | **VALIDATED** |
| DA-3 | Regulatory compliant | L32 | `tests/explainability/test_telemetry_schema.py` | **PARTIAL** |
| DA-4 | Full audit trail | L686 | `tests/explainability/test_telemetry_schema.py` (`TestAuditTrail`) | **VALIDATED** |
| DA-5 | Provable reasoning | L13 | `tests/test_ledger_replay_verifier.py` | **PARTIAL** |

**Notes:** DA-1 is backed by 75+ ontology router tests (100-run determinism tests, forbidden imports, hash stability) and 50+ ledger replay verifier tests. DA-3 ("regulatory compliant") is supported by the enterprise policy engine tests but no actual regulatory certification exists — this claim should be qualified. DA-5 is supported by ledger replay verification (deterministic re-execution) but "provable" implies formal verification which does not exist.

### C. Semantic Grounding & Interpretability

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| SG-1 | 32D Sovereign State — Interpretable ontology | L10, L315 | `tests/integration/test_sovereign_integration.py` | **VALIDATED** |
| SG-2 | Interpretable meaning | L619 | `tests/explainability/test_telemetry_schema.py` (`TestPhaseQuadExplainer`) | **VALIDATED** |
| SG-3 | 32D State trace | L683 | `tests/explainability/test_telemetry_schema.py` | **VALIDATED** |

**Notes:** The 32D Sovereign State is defined in `symbolu/phase_transformer.py:103-176` with explicit plane decomposition (Phase[0:12], Control[12:28], Learning[28:32]). The explainer produces per-layer traces of all 32 dimensions.

### D. Hallucination Detection

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| HD-1 | Hallucination Detection — Built-in (Vritti layer) | L22 | `symbolu/agentic_framework/tests/test_confidence_gate.py` | **PARTIAL** |
| HD-2 | <5% (Vritti detection) | L668 | — | **UNVALIDATED** |

**Notes:** HD-1 is partially covered by confidence gating tests which verify that low-confidence outputs are blocked/escalated (Vritti maps to epistemic reliability in the control plane). HD-2 cites a specific "<5%" hallucination rate but no test suite benchmarks this metric against a hallucination dataset.

### E. Confidence-Gated Compute

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| CG-1 | PID-governed reasoning | L11, L685 | `symbolu/agentic_framework/tests/test_confidence_gate.py` | **VALIDATED** |
| CG-2 | SRK Control System | L11 | `symbolu/agentic_framework/tests/test_confidence_gate.py` | **VALIDATED** |

**Notes:** 70+ tests covering FULL/CAUTIOUS/CONFIRM/BLOCKED execution modes, budget allocation scaling with confidence, and memory gating.

### F. Context & Retrieval

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| CR-1 | Infinite context | L13 | `test_needle_haystack.py`, `eval_passkey.py` | **PARTIAL** |
| CR-2 | 100% at 10K tokens | L21 | `test_needle_haystack.py` | **PARTIAL** |
| CR-3 | 99% reduction at 32K context | L19 | — | **UNVALIDATED** |

**Notes:** CR-1 is backed by needle-in-haystack and passkey evaluation scripts but "infinite" is aspirational — tests cover up to 128K context, not unbounded. CR-2 references 100% retrieval accuracy at 10K but the test harness does not assert this specific threshold in CI. CR-3 claims a 99% memory reduction at 32K context which requires a benchmarking test against a baseline (not present).

### G. Cost & Efficiency

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| CE-1 | 25-30x savings | L29 | — | **UNVALIDATED** |
| CE-2 | 500x faster | L30 | — | **UNVALIDATED** |
| CE-3 | 83-97% cost savings | L76 | — | **UNVALIDATED** |
| CE-4 | 77x reduction (vector dimensions 10D vs 768D) | L33, L160 | — | **UNVALIDATED** |

**Notes:** These are comparative cost/efficiency claims against LLM API pricing. They are derived from architectural arguments (symbolic routing at $0 vs LLM API calls at $X) but no test suite computes or validates these ratios. These claims should either be qualified as projections or backed by a reproducible cost benchmark.

### H. Accuracy & Routing

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| AR-1 | Intent classification (98% accuracy) | L954 | `tests/training/test_trainers.py` | **PARTIAL** |
| AR-2 | <1ms routing latency | L951, L1273 | `tests/ontology_router/test_ontological_router_r1.py` | **PARTIAL** |
| AR-3 | Overall STL Accuracy 98% | L1226 | — | **UNVALIDATED** |

**Notes:** AR-1 trainer tests verify that training runs complete and produce metrics but do not assert a 98% accuracy threshold. AR-2 router tests verify correctness but do not benchmark latency. AR-3 claims 98% overall accuracy which requires an evaluation benchmark harness.

### I. Ontology Governance

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| OG-1 | Ontology freeze contract | (internal) | `tests/test_ontology_freeze_contract.py` | **VALIDATED** |
| OG-2 | Deterministic routing (fail-closed) | (internal) | `tests/ontology_router/test_ontological_router_r1.py` | **VALIDATED** |
| OG-3 | Phase-4A exclusive access | (internal) | `tests/test_ontology_freeze_contract.py` | **VALIDATED** |

**Notes:** These are not investor-facing claims but are internal architectural guarantees. All are fully validated with dedicated test suites and CI enforcement.

### J. Coherence & Stability

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| ST-1 | Emergency Brake: Catastrophic Deviation Protection | L442 | `tests/test_phase48_macro_stability_regulator.py` | **VALIDATED** |
| ST-2 | Closed-loop control for stable, predictable reasoning | L379 | `tests/test_phase49_unified_temporal_stability.py` | **VALIDATED** |
| ST-3 | ±5% (predictable) cost variance | L173 | — | **UNVALIDATED** |

**Notes:** ST-1 and ST-2 are backed by phase-level invariance audits. ST-3 is a financial projection with no test coverage.

### K. Security

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| SE-1 | Adversarial detection | (telemetry) | `symbolu/mechanical/pipeline/integration_tests/test_adversarial_po1_p9.py` | **VALIDATED** |
| SE-2 | Prompt injection detection | (telemetry) | `tests/explainability/test_telemetry_schema.py`, `tests/unit/service/test_api_security.py` | **VALIDATED** |

### L. Production Readiness

| ID | Claim (verbatim) | Source Line | Primary Test Suite | Validation |
|----|-------------------|-------------|-------------------|------------|
| PR-1 | 9,431 tests passing (99.7% pass rate) | L1364 | CI pipeline (all workflows) | **VALIDATED** |
| PR-2 | 78.1% code coverage | L1365 | `.github/workflows/pipeline-ci.yml` (coverage report) | **VALIDATED** |
| PR-3 | 48/48 phases healthy (100% phase health) | L1366 | `.github/workflows/pipeline-ci.yml` (invariance audit) | **VALIDATED** |
| PR-4 | Zero critical issues | L1367 | — | **PARTIAL** |

**Notes:** PR-1 through PR-3 are validated by CI. PR-4 ("zero critical issues") is a snapshot claim that can become stale — it should reference a live status badge or be removed.

---

## 2) Validation Summary

| Status | Count | Percentage |
|--------|-------|------------|
| VALIDATED | 19 | 53% |
| PARTIAL | 10 | 28% |
| UNVALIDATED | 7 | 19% |
| **Total** | **36** | **100%** |

### Unvalidated claims requiring action

| ID | Claim | Recommended Action |
|----|-------|-------------------|
| HD-2 | <5% hallucination rate | Add hallucination benchmark test against standard dataset |
| CR-3 | 99% memory reduction at 32K | Add memory profiling benchmark comparing baseline vs phase attention |
| CE-1 | 25-30x cost savings | Add cost model test with mock API pricing |
| CE-2 | 500x faster | Add latency benchmark comparing symbolic routing vs LLM call |
| CE-3 | 83-97% cost savings | Add cost model test (may combine with CE-1) |
| CE-4 | 77x dimension reduction | Add dimension comparison test (10D vs 768D effectiveness) |
| AR-3 | 98% STL accuracy | Add evaluation benchmark with accuracy threshold assertion |

### Partially validated claims requiring tightening

| ID | Claim | Gap | Recommended Action |
|----|-------|-----|--------------------|
| DA-3 | Regulatory compliant | No regulatory cert | Qualify claim or add compliance test suite |
| DA-5 | Provable reasoning | Not formally verified | Qualify as "auditable reasoning" or add formal verification |
| CR-1 | Infinite context | Tests cap at 128K | Qualify as "long context" or extend needle-haystack tests |
| CR-2 | 100% at 10K tokens | No threshold assertion | Add CI assertion for retrieval accuracy at 10K |
| AR-1 | 98% intent accuracy | Training tests don't assert threshold | Add accuracy threshold assertion to trainer eval |
| AR-2 | <1ms routing latency | No latency benchmark | Add latency benchmark to router test suite |

---

## 3) CI Integration

The following CI workflows validate claims in this matrix:

| Workflow | Claims Validated | Status |
|----------|-----------------|--------|
| `ontology-freeze-ci.yml` | OG-1, OG-2, OG-3 | Active |
| `pipeline-ci.yml` | PR-1, PR-2, PR-3, ST-1, ST-2, DA-4 | Active |
| `telemetry-audit-ci.yml` | DA-2, SG-2, SG-3, CG-1, SE-1, SE-2 | Active |
| `backbone-ci.yml` | CS-1 (phase attention) | Active |
| `formula-drift-ci.yml` | ST-1, ST-2 | Active |
| `gcc-safety-ci.yml` | SE-1, SE-2 | Active |

---

## 4) Developer Instructions

### Adding a new claim

1. Add the claim to the appropriate category in Section 1 with status **UNVALIDATED**.
2. Identify or create the test suite that validates it.
3. Update the Primary Test Suite column and change status to **VALIDATED** or **PARTIAL**.
4. If the claim requires a new benchmark, file a tracking issue.

### Updating this matrix

- After merging a new phase, check if any PARTIAL or UNVALIDATED claims are now covered.
- After modifying `docs/INVESTOR_PITCH.md`, verify all new claims appear in this matrix.
- Run `tests/test_claims_matrix_integrity.py` in CI to verify all referenced test files exist.

---

## 5) Version History

| Date | Change | Author |
|------|--------|--------|
| 2026-02-13 | Initial matrix — 36 claims mapped across 12 categories | Claude |
