"""Strict, typed loaders for the reference pilot's owner/developer-supplied inputs.

Every loader requires exactly the documented keys with exact JSON types. Nothing is
defaulted, coerced, combined or inferred; unknown keys are refused. Provider credentials
are never read here: the provider reference is a factory dotted path only."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Tuple

from experiments.reasoning_method_advisor_demo.demo import load_profile as _load_profile
from ugence_reasoning_method_governance.api import (
    TASK_CLASS_SCHEMA_VERSION,
    AggregationRef,
    BindingRef,
    ComparisonPolicy,
    ConsequenceClass,
    EvidenceAdmissionRef,
    ResourceDimension,
    SufficiencyKind,
    SufficiencyRule,
    TaskClassIdentity,
    TaskProfile,
    TaskReversibility,
)
from ugence_uvi_policy_contracts.api import ComparisonOperator, GovernedThreshold
from ugence_workflow_fit_pilot.api import ATTESTABLE_TELEMETRY_FIELDS, CaptureBoundaryDeclaration, EvaluatorKind, PilotIdentity, QualityEvaluatorDeclaration

_HEX = re.compile(r"^[0-9a-f]{64}$")
_FACTORY = re.compile(r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")
CREDENTIAL_KEYS = ("api_key", "apikey", "secret", "token", "password", "credential", "authorization", "bearer")


class InputDocumentError(ValueError):
    """The input document is not the canonical shape. Nothing is inferred to repair it."""


def _obj(data: Any, name: str, keys: Tuple[str, ...]) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise InputDocumentError(f"{name} must be a JSON object")
    for k in data:
        if any(c in str(k).lower() for c in CREDENTIAL_KEYS):
            raise InputDocumentError(f"{name}: credential-like key {k!r} is never accepted")
    missing = sorted(set(keys) - set(data))
    unknown = sorted(set(data) - set(keys))
    if missing or unknown:
        raise InputDocumentError(f"{name}: missing {missing or '-'}; unknown {unknown or '-'}")
    return data


def _str(v: Any, name: str, *, blank_ok: bool = False) -> str:
    if not isinstance(v, str) or (not blank_ok and not v.strip()):
        raise InputDocumentError(f"{name} must be a {'' if blank_ok else 'non-blank '}JSON string")
    return v


def _digest(v: Any, name: str) -> str:
    s = _str(v, name)
    if not _HEX.match(s):
        raise InputDocumentError(f"{name} must be 64 lowercase hex characters")
    return s


def _str_list(v: Any, name: str) -> Tuple[str, ...]:
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise InputDocumentError(f"{name} must be a JSON array of strings")
    return tuple(v)


def _enum(cls, v: Any, name: str):
    _str(v, name)
    if v not in {m.value for m in cls}:
        raise InputDocumentError(f"{name} must be one of {sorted(m.value for m in cls)}")
    return cls(v)


def _instant(v: Any, name: str) -> datetime:
    s = _str(v, name)
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise InputDocumentError(f"{name} must be an ISO 8601 instant") from None
    if d.tzinfo is None:
        raise InputDocumentError(f"{name} must carry a UTC offset")
    return d


def load_profile(data: Any) -> TaskProfile:
    """The developer-authored typed profile, exactly as the Phase 3 intake ruling requires."""
    return _load_profile(data)


def load_task_class(data: Any) -> TaskClassIdentity:
    d = _obj(data, "task_class", ("task_class_id", "domain_ref", "intended_outcome_ref", "consequence_class", "reversibility", "evidence_requirement_refs", "tool_requirement_refs",
                                   "structural_characteristics", "population_ref", "benchmark_set_ref", "comparison_policy"))
    pol = _obj(d["comparison_policy"], "task_class.comparison_policy", ("policy_id", "policy_version", "sufficiency_rule_id", "sufficiency_rule_version", "sufficiency_kind", "threshold", "evidence_admission", "resource_dimensions", "quality_aggregation"))
    thr = _obj(pol["threshold"], "task_class.comparison_policy.threshold", ("threshold_id", "unit", "comparator", "literal"))
    literal = _str(thr["literal"], "threshold.literal")
    try:
        Decimal(literal)
    except InvalidOperation:
        raise InputDocumentError("threshold.literal must be a decimal string") from None
    admission = pol["evidence_admission"]
    adm = None
    if admission is not None:
        a = _obj(admission, "task_class.comparison_policy.evidence_admission", ("authority_identity", "authority_result_ref", "admitted_digest"))
        adm = EvidenceAdmissionRef(_str(a["authority_identity"], "authority_identity"), _str(a["authority_result_ref"], "authority_result_ref"), _digest(a["admitted_digest"], "admitted_digest"))
    rule = SufficiencyRule(_str(pol["sufficiency_rule_id"], "sufficiency_rule_id"), _str(pol["sufficiency_rule_version"], "sufficiency_rule_version"), _enum(SufficiencyKind, pol["sufficiency_kind"], "sufficiency_kind"),
                           GovernedThreshold(_str(thr["threshold_id"], "threshold_id"), _str(thr["unit"], "unit"), _enum(ComparisonOperator, thr["comparator"], "comparator"), literal), adm)
    dims = tuple(_enum(ResourceDimension, x, "resource_dimensions item") for x in _str_list(pol["resource_dimensions"], "resource_dimensions"))
    policy = ComparisonPolicy(_str(pol["policy_id"], "policy_id"), _str(pol["policy_version"], "policy_version"), rule, dims, load_aggregation(pol["quality_aggregation"], "quality_aggregation"))
    return _TaskClassBuilder(d, policy).build


class _TaskClassBuilder:
    """Defers construction so the benchmark manifest digest (computed by prepare) can be bound."""

    def __init__(self, d: Mapping[str, Any], policy: ComparisonPolicy) -> None:
        self.d, self.policy = d, policy

    def build(self, benchmark_manifest_digest: str) -> TaskClassIdentity:
        d = self.d
        return TaskClassIdentity(
            TASK_CLASS_SCHEMA_VERSION, _str(d["task_class_id"], "task_class_id"), _str(d["domain_ref"], "domain_ref"), _str(d["intended_outcome_ref"], "intended_outcome_ref"),
            _enum(ConsequenceClass, d["consequence_class"], "consequence_class"), _enum(TaskReversibility, d["reversibility"], "reversibility"),
            _str_list(d["evidence_requirement_refs"], "evidence_requirement_refs"), _str_list(d["tool_requirement_refs"], "tool_requirement_refs"),
            _str_list(d["structural_characteristics"], "structural_characteristics"), _str(d["population_ref"], "population_ref"),
            _str(d["benchmark_set_ref"], "benchmark_set_ref"), benchmark_manifest_digest, self.policy,
        )


def load_aggregation(data: Any, name: str = "aggregation") -> AggregationRef:
    d = _obj(data, name, ("aggregation_method_id", "aggregation_method_version", "calculation_ref"))
    return AggregationRef(_str(d["aggregation_method_id"], f"{name}.aggregation_method_id"), _str(d["aggregation_method_version"], f"{name}.aggregation_method_version"), _str(d["calculation_ref"], f"{name}.calculation_ref"))


def load_aggregations(data: Any) -> Tuple[AggregationRef, AggregationRef]:
    d = _obj(data, "aggregation", ("resource_aggregation", "quality_aggregation"))
    return load_aggregation(d["resource_aggregation"], "resource_aggregation"), load_aggregation(d["quality_aggregation"], "quality_aggregation")


def load_binding(data: Any) -> BindingRef:
    d = _obj(data, "binding", ("binding_id", "configuration_id", "configuration_digest", "context_digest", "binding_digest"))
    return BindingRef(_str(d["binding_id"], "binding_id"), _str(d["configuration_id"], "configuration_id"), _digest(d["configuration_digest"], "configuration_digest"), _digest(d["context_digest"], "context_digest"), _digest(d["binding_digest"], "binding_digest"))


def load_cases(data: Any) -> Tuple[Dict[str, Any], ...]:
    """Workflow-visible case inputs only: case_id, query, context. Expected answers live in a
    separate document (load_expected) and never enter the workflow."""
    d = _obj(data, "cases", ("cases",))
    items = d["cases"]
    if not isinstance(items, list) or not items:
        raise InputDocumentError("cases.cases must be a non-empty JSON array")
    out: List[Dict[str, Any]] = []
    seen = set()
    for i, c in enumerate(items):
        cd = _obj(c, f"cases.cases[{i}]", ("case_id", "query", "context"))
        cid = _str(cd["case_id"], "case_id")
        if cid in seen:
            raise InputDocumentError(f"duplicate case_id {cid!r}")
        seen.add(cid)
        out.append({"case_id": cid, "query": _str(cd["query"], "query"), "context": _str(cd["context"], "context", blank_ok=True)})
    return tuple(out)


def load_expected(data: Any, case_ids: Tuple[str, ...]) -> Dict[str, str]:
    d = _obj(data, "expected", ("expected",))
    exp = d["expected"]
    if not isinstance(exp, Mapping):
        raise InputDocumentError("expected.expected must be a JSON object keyed by case_id")
    if set(exp) != set(case_ids):
        raise InputDocumentError("expected answers must cover exactly the case ids")
    return {k: _str(v, f"expected[{k}]") for k, v in exp.items()}


def load_provider_reference(data: Any) -> Tuple[str, str]:
    """(provider_factory dotted path, provider_ref label). Credentials are never part of this document."""
    d = _obj(data, "provider", ("provider_factory", "provider_ref"))
    f = _str(d["provider_factory"], "provider_factory")
    if not _FACTORY.match(f):
        raise InputDocumentError("provider_factory must be 'package.module:function'")
    return f, _str(d["provider_ref"], "provider_ref")


def load_evaluator(data: Any, *, scoring_instruction_digest: str, benchmark_manifest_digest: str) -> QualityEvaluatorDeclaration:
    d = _obj(data, "evaluator", ("evaluator_identity", "evaluator_version", "kind", "model_ref", "separation_declaration_ref", "calibration_evidence_ref"))
    kind = _enum(EvaluatorKind, d["kind"], "kind")
    model_ref = d["model_ref"]
    if model_ref is not None:
        _str(model_ref, "model_ref")
    calibration = d["calibration_evidence_ref"]
    if calibration is not None:
        _str(calibration, "calibration_evidence_ref")
    return QualityEvaluatorDeclaration(_str(d["evaluator_identity"], "evaluator_identity"), _str(d["evaluator_version"], "evaluator_version"), kind, model_ref,
                                       _str(d["separation_declaration_ref"], "separation_declaration_ref"), scoring_instruction_digest, benchmark_manifest_digest, calibration if calibration is not None else "")


def load_boundary(data: Any) -> CaptureBoundaryDeclaration:
    d = _obj(data, "boundary", ("boundary_identity", "boundary_version", "process_separation_ref", "port_ref", "allowed_attested_fields"))
    fields = _str_list(d["allowed_attested_fields"], "allowed_attested_fields")
    if not set(fields) <= set(ATTESTABLE_TELEMETRY_FIELDS):
        raise InputDocumentError("allowed_attested_fields outside ATTESTABLE_TELEMETRY_FIELDS")
    return CaptureBoundaryDeclaration(_str(d["boundary_identity"], "boundary_identity"), _str(d["boundary_version"], "boundary_version"), _str(d["process_separation_ref"], "process_separation_ref"), _str(d["port_ref"], "port_ref"), fields)


def load_identity(data: Any) -> PilotIdentity:
    d = _obj(data, "identity", ("tenant_id", "subject_id", "record_issuer_identity", "requester_identity", "model_ref"))
    return PilotIdentity(*(_str(d[k], k) for k in ("tenant_id", "subject_id", "record_issuer_identity", "requester_identity", "model_ref")))


def load_instants(data: Any) -> Dict[str, datetime]:
    d = _obj(data, "instants", ("preregistered_at", "run_started_at", "issued_at"))
    return {k: _instant(d[k], k) for k in ("preregistered_at", "run_started_at", "issued_at")}


def load_plan_fields(data: Any) -> Dict[str, str]:
    d = _obj(data, "plan", ("manifest_id", "plan_id", "baseline_method_id", "preregistered_by", "sampling_policy_ref", "declared_coverage_ref", "benchmark_id", "benchmark_version", "benchmark_issuer_ref", "benchmark_issuer_identity"))
    return {k: _str(v, k) for k, v in d.items()}


__all__ = [
    "InputDocumentError", "CREDENTIAL_KEYS", "load_profile", "load_task_class", "load_aggregation", "load_aggregations", "load_binding", "load_cases", "load_expected",
    "load_provider_reference", "load_evaluator", "load_boundary", "load_identity", "load_instants", "load_plan_fields",
]
