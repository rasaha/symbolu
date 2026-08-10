# Stage Contracts (Phase 3)

*`governed_inference_pilot/contracts.py` (`gip_contracts_v1`). Eleven versioned handoff contracts. Each
validates required fields, missing-field behavior, unknown-vocabulary, and semantic loss, with an
explicit fail-open/fail-closed rule. **No adapter discards unknown fields silently.***

## The eleven contracts

| # | Contract | Required | Fail rule |
|---|---|---|---|
| 1 | request → ExecutionGate | request_id, risk_tier, domain | **closed** |
| 2 | ExecutionGate → ModelPolicy | eligible_models | **closed** |
| 3 | ModelPolicy → execution | selected_model | **closed** |
| 4 | execution → ClaimIntegrity | model_output | **closed** |
| 5 | ClaimIntegrity → ScopeIntegrity | claims | **closed** |
| 6 | claims → evidence binder | claims | **closed** |
| 7 | evidence binder → EvidenceAssurance | evidence_case | **closed** |
| 8 | EvidenceAssurance → AssertionGate | evidence_state | **closed** |
| 9 | assertion → action extractor | assertion_disposition | open (diagnostic) |
| 10 | action → ActionGate | action_proposal | **closed** |
| 11 | all → audit | trace_id | open (never blocks audit) |

## Rules per contract

- **Required fields:** absent or empty → `GIP.MISSING_FIELD`. On a fail-closed contract this forces the
  pipeline to `CONTRACT_ERROR` / `INDETERMINATE`; it never proceeds as if the field were present.
- **Unknown vocabulary:** a disposition value outside the known set for that field (`evidence_state`,
  `assertion_disposition`) → `GIP.UNKNOWN_VOCAB`. Fail-closed — an unrecognized downstream disposition
  is treated as unsafe, never mapped to ALLOW.
- **Version mismatch:** the payload carries the producing component's version; a mismatch against the
  contract's expected version is recorded as a reason code and, on fail-closed contracts, halts.
- **Semantic-loss check:** `semantic_loss_check(source, transformed, must_preserve)` returns any field
  that was non-empty in the source representation but empty after transformation (e.g. a dropped
  `exceptions` list). Both source and transformed representations are preserved in the audit; a loss on
  a governing field fails closed.
- **Trace linkage:** every contract result is attached to the stage event and the unified trace.

## The fail-closed principle

The eight safety-critical handoffs (1–8, 10) fail **closed**: a contract violation cannot produce a
permissive outcome. Only the diagnostic (9) and audit (11) handoffs fail open, and even they record the
violation. This is the structural guarantee that a broken contract degrades to `CONTRACT_ERROR` /
`INDETERMINATE` — never to a silent `WOULD_ALLOW`.

## Source and transformed representations

Every adapter preserves BOTH the component's original output (`source_repr`) and the canonical-schema
mapping (`transformed_repr`) in its stage event. This is what makes the semantic-loss check auditable
and what lets replay (Phase 6) detect adapter drift.
