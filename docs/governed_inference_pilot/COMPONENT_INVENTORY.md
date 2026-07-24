# Component Inventory (Phase 1)

*Each stage the pilot composes, consumed read-only. Version identifiers are read from the frozen
components; failure modes and residuals are recorded so the orchestrator (Phase 13) and the integration
failure taxonomy (Phase 16) can plan for them.*

| Component | Import (read-only) | Version | Local-invokable | Fixture need |
|---|---|---|---|---|
| ExecutionGate | `execution_gate.gate.ExecutionGate` | `exec_gate_v1` | yes | candidate registry + evidence |
| ModelPolicy | `model_selection_reconciliation.variants.route_A/B/C` | reconciliation v1 | yes | task + registry + telemetry |
| Model execution | (pilot fixture layer) | `fixture_v1` | yes (fixtures) | recorded / deterministic outputs |
| ClaimIntegrity | `claim_integrity.claims.decompose` | `ci_claim_v1` (17 dispositions) | yes | none (text in) |
| ScopeIntegrity | `scope_integrity.variants.variant_h_integrated` | gated hybrid | yes | none |
| EvidenceAssurance | `evidence_assurance.adapter.assess / evidence_to_delivery` | `ea_evidence_v1` (11 states) | yes | evidence case dict |
| AssertionGate | `assertion_gate_robustness.gate.govern` | `assertion_gate_v1` / `agr_policy_v1` | yes | SignalBundle |
| ActionGate | `control_plane_shadow.adapters.action_gate_adapter` | shadow adapter | yes | action proposal |

## Per-component detail

### ExecutionGate (`exec_gate_v1`)
- **Responsibility:** is execution currently possible and permitted for a candidate model?
- **Inputs:** `Candidate`, `Request`, `now`. **Outputs:** `EligibilityDecision(state ∈ {ELIGIBLE,
  CONDITIONALLY_ELIGIBLE, INELIGIBLE, INDETERMINATE}, reasons, conditions, policy_version, ttl)`.
- **Abstention:** `INDETERMINATE` when evidence is insufficient/stale. **Failure mode:** stale evidence
  TTL, missing feature. **Audit:** reason codes, conditions, ttl. **Residual:** eligibility is
  evidence-driven; missing evidence → INDETERMINATE, not a guess.

### ModelPolicy (reconciliation v1)
- **Responsibility:** select among executable models by the routing objective (A = soft utility;
  B/C = constrained cost with a quality floor). **Outputs:** chosen model + rationale, or abstention
  when no eligible model meets the floor. **Residual:** Q̂ is optimistically calibrated (documented in
  the reconciliation study); high quality floors raise abstention.

### ClaimIntegrity (`ci_claim_v1`)
- **Responsibility:** decompose text into governable claims, preserving scope; resolve references; skip
  non-assertive text. **Outputs:** claim units + disposition (17-value vocabulary). **Abstention:**
  `INDETERMINATE`/`AMBIGUOUS`. **Residual:** ties sentence-splitting on the primary endpoint; value is
  reference resolution + validation as an audit (see ClaimIntegrity decision).

### ScopeIntegrity (gated hybrid)
- **Responsibility:** the narrowly-gated postposed-exception conjunction fix over the ClaimIntegrity
  splitter output. **Outputs:** scope-faithful atomic claims, or `INDETERMINATE_SCOPE` (preserve-whole)
  when attachment is not provable. **Residual:** ambiguous families flagged, not solved; the general
  0.000 is corpus-bounded.

### EvidenceAssurance (`ea_evidence_v1`, 11 states)
- **Responsibility:** evidence-state disposition from provenance/independence/alignment/freshness/
  authority/counterevidence. **Outputs:** `AssuranceResult(state, delivery_effect, reason_codes)`.
  **Abstention:** `INDETERMINATE` on untrusted/missing provenance. **Residual:** no-tell correlated
  failure escapes (documented ceiling); metadata-based only.

### AssertionGate (`assertion_gate_v1` / `agr_policy_v1`)
- **Responsibility:** deliver / qualify / reject / escalate an assertion from calibrated signals.
  **Outputs:** `GateDecision(disposition, delivered_text, qualification, reason_codes, uncertainty,
  effective_support, audit)`. **Residual:** correlated-signal failure defeats it (kept for high-risk).

### ActionGate (shadow adapter)
- **Responsibility:** permit / constrain / block / escalate a proposed action. **Outputs:**
  `ActionDisposition`. **Residual:** shadow adapter; action authority mapping is conservative.

## Known cross-cutting residuals
- Every stage has an abstention path; the pilot must ensure abstentions compose safely (Phase 19).
- Dispositions differ per stage and must be reconciled without conflation (Phase 4).
- No stage may infer another stage approved something unless the versioned contract says so (Phase 3).
