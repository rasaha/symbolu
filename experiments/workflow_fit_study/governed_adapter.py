"""Adapter from the Workflow-Fit study harness to the governed slice 1 contracts
(specification §9 item 5). Lives in ``experiments/``, not in either package.

Maps the study's per-case ``RunRecord``s into:

* one ``ReasoningMethodExecutionRecord`` per (task class, method), whose
  ``llm_calls`` is the SUM of runtime-reported calls over the SAME case set for
  every method, with ``llm_calls_basis = CALLER_SUPPLIED`` and every per-case
  provenance ref in ``capture_refs``. Slice 1 admits exactly one record per
  method per class (5.1-A) and names no resource aggregation; summing over an
  identical case set is the research-only pre-aggregation this adapter
  declares, and it refuses to adapt when the case sets differ.
* one ``MetricClaim`` per (task class, method) with
  ``transformation_method = CALCULATED`` and a ``calculation_ref`` naming the
  research mean, plus a matching ``QualityResult`` carrying the same
  ``AggregationRef``; the task class built here declares that ref in its
  ``ComparisonPolicy.quality_aggregation`` so the engine admits the claim.

The per-case self-reported quality is carried on the record, labelled, and is
never referenced by any claim. Every output is research-only evidence at
OBSERVED / UNATTESTED / UNVERIFIED by the record's constants.

No value here is a default: threshold, consequence class, reversibility,
domain, outcome and population are all caller-supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, Iterable, List, Mapping, Tuple

from ugence_governance_contracts.api import MetricClaim, SourceBasis, TransformationMethod
from ugence_jcs import canonical_sha256_hex
from ugence_reasoning_method_governance.api import (
    COMPARISON_REQUEST_SCHEMA_VERSION,
    RECORD_SCHEMA_VERSION,
    TASK_CLASS_SCHEMA_VERSION,
    AggregationRef,
    BindingRef,
    ComparisonPolicy,
    ConsequenceClass,
    CountBasis,
    ExecutionTelemetry,
    QualityResult,
    ReadinessComparisonRequest,
    ReasoningMethodCatalog,
    ReasoningMethodExecutionRecord,
    ReasoningMethodRef,
    ResourceDimension,
    SufficiencyKind,
    SufficiencyRule,
    TaskClassIdentity,
    TaskReversibility,
    UsageAvailabilityToken,
)
from ugence_uvi_policy_contracts.api import ComparisonOperator, GovernedThreshold

from .study import RunRecord, StudyConfig

RESEARCH_MEAN = AggregationRef("research.mean", "0", "calc:experiments.workflow_fit_study.mean_over_cases.v0")
RESEARCH_CALLS_SUM_REF = "calc:experiments.workflow_fit_study.sum_calls_over_identical_case_set.v0"
QUALITY_UNIT = "score.unit"


@dataclass(frozen=True)
class StudyClassDeclaration:
    """Caller-declared governed coordinates for one study task class. No defaults."""

    task_class: str
    domain_ref: str
    intended_outcome_ref: str
    consequence_class: ConsequenceClass
    reversibility: TaskReversibility
    population_ref: str
    benchmark_set_ref: str
    benchmark_set_digest: str
    structural_characteristics: Tuple[str, ...]
    sufficiency_kind: SufficiencyKind


class AdapterRefusal(ValueError):
    """The study data cannot be adapted honestly; nothing is emitted."""


def build_task_class(decl: StudyClassDeclaration, config: StudyConfig) -> TaskClassIdentity:
    tau = config.sufficiency.get(decl.task_class)
    if tau is None:
        raise AdapterRefusal(f"no sufficiency threshold declared for task class {decl.task_class!r}; the adapter supplies none")
    rule = SufficiencyRule(
        rule_id=f"study.{decl.task_class}.sufficiency",
        rule_version="0",
        kind=decl.sufficiency_kind,
        threshold=GovernedThreshold(f"study.{decl.task_class}.tau", QUALITY_UNIT, ComparisonOperator.GTE, str(tau)),
    )
    policy = ComparisonPolicy(
        policy_id=f"study.{decl.task_class}.policy",
        policy_version="0",
        sufficiency=rule,
        required_dimensions=(ResourceDimension.LLM_CALLS,),
        quality_aggregation=RESEARCH_MEAN,
    )
    return TaskClassIdentity(
        TASK_CLASS_SCHEMA_VERSION, f"study.{decl.task_class}", decl.domain_ref, decl.intended_outcome_ref,
        decl.consequence_class, decl.reversibility, (), (), decl.structural_characteristics, decl.population_ref,
        decl.benchmark_set_ref, decl.benchmark_set_digest, policy,
    )


def _case_set_digest(records: Iterable[RunRecord]) -> str:
    return canonical_sha256_hex(sorted(r.case_id for r in records))


def adapt_class(
    *,
    records: Iterable[RunRecord],
    task_class: TaskClassIdentity,
    study_class: str,
    catalog: ReasoningMethodCatalog,
    method_versions: Mapping[str, str],
    binding: BindingRef,
    tenant_id: str,
    subject_id: str,
    issuer_identity: str,
    model_ref: str,
    captured_at: datetime,
    baseline_workflow: str,
    request_id: str,
) -> ReadinessComparisonRequest:
    """One request per study task class. Refuses when methods ran different case sets."""

    rows = [r for r in records if r.task_class == study_class]
    if not rows:
        raise AdapterRefusal(f"no run records for study class {study_class!r}")
    by_method: Dict[str, List[RunRecord]] = {}
    for r in rows:
        by_method.setdefault(r.workflow.value, []).append(r)
    case_sets = {m: frozenset(x.case_id for x in rs) for m, rs in by_method.items()}
    if len(set(case_sets.values())) != 1:
        raise AdapterRefusal("methods ran different case sets; summed calls would not be comparable and the adapter declares no other aggregation")
    input_digest = _case_set_digest(rows)

    out_records: List[ReasoningMethodExecutionRecord] = []
    quality_results: List[QualityResult] = []
    claims: List[MetricClaim] = []
    refs: Dict[str, ReasoningMethodRef] = {}
    for method_id in sorted(by_method):
        rs = sorted(by_method[method_id], key=lambda x: x.case_id)
        ref = catalog.method_ref(method_id, method_versions[method_id])
        refs[method_id] = ref
        telemetry = ExecutionTelemetry(
            llm_calls=sum(x.calls_runtime_reported for x in rs),
            llm_calls_basis=CountBasis.CALLER_SUPPLIED,
            token_usage_availability=UsageAvailabilityToken.UNAVAILABLE_NOT_REPORTED,
            token_usage=None,
            token_count_basis=CountBasis.UNKNOWN,
            duration_ms=int(sum(x.duration_ms for x in rs)),
            capture_refs=tuple(f"study:{study_class}:{method_id}:case:{x.case_id}:calls:{x.calls_runtime_reported}" for x in rs) + (RESEARCH_CALLS_SUM_REF,),
        )
        mean_self = sum(Decimal(str(x.self_reported_quality)) for x in rs) / len(rs)
        record = ReasoningMethodExecutionRecord(
            schema_version=RECORD_SCHEMA_VERSION,
            record_id=f"{request_id}:{method_id}",
            tenant_id=tenant_id,
            subject_id=subject_id,
            invocation_id=f"{request_id}:{method_id}:sum-over-cases",
            method=ref,
            binding=binding,
            task_class_ref=task_class.task_class_id,
            task_class_digest=task_class.task_class_digest,
            input_digest=input_digest,
            model_ref=model_ref,
            policy_refs=(),
            artifacts=(),
            telemetry=telemetry,
            self_reported_quality=str(mean_self),
            issuer_identity=issuer_identity,
            captured_at=captured_at,
            parent_record_digest=None,
        )
        out_records.append(record)
        mean_quality = sum(x.quality for x in rs) / len(rs)
        claim_id = f"{request_id}:{method_id}:quality"
        claims.append(
            MetricClaim(
                claim_id, tenant_id, subject_id, "study.quality.mean_over_cases", str(mean_quality), QUALITY_UNIT,
                SourceBasis.REPORTED, TransformationMethod.CALCULATED,
                input_evidence_refs=tuple(f"study:{study_class}:{method_id}:case:{x.case_id}:scorer" for x in rs),
                calculation_ref=RESEARCH_MEAN.calculation_ref,
            )
        )
        quality_results.append(QualityResult(ref, claim_id, QUALITY_UNIT, str(mean_quality), RESEARCH_MEAN))

    if baseline_workflow not in refs:
        raise AdapterRefusal(f"baseline {baseline_workflow!r} has no runs in study class {study_class!r}")
    return ReadinessComparisonRequest(
        schema_version=COMPARISON_REQUEST_SCHEMA_VERSION,
        request_id=request_id,
        task_class=task_class,
        catalog=catalog.ref(),
        baseline=refs[baseline_workflow],
        candidates=tuple(refs[m] for m in sorted(refs)),
        records=tuple(out_records),
        quality_results=tuple(quality_results),
        quality_claims=tuple(claims),
        requester_identity=issuer_identity,
    )


__all__ = ["RESEARCH_MEAN", "RESEARCH_CALLS_SUM_REF", "QUALITY_UNIT", "StudyClassDeclaration", "AdapterRefusal", "build_task_class", "adapt_class"]
