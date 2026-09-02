# ugence-reasoning-method-governance

Shared reasoning-method contracts: slice 1 (research-only) of
`docs/architecture/REASONING_METHOD_GOVERNANCE_CONTRACT_AND_COMMISSIONING_BALLOT.md`,
owner-ratified 2026-09-02.

Contents, by specification section:

- §2 `ReasoningMethodCatalog`, `ReasoningMethodCatalogRef`, `ReasoningMethodRef`,
  `ReasoningMethodEntry` with evidence-derived `implementation_status`
- §3 `TaskProfile`, `TaskClassIdentity`, `ComparisonPolicy`, `SufficiencyRule`,
  `AggregationRef`, `EvidenceAdmissionRef`, `TaskReversibility`, `ConsequenceClass`
- §4 `ReasoningMethodExecutionRecord` v1, permanently `OBSERVED / UNATTESTED /
  UNVERIFIED` as class constants; `ExecutionTelemetry` with mirrored, pinned
  telemetry vocabulary
- §5 `ReasoningMethodFitAssessment`, `FitOutcome`, `QualityResult`, `ResourceDelta`,
  `DominationRecord`
- §6 `AttestationEnvelope`, `VerificationEnvelope`, `EvidenceStatusView` (shapes only;
  slice 1 issues no envelope)
- §7 `ReadinessComparisonRequest`, `ReadinessComparisonResult`, `Refusal`
- §8 `ResearchComparisonPlan`
- §11 `ContractErrorCode`, `RefusalCode`

This package holds contracts only. The comparison implementation is
`ugence-readiness-comparison`, which this package never imports. Nothing here
imports the experimental reasoning runtime under `agentic/`; a boundary test
enforces that. No approval, eligibility, pilot state, revision lineage or
reassessment trigger is defined.
