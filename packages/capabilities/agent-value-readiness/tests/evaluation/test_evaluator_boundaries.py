"""Boundary invariants: what the GV-3R-b evaluator must never do.

Evidence classification, financial neutrality, clock independence, composite
non-influence, and the absence of any deployment authorization.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
from decimal import Decimal

import pytest

from ugence_governance_contracts.api import (
    AttestationStatus,
    AttributionStatus,
    SourceBasis,
    VerificationStatus,
)
from ugence_agent_value_readiness.api import (
    AdvisoryComposite,
    GateStatus,
    ReadinessAdvisoryCode,
    ReadinessClassification,
    ReadinessEvaluationCase,
    ReadinessEvaluationResult,
    ReadinessEvaluationTrace,
    evaluate_readiness,
)
import ugence_agent_value_readiness as R
from ugence_agent_value_readiness import evaluation as EV

from _fixtures import (  # noqa: E402
    CONDITIONAL,
    MANDATORY,
    NOW,
    PILOT,
    case,
    condition,
    gate,
    gate_result,
    readiness_policy,
)

PASS = GateStatus.PASS
FAIL = GateStatus.FAIL
CLS = ReadinessClassification
EVAL_SRC = pathlib.Path(EV.__file__).resolve().parent


def run(c, when=NOW):
    return evaluate_readiness(c, evaluation_time=when)


def _sources():
    return sorted(EVAL_SRC.rglob("*.py"))


# --------------------------------------------------------------------------- #
# Evidence classification is preserved, never elevated
# --------------------------------------------------------------------------- #
def test_evidence_axes_survive_evaluation_unchanged():
    p = readiness_policy([gate("m1", MANDATORY)])
    c = case(policy=p, gate_results=[gate_result(p, "m1", PASS)])
    before = c.intelligence_results[0].claim
    r = run(c)
    after = r.determination.intelligence_results[0].claim
    assert after is before
    assert after.source_basis is SourceBasis.REPORTED
    assert after.attestation_status is AttestationStatus.UNATTESTED
    assert after.attribution_status is AttributionStatus.NOT_APPLICABLE
    assert after.verification_status is VerificationStatus.UNVERIFIED


def test_a_high_tier_does_not_upgrade_evidence():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    assert r.classification is CLS.DEPLOYMENT_READY
    for group in (r.determination.intelligence_results,
                  r.determination.capability_results,
                  r.determination.adoption_results):
        for result in group:
            assert result.claim.verification_status is VerificationStatus.UNVERIFIED
            assert result.claim.source_basis is SourceBasis.REPORTED
    assert ReadinessAdvisoryCode.EVIDENCE_CLASSIFICATION_PRESERVED.value in r.advisory_codes


def test_evaluator_never_constructs_or_relabels_evidence():
    """No evidence type is instantiated anywhere in the evaluator."""

    forbidden = {"MetricClaim", "MetricObservation", "EvidenceProvenance", "EvidenceReference"}
    offenders = {}
    for path in _sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in forbidden:
                    offenders.setdefault(path.name, set()).add(node.func.id)
    assert not offenders, offenders


# --------------------------------------------------------------------------- #
# The advisory composite can never move the tier
# --------------------------------------------------------------------------- #
def _composite(score):
    return AdvisoryComposite(
        method_id="m", method_version="1", score=Decimal(score),
        scale_min=Decimal("0"), scale_max=Decimal("100"),
        component_result_refs=("ir1", "cr1", "ar1"),
    )


@pytest.mark.parametrize(
    "gates,expected",
    [
        ([("m1", MANDATORY, FAIL)], CLS.NOT_READY),
        ([("m1", MANDATORY, PASS)], CLS.DEPLOYMENT_READY),
        ([("m1", MANDATORY, GateStatus.INDETERMINATE)], CLS.NOT_ASSESSABLE),
    ],
)
def test_composite_min_and_max_produce_the_same_classification(gates, expected):
    p = readiness_policy([gate(gid, kind) for gid, kind, _ in gates])
    results = [gate_result(p, gid, status) for gid, _, status in gates]

    low = run(case(policy=p, gate_results=results, composite=_composite("0")))
    high = run(case(policy=p, gate_results=results, composite=_composite("100")))

    assert low.classification is expected and high.classification is expected
    assert low.rule_id == high.rule_id
    assert low.reason_codes == high.reason_codes
    assert low.trace.mandatory_failure_gate_ids == high.trace.mandatory_failure_gate_ids


def test_composite_cannot_rescue_an_uncovered_conditional_concern():
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "c1", FAIL)], composite=_composite("100")))
    assert r.classification is CLS.NOT_READY


def test_composite_is_carried_through_unchanged():
    p = readiness_policy([gate("m1", MANDATORY)])
    comp = _composite("42")
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)], composite=comp))
    assert r.determination.advisory_composite is comp
    assert r.determination.advisory_composite.score == Decimal("42")
    assert r.trace.advisory_composite_carried is True
    assert ReadinessAdvisoryCode.COMPOSITE_CARRIED_NOT_USED_IN_SELECTION.value in r.advisory_codes


def test_composite_is_absent_from_the_trace_decision_inputs():
    """The trace records that a composite existed, never a score used to decide."""

    fields = {f.name for f in dataclasses.fields(ReadinessEvaluationTrace)}
    assert "advisory_composite" not in fields
    assert not any("score" in f for f in fields)


# --------------------------------------------------------------------------- #
# No system clock
# --------------------------------------------------------------------------- #
def test_evaluator_never_reads_the_system_clock():
    banned_attrs = {"now", "utcnow", "today", "time", "monotonic", "time_ns"}
    offenders = {}
    for path in _sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in banned_attrs:
                    offenders.setdefault(path.name, set()).add(node.func.attr)
    assert not offenders, offenders


def test_evaluator_imports_no_clock_module():
    allowed = {"__future__", "hashlib", "json", "contextlib", "dataclasses", "datetime",
               "typing", "enum", "ugence_uvi_policy_contracts", "ugence_agent_value_readiness"}
    strays = {}
    for path in _sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            roots = set()
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                roots = {node.module.split(".")[0]}
            for r in roots - allowed:
                strays.setdefault(path.name, set()).add(r)
    assert not strays, strays
    # `time` is never imported at all, so no clock is reachable.


def test_supplied_time_is_the_only_temporal_input():
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    c = case(policy=p, gate_results=[gate_result(p, "c1", FAIL)],
             conditions=[condition("cond-1", "c1")])
    r = run(c)
    assert r.determination.created_at == NOW
    assert r.trace.evaluation_time == NOW


# --------------------------------------------------------------------------- #
# Non-financial, non-authorizing
# --------------------------------------------------------------------------- #
#: Financial concepts, matched as whole ``snake_case`` parts so that an innocent
#: substring (``evaluation_time`` contains "valuation") is not a false positive.
_FINANCIAL_WORDS = {
    "money", "currency", "roi", "benefit", "cost", "revenue", "multiplier",
    "price", "profit", "payback", "npv", "valuation", "forecast", "monetary",
}


def test_no_financial_field_on_any_evaluation_type():
    for shape in (ReadinessEvaluationCase, ReadinessEvaluationTrace, ReadinessEvaluationResult):
        for f in dataclasses.fields(shape):
            parts = set(f.name.lower().split("_"))
            assert not (parts & _FINANCIAL_WORDS), (shape.__name__, f.name)


def test_no_financial_or_governed_value_symbol_in_the_evaluator():
    offenders = {}
    for path in _sources():
        text = path.read_text()
        for token in ("Money", "governed_value", "ugence_governed_value", "ValuationPolicy"):
            if token in text:
                offenders.setdefault(path.name, set()).add(token)
    assert not offenders, offenders


def test_no_evaluation_field_implies_authorization():
    banned = ("authoriz", "approve", "permit", "grant", "allow")
    for shape in (ReadinessEvaluationCase, ReadinessEvaluationTrace, ReadinessEvaluationResult):
        for f in dataclasses.fields(shape):
            low = f.name.lower()
            assert not any(token in low for token in banned), (shape.__name__, f.name)


@pytest.mark.parametrize(
    "gates,target,expected",
    [
        ([("m1", MANDATORY, PASS)], None, CLS.DEPLOYMENT_READY),
        ([("m1", MANDATORY, FAIL)], None, CLS.NOT_READY),
        ([("m1", MANDATORY, GateStatus.INDETERMINATE)], None, CLS.NOT_ASSESSABLE),
    ],
)
def test_every_result_is_advisory_and_authorizes_nothing(gates, target, expected):
    p = readiness_policy([gate(gid, kind) for gid, kind, _ in gates])
    r = run(case(policy=p, gate_results=[gate_result(p, gid, s) for gid, _, s in gates]))
    assert r.classification is expected
    assert r.is_advisory is True
    assert r.authorizes_deployment is False
    assert r.determination.is_advisory is True
    assert ReadinessAdvisoryCode.ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION.value in r.advisory_codes


def test_standing_advisories_are_present_on_every_result():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    for code in (
        ReadinessAdvisoryCode.ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION,
        ReadinessAdvisoryCode.POLICY_AUTHENTICITY_NOT_VERIFIED,
        ReadinessAdvisoryCode.GATE_STATUS_STRUCTURALLY_SUPPLIED,
        ReadinessAdvisoryCode.EVIDENCE_CLASSIFICATION_PRESERVED,
        ReadinessAdvisoryCode.READINESS_IS_LEADING_INDICATOR_ONLY,
    ):
        assert code.value in r.advisory_codes
        assert code.value in r.determination.reason_codes


def test_condition_authenticity_advisories_appear_only_with_conditions():
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    without = run(case(policy=p, gate_results=[gate_result(p, "c1", PASS)]))
    with_ = run(case(policy=p, gate_results=[gate_result(p, "c1", FAIL)],
                     conditions=[condition("cond-1", "c1")]))
    code = ReadinessAdvisoryCode.CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED.value
    scope = ReadinessAdvisoryCode.CONDITION_SCOPE_NOT_TENANT_BOUND.value
    assert code not in without.advisory_codes
    assert code in with_.advisory_codes and scope in with_.advisory_codes


# --------------------------------------------------------------------------- #
# One canonical path, one trace
# --------------------------------------------------------------------------- #
def test_only_one_public_entry_point_selects_a_classification():
    callables = [
        name for name in R.api.__all__
        if callable(getattr(R.api, name)) and not isinstance(getattr(R.api, name), type)
    ]
    assert callables == ["evaluate_readiness"]


def test_trace_is_explanatory_and_bound_to_its_determination():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    assert r.trace.is_explanatory_only is True
    assert r.trace.classification is r.determination.classification
    assert r.trace.requested_target is r.determination.requested_target
    assert r.trace.input_digest == r.determination.evidence_digest
    assert len(r.trace.input_digest) == 64
    assert r.trace.evaluator_id and r.trace.formula_version == "GV-3R-b.2"


def test_pilot_and_production_traces_report_the_same_gate_inventory_shape():
    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY, applicability=(PILOT,))])
    prod = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    assert prod.trace.applicable_gate_ids == ("m1",)
    assert prod.trace.diagnostic_gate_ids == ("m2",)


def test_package_version_is_bumped():
    assert R.__version__ == "0.2.0"
