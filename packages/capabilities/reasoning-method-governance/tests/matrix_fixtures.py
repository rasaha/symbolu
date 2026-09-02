"""Builders for the §11 contract-consistency matrix (rows C1–C24).

Every value here is a TEST INPUT. None is a governed threshold, default or
acceptance criterion. Shared by both packages' test suites.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence, Tuple

from ugence_governance_contracts.api import MetricClaim, SourceBasis, TransformationMethod
from ugence_reasoning_method_governance.api import (
    ATTESTATION_ENVELOPE_SCHEMA_VERSION,
    CATALOG_SCHEMA_VERSION,
    COMPARISON_REQUEST_SCHEMA_VERSION,
    PROFILE_SCHEMA_VERSION,
    RECORD_SCHEMA_VERSION,
    RESEARCH_PLAN_SCHEMA_VERSION,
    TASK_CLASS_SCHEMA_VERSION,
    USAGE_SCOPE_RESEARCH_ONLY,
    VERIFICATION_ENVELOPE_SCHEMA_VERSION,
    AggregationRef,
    ArtifactKind,
    ArtifactRef,
    AttestationEnvelope,
    BindingRef,
    ChallengerSamplingPolicy,
    ComparisonPolicy,
    ConsequenceClass,
    CountBasis,
    EvidenceAdmissionRef,
    ExecutionTelemetry,
    ImplementationEvidence,
    ImplementationEvidenceKind,
    QualityResult,
    ReadinessComparisonRequest,
    ReasoningMethodCatalog,
    ReasoningMethodCatalogRef,
    ReasoningMethodEntry,
    ReasoningMethodExecutionRecord,
    ReasoningMethodRef,
    ResearchComparisonPlan,
    ResolvedAdmission,
    ResolvedAuthority,
    ResourceDimension,
    SamplingKind,
    SufficiencyKind,
    SufficiencyRule,
    TaskClassIdentity,
    TaskProfile,
    TaskReversibility,
    TokenUsageSnapshot,
    UsageAvailabilityToken,
    VerificationEnvelope,
)
from ugence_uvi_policy_contracts.api import ComparisonOperator, GovernedThreshold

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64
UNIT = "score.unit"

SEVEN_METHODS: Tuple[str, ...] = (
    "linear_chain",
    "tree_of_thought",
    "iterative_refinement",
    "debate",
    "map_reduce",
    "socratic_progressive",
    "metacognitive",
)

# Evidence refs for the seven WorkflowType members (spec §2, 2026-09-02).
_CLASS_LINES = {
    "linear_chain": 291,
    "tree_of_thought": 396,
    "iterative_refinement": 523,
    "debate": 657,
    "map_reduce": 774,
    "socratic_progressive": 898,
    "metacognitive": 1011,
}


def four_evidence(method_id: str) -> Tuple[ImplementationEvidence, ...]:
    return (
        ImplementationEvidence(
            ImplementationEvidenceKind.CONCRETE_CLASS_REGISTERED,
            f"agentic/agentic_framework/reasoning_workflows.py:{_CLASS_LINES[method_id]}",
            NOW,
        ),
        ImplementationEvidence(ImplementationEvidenceKind.STUB_EXECUTION_COMPLETED, "session:2026-09-02:stub-execution", NOW),
        ImplementationEvidence(ImplementationEvidenceKind.UNIT_TESTS_PRESENT, "agentic/agentic_framework/tests/test_reasoning_workflows.py", NOW),
    )


def c1_catalog_ref(digest: str = HEX_A) -> ReasoningMethodCatalogRef:
    return ReasoningMethodCatalogRef("cat.rm", "1", digest)


def c2_ref(method_id: str = "tree_of_thought", catalog: Optional[ReasoningMethodCatalogRef] = None) -> ReasoningMethodRef:
    return ReasoningMethodRef(catalog or c1_catalog_ref(), method_id, "1")


def c3_entry(method_id: str = "tree_of_thought", evidence: Optional[Sequence[ImplementationEvidence]] = None, signals: Tuple[str, ...] = ("comparison_request",)) -> ReasoningMethodEntry:
    return ReasoningMethodEntry(
        method_id=method_id,
        method_version="1",
        display_name=method_id.replace("_", " ").title(),
        implementation_evidence=tuple(evidence if evidence is not None else four_evidence(method_id)),
        declared_signals=signals,
        requirement_refs=(),
        runtime_binding_ref=f"agentic.reasoning_workflows.WorkflowType.{method_id.upper()}",
    )


def c4_catalog() -> ReasoningMethodCatalog:
    entries = tuple(sorted((c3_entry(m) for m in SEVEN_METHODS), key=lambda e: e.sort_key))
    return ReasoningMethodCatalog(CATALOG_SCHEMA_VERSION, "cat.rm", "1", entries, "issuer:test", NOW)


def threshold(comparator: ComparisonOperator = ComparisonOperator.GTE, literal: str = "0.9", unit: str = UNIT) -> GovernedThreshold:
    return GovernedThreshold("thr.quality", unit, comparator, literal)


def c6_rule(kind: SufficiencyKind = SufficiencyKind.THRESHOLD_BASED, thr: Optional[GovernedThreshold] = None, admission: Optional[EvidenceAdmissionRef] = None) -> SufficiencyRule:
    return SufficiencyRule("rule.suff", "1", kind, thr or threshold(), admission)


def admission_ref() -> EvidenceAdmissionRef:
    return EvidenceAdmissionRef("authority:evidence", "result:admit-1", HEX_C)


def c7_rule_hc() -> SufficiencyRule:
    return c6_rule(admission=admission_ref())


def research_aggregation() -> AggregationRef:
    return AggregationRef("research.mean", "0", "calc:research.mean.v0")


def c8_policy(rule: Optional[SufficiencyRule] = None, dims: Tuple[ResourceDimension, ...] = (ResourceDimension.LLM_CALLS,), aggregation: Optional[AggregationRef] = None) -> ComparisonPolicy:
    return ComparisonPolicy("pol.cmp", "1", rule or c6_rule(), dims, aggregation)


def c24_policy_agg() -> ComparisonPolicy:
    return c8_policy(aggregation=research_aggregation())


def c9_profile() -> TaskProfile:
    return TaskProfile(
        PROFILE_SCHEMA_VERSION, "profile.1", "domain:support", "outcome:resolve",
        ConsequenceClass.RECOVERABLE, TaskReversibility.OUTCOME_REVERSIBLE,
        (), (), ("comparison_request", "multi_part_question"), "population:all",
    )


def c10_class(policy: Optional[ComparisonPolicy] = None, consequence: ConsequenceClass = ConsequenceClass.RECOVERABLE, reversibility: TaskReversibility = TaskReversibility.OUTCOME_COMPENSATABLE, task_class_id: str = "class.support") -> TaskClassIdentity:
    return TaskClassIdentity(
        TASK_CLASS_SCHEMA_VERSION, task_class_id, "domain:support", "outcome:resolve",
        consequence, reversibility, (), (), ("comparison_request",), "population:all",
        "benchmarks:support", HEX_B, policy or c8_policy(),
    )


def c11_class_hc() -> TaskClassIdentity:
    return c10_class(policy=c8_policy(rule=c7_rule_hc()), consequence=ConsequenceClass.SEVERE)


def c12_telemetry(calls: Optional[int] = 4, basis: CountBasis = CountBasis.INJECTED_COUNTER) -> ExecutionTelemetry:
    return ExecutionTelemetry(calls, basis, UsageAvailabilityToken.UNAVAILABLE_NOT_REPORTED, None, CountBasis.UNKNOWN, 12)


def c13_telemetry_tokens(calls: int = 4, total_tokens: int = 812) -> ExecutionTelemetry:
    return ExecutionTelemetry(calls, CountBasis.INJECTED_COUNTER, UsageAvailabilityToken.AVAILABLE, TokenUsageSnapshot(total_tokens=total_tokens), CountBasis.PROVIDER_REPORTED, 12)


def c14_binding() -> BindingRef:
    return BindingRef("binding.1", "config.1", HEX_A, HEX_B, HEX_D)


def c15_record(method: Optional[ReasoningMethodRef] = None, telemetry: Optional[ExecutionTelemetry] = None, task_class: Optional[TaskClassIdentity] = None, record_id: str = "rec.1", parent: Optional[str] = None, issuer: str = "adapter:study", self_quality: Optional[str] = "0.75", artifacts: Optional[Tuple[ArtifactRef, ...]] = None, captured_at: datetime = NOW, schema_version: str = RECORD_SCHEMA_VERSION) -> ReasoningMethodExecutionRecord:
    tc = task_class or c10_class()
    return ReasoningMethodExecutionRecord(
        schema_version=schema_version,
        record_id=record_id,
        tenant_id="tenant.t",
        subject_id="subject.s",
        invocation_id=f"inv.{record_id}",
        method=method or c2_ref(),
        binding=c14_binding(),
        task_class_ref=tc.task_class_id,
        task_class_digest=tc.task_class_digest,
        input_digest=HEX_C,
        model_ref="model:authority-ref",
        policy_refs=(),
        artifacts=artifacts if artifacts is not None else (ArtifactRef(ArtifactKind.FINAL_OUTPUT, "artifact:out", HEX_A),),
        telemetry=telemetry or c12_telemetry(),
        self_reported_quality=self_quality,
        issuer_identity=issuer,
        captured_at=captured_at,
        parent_record_digest=parent,
    )


def c16_child(parent: ReasoningMethodExecutionRecord) -> ReasoningMethodExecutionRecord:
    return c15_record(method=parent.method, record_id="rec.1.child", parent=parent.record_digest, task_class=None)


def c17_quality(method: Optional[ReasoningMethodRef] = None, value: str = "0.92", unit: str = UNIT, claim_ref: str = "claim.1", aggregation: Optional[AggregationRef] = None) -> QualityResult:
    return QualityResult(method or c2_ref(), claim_ref, unit, value, aggregation)


def c18_quality_agg(method: Optional[ReasoningMethodRef] = None, value: str = "0.92", claim_ref: str = "claim.1") -> QualityResult:
    return c17_quality(method, value, claim_ref=claim_ref, aggregation=research_aggregation())


def claim(claim_id: str, value: str, unit: str = UNIT, input_refs: Tuple[str, ...] = (), evidence_refs: Tuple[str, ...] = (), calculated: bool = False) -> MetricClaim:
    if calculated:
        return MetricClaim(claim_id, "tenant.t", "subject.s", "quality", value, unit, SourceBasis.REPORTED, TransformationMethod.CALCULATED,
                           input_evidence_refs=input_refs, evidence_refs=evidence_refs, calculation_ref="calc:research.mean.v0")
    return MetricClaim(claim_id, "tenant.t", "subject.s", "quality", value, unit, SourceBasis.REPORTED, TransformationMethod.DIRECT,
                       input_evidence_refs=input_refs, evidence_refs=evidence_refs)


def c19_attestation(record: ReasoningMethodExecutionRecord, attester: str = "cm-ta1", fields: Tuple[str, ...] = ("telemetry.llm_calls",), record_digest: Optional[str] = None) -> AttestationEnvelope:
    return AttestationEnvelope(ATTESTATION_ENVELOPE_SCHEMA_VERSION, "att.1", record_digest or record.record_digest, attester, "capture:cm-ta1:fingerprints", fields, NOW)


def c20_verification(record: ReasoningMethodExecutionRecord, attestation: Optional[AttestationEnvelope], verifier: str = "tev", record_digest: Optional[str] = None) -> VerificationEnvelope:
    att_digest = attestation.envelope_digest if attestation is not None else HEX_D
    return VerificationEnvelope(VERIFICATION_ENVELOPE_SCHEMA_VERSION, "ver.1", record_digest or record.record_digest, att_digest, verifier, "verification:tev:1", ("telemetry.llm_calls",), NOW)


def two_method_request(
    *,
    task_class: Optional[TaskClassIdentity] = None,
    baseline_calls: int = 1,
    candidate_calls: int = 4,
    baseline_quality: str = "0.92",
    candidate_quality: str = "0.94",
    baseline_telemetry: Optional[ExecutionTelemetry] = None,
    candidate_telemetry: Optional[ExecutionTelemetry] = None,
    quality_results: Optional[Tuple[QualityResult, ...]] = None,
    quality_claims: Optional[Tuple[MetricClaim, ...]] = None,
    records: Optional[Tuple[ReasoningMethodExecutionRecord, ...]] = None,
    candidates: Optional[Tuple[ReasoningMethodRef, ...]] = None,
    attestation_envelopes: Tuple[AttestationEnvelope, ...] = (),
    verification_envelopes: Tuple[VerificationEnvelope, ...] = (),
    resolved_authorities: Tuple[ResolvedAuthority, ...] = (),
    resolved_admissions: Tuple[ResolvedAdmission, ...] = (),
    requester_identity: str = "requester:study",
    schema_version: str = COMPARISON_REQUEST_SCHEMA_VERSION,
    request_id: str = "req.1",
) -> ReadinessComparisonRequest:
    """C21: baseline linear_chain (1 call, 0.92) and candidate tree_of_thought (4 calls, 0.94)."""
    tc = task_class or c10_class()
    lc, tot = c2_ref("linear_chain"), c2_ref("tree_of_thought")
    recs = records if records is not None else (
        c15_record(lc, baseline_telemetry or c12_telemetry(baseline_calls), tc, "rec.lc"),
        c15_record(tot, candidate_telemetry or c12_telemetry(candidate_calls), tc, "rec.tot"),
    )
    qrs = quality_results if quality_results is not None else (
        c17_quality(lc, baseline_quality, claim_ref="claim.lc"),
        c17_quality(tot, candidate_quality, claim_ref="claim.tot"),
    )
    claims = quality_claims if quality_claims is not None else tuple(claim(q.claim_ref, q.value, q.governed_unit) for q in qrs)
    return ReadinessComparisonRequest(
        schema_version=schema_version,
        request_id=request_id,
        task_class=tc,
        catalog=c1_catalog_ref(),
        baseline=lc,
        candidates=candidates if candidates is not None else (lc, tot),
        records=recs,
        quality_results=qrs,
        quality_claims=claims,
        attestation_envelopes=attestation_envelopes,
        verification_envelopes=verification_envelopes,
        resolved_authorities=resolved_authorities,
        resolved_admissions=resolved_admissions,
        requester_identity=requester_identity,
    )


def c23_plan() -> ResearchComparisonPlan:
    return ResearchComparisonPlan(
        RESEARCH_PLAN_SCHEMA_VERSION, "plan.1", c10_class(), c14_binding(), c1_catalog_ref(), c2_ref("linear_chain"),
        (), ChallengerSamplingPolicy(SamplingKind.PREREGISTERED, "prereg:plan.1", "coverage:plan.1"),
        USAGE_SCOPE_RESEARCH_ONLY, "researcher:test", NOW,
    )
