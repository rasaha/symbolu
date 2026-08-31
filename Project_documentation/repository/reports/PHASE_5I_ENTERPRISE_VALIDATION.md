# Phase 5I — Enterprise Validation Pilot

- **Dataset:** `enterprise_pilot_v1` (hash `4d6de4294324a7b4…`, 90 scenarios, 3 domains)
- **Substantive reproducibility digest:** `a293154ff74b7665…`
- **Overall pilot pass:** YES

## Measured result

- Scenarios reproducing ground truth: **90/90**
- Safety invariants: **ALL PASS** (15/15)
- Failure injection fail-safe: **ALL FAIL-SAFE** (13/13)
- Provider independence: **PEERS**
- Manifest valid: **True**

### Metrics by layer (no aggregate governance score)

**TAP (assertion):**
- `outcome_accuracy`: 1.0
- `supported_precision`: 1.0
- `supported_precision_n`: 45
- `supported_recall`: 1.0
- `supported_recall_n`: 45
- `unsupported_recall`: 1.0
- `constrained_recall`: 1.0
- `indeterminate_recall`: 1.0
- `qualifier_detection_recall`: 1.0
- `unsupported_component_recall`: 1.0
- `evidence_coverage_mean_abs_error`: 0.0
- `provider_failure_failsafe_rate`: 1.0
- `provider_failure_n`: 3

**ActionGate (action):**
- `authorization_accuracy`: 1.0
- `unsafe_authorization_rate`: 0.0
- `false_denial_rate`: 0.0
- `constraint_preservation_rate`: 1.0
- `obligation_preservation_rate`: 1.0
- `denial_non_dispatch_rate`: 1.0
- `indeterminate_non_dispatch_rate`: 1.0
- `provider_failure_failsafe_rate`: 1.0
- `provider_failure_n`: 9
- `actions_evaluated_n`: 75

**Workflow:**
- `end_to_end_trace_completeness`: 1.0
- `provider_resolution_determinism`: 1.0
- `constraint_enforcement_rate`: 1.0
- `obligation_verification_rate`: 1.0
- `execution_reconciliation_consistency`: 1.0
- `cross_provider_isolation_violations`: 0
- `audit_correlation_completeness`: 1.0
- `scenarios_n`: 90

## Designed expectation

The pilot composes the frozen kernel, framework, TAP, and ActionGate through
their public APIs and drives the full workflow (assertion → assessment →
recommendation → decision → action → authorization → execution →
reconciliation). Each scenario's expected outcome was authored independently,
before execution, from design intent — never inferred from provider output.

## Inference

The architecture operates coherently under realistic cross-provider workflows
while preserving its boundaries: unsupported/indeterminate assertions never
become supported; denied/indeterminate actions never dispatch; constraints are
enforced before dispatch; obligations are verified independently of execution
success; and TAP and ActionGate act as independent peers.

## Limitation

- TAP/ActionGate outcomes are produced by the providers' **deterministic
  reference engines configured per domain policy**; the pilot validates
  *workflow integration and invariant enforcement*, not the providers'
  model/NLP accuracy — that is covered by provider conformance, which the
  pilot consumes and does not redefine.
- All data is synthetic. **No production-readiness or regulatory-compliance
  claim** is made from these results.
- The `tenant` field remains absent from the neutral request contract (noted
  in Phase 5G/5H); no scenario required it, so no contract extension is
  proposed.

