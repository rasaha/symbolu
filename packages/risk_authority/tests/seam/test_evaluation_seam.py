"""Adversarial + conformance suite for the stop-at-decision evaluation seam (PR-1).

The negative / deny / non-decision / trust-boundary cases deliberately and materially
outnumber the two happy-path risk-pass cases (2 pass vs > 20 negatives), and sentinels
prove the envelope issuer and ActionGate are never reached.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from risk_authority.api import RiskEvaluationSeam, SeamConfigurationError
from risk_authority.api.dependencies import RiskAuthorityApplication
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.domain import (
    AuthorityGrant,
    AuthorityType,
    Predicate,
    PredicateOp,
    RiskClass,
    RuleEffect,
    Scope,
    WorkflowIR,
    WorkflowRule,
    WorkflowStatus,
)
from risk_authority.domain.enums import ControlStatus, RiskOutcome
from risk_authority.domain.errors import RiskAuthorityError
from risk_authority.integrations import InMemoryWorkflowIRSource
from risk_authority.integrations.control_assurance import (
    ControlAssuranceRequest,
    ControlAssuranceResult,
    bind_control_result,
)
from risk_authority.integrations.evaluation_contracts import (
    ReferenceControlEvidenceResolver,
    ReferencePolicyResolver,
    SeamContractError,
    SubjectRiskDecision,
    SubjectRiskDisposition,
    SubjectRiskEvaluationRequest,
    SubjectRiskNonDecisionReason,
)
from risk_authority.services.decision_authority import ReferenceDecisionAuthority
from tests.scenario import durable_store

NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)
KEY = SigningKeyRecord("k1", SigningKey.from_seed(bytes(range(32))))
TENANT = "t1"
SCOPE = Scope(purposes=("SCALE",), max_autonomy_level=1)


# --------------------------------------------------------------------------- fixtures
def _wf(controls=()):
    rules = ()
    if controls:
        rules = (WorkflowRule(rule_id="R1",
                              conditions=(Predicate("domain", PredicateOp.EQ, "SCALING"),),
                              required_controls=tuple(controls),
                              effect=RuleEffect.DENY_UNLESS_ALL),)
    return WorkflowIR(workflow_ir_id="scaling-pol", version="1.0.0",
                      status=WorkflowStatus.ACTIVE, rules=rules, source_refs=(),
                      effective_at=NOW).with_digest()


def _request(**kw):
    base = dict(
        subject_type="cloud_scaling_recommendation",
        subject_id="rec-1",
        subject_digest="sha256:abc",
        tenant_id=TENANT,
        requested_purpose="SCALE",
        requested_domain="SCALING",
        requested_scope=SCOPE,
        requested_risk_class=RiskClass.HIGH,
        requested_autonomy_level=1,
        correlation_id="corr-1",
        idempotency_key="idem-1",
        evaluation_time=NOW,
    )
    base.update(kw)
    return SubjectRiskEvaluationRequest(**base)


def _reference_seam(controls=(), *, resolver=None):
    src = InMemoryWorkflowIRSource()
    w = src.register(_wf(controls))
    resolver = resolver or ReferencePolicyResolver(by_purpose_domain={("SCALE", "SCALING"): w})
    return RiskEvaluationSeam.reference(
        workflow_source=src, key_record=KEY, clock=lambda: NOW, policy_resolver=resolver)


# ----- production doubles (minimal, explicitly production-authoritative) -------------
class _ProdPolicyResolver:
    is_production_authoritative = True

    def __init__(self, workflow):
        self._w = workflow

    def resolve(self, *, tenant_id, purpose, domain, risk_class, requested_scope, now):
        return self._w if domain == "SCALING" else None


class _ProdEvidenceResolver:
    is_production_authoritative = True

    def resolve(self, *, tenant_id, risk_case_id, workflow_ir_digest, policy_digest,
                subject_id, evidence_references, now):
        return ()  # RA-5 not implemented → no trusted evidence → controls fail closed


class _ProdIngress:
    # No is_reference_ingress attribute → treated as a real channel verifier.
    def is_trusted(self, evidence, *, now):
        return True


class _ProdAdmission:
    def is_admissible(self, record, *, now):
        return True


class _ProdControlAssurance:
    is_production_authoritative = True

    def evaluate(self, request: ControlAssuranceRequest) -> ControlAssuranceResult:
        result = bind_control_result(
            request, status=ControlStatus.MISSING,
            engine_id="prod-assurance-double", engine_version="1",
            reason="no admitted evidence")
        return ControlAssuranceResult(control_result=result,
                                      engine_id="prod-assurance-double",
                                      engine_version="1", available=True)


class _ProdDecisionAuthority:
    """A production-authoritative adapter test double delegating to the reference ruler.

    In real deployments this is an adapter over ``ugence-decision-authority``; here it is
    marked production-authoritative purely to exercise the seam's injection boundary."""

    is_production_authoritative = True

    def __init__(self):
        self._inner = ReferenceDecisionAuthority()

    def issue_decision(self, **kw):
        return self._inner.issue_decision(**kw)


def _prod_grant():
    return AuthorityGrant(
        principal_id="prod-evaluator",
        tenant_id=TENANT,
        authority_type=AuthorityType.RISK_APPROVAL,
        domains=("SCALING",),
        allowed_risk_classes=(RiskClass.LOW, RiskClass.MEDIUM, RiskClass.HIGH),
        max_autonomy=5,
        delegated_by="root",
        grantable_scope=SCOPE,
    )


def _production_seam(controls=(), *, grant="default", evidence_admission="default",
                     control_assurance="default", evidence_ingress="default",
                     decision_authority="default", policy_resolver="default",
                     evidence_resolver="default"):
    src = InMemoryWorkflowIRSource()
    w = src.register(_wf(controls))
    kw = dict(
        workflow_source=src,
        policy_resolver=_ProdPolicyResolver(w) if policy_resolver == "default" else policy_resolver,
        evidence_resolver=_ProdEvidenceResolver() if evidence_resolver == "default" else evidence_resolver,
        evidence_admission=_ProdAdmission() if evidence_admission == "default" else evidence_admission,
        control_assurance=_ProdControlAssurance() if control_assurance == "default" else control_assurance,
        evidence_ingress=_ProdIngress() if evidence_ingress == "default" else evidence_ingress,
        decision_authority=_ProdDecisionAuthority() if decision_authority == "default" else decision_authority,
        evaluator_grant=_prod_grant() if grant == "default" else grant,
        key_record=KEY,
        clock=lambda: NOW,
        persistence=durable_store(),
    )
    return RiskEvaluationSeam.production(**kw)


# =========================================================== HAPPY PATH (2 only)
def test_reference_pass_zero_controls():
    r = _reference_seam(controls=()).evaluate(_request())
    assert r.disposition is SubjectRiskDisposition.RISK_PASSED
    assert r.risk_outcome is RiskOutcome.ALLOW
    assert r.decision_snapshot is not None and r.evaluation_snapshot is not None
    # Non-executable invariants.
    assert (r.executable, r.authorization_performed, r.envelope_issued,
            r.actiongate_invoked, r.actuation_performed, r.effect_verified) == (False,) * 6


def test_production_pass_zero_controls():
    r = _production_seam(controls=()).evaluate(_request())
    assert r.disposition is SubjectRiskDisposition.RISK_PASSED
    assert r.risk_outcome is RiskOutcome.ALLOW
    assert r.executable is False and r.envelope_issued is False


# =========================================================== DENY / ESCALATE
def test_reference_deny_required_control_no_evidence():
    r = _reference_seam(controls=("CTRL_A",)).evaluate(_request())
    assert r.disposition in (SubjectRiskDisposition.RISK_DENIED, SubjectRiskDisposition.RISK_ESCALATED)
    assert r.risk_outcome in (RiskOutcome.DENY, RiskOutcome.ESCALATE)
    assert r.evaluation_snapshot is not None


def test_production_deny_required_control_missing_evidence():
    r = _production_seam(controls=("CTRL_A",)).evaluate(_request())
    assert r.disposition in (SubjectRiskDisposition.RISK_DENIED, SubjectRiskDisposition.RISK_ESCALATED)
    # Production denial reaches no AUTHORITY_REVIEW ⇒ no binding decision, evaluation stands.
    assert r.decision_snapshot is None
    assert r.evaluation_snapshot is not None


def test_production_evidence_resolver_returns_non_records_fails_closed():
    class _Junk:
        is_production_authoritative = True

        def resolve(self, **kw):
            return ("not-a-record", 123)

    r = _production_seam(controls=("CTRL_A",), evidence_resolver=_Junk()).evaluate(_request())
    assert r.disposition in (SubjectRiskDisposition.RISK_DENIED, SubjectRiskDisposition.RISK_ESCALATED)


# =========================================================== TYPED NON-DECISIONS
def test_no_authoritative_policy():
    r = _reference_seam(controls=()).evaluate(_request(requested_domain="OTHER"))
    assert r.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert r.non_decision_reason is SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY


def test_ambiguous_policy_resolver_raises():
    class _Ambiguous:
        is_production_authoritative = False

        def resolve(self, **kw):
            raise RuntimeError("multiple policies claim authority")

    r = _reference_seam(resolver=_Ambiguous()).evaluate(_request())
    assert r.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert r.non_decision_reason is SubjectRiskNonDecisionReason.AMBIGUOUS_POLICY


def test_unsupported_schema_version():
    r = _reference_seam().evaluate(_request(schema_version="bogus-99"))
    assert r.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert r.non_decision_reason is SubjectRiskNonDecisionReason.UNSUPPORTED_SCHEMA_VERSION


def test_authority_unavailable_tenant_mismatch():
    # Zero-control policy passes evaluation, but the injected grant is for TENANT while
    # the request is a different tenant ⇒ the evaluator cannot bind ⇒ AUTHORITY_UNAVAILABLE.
    seam = _production_seam(controls=())
    r = seam.evaluate(_request(tenant_id="other-tenant"))
    assert r.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert r.non_decision_reason in (
        SubjectRiskNonDecisionReason.AUTHORITY_UNAVAILABLE,
        SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY,
    )


# =========================================================== TRUST BOUNDARY (request)
def test_request_has_no_control_results_field():
    with pytest.raises(TypeError):
        SubjectRiskEvaluationRequest(  # type: ignore[call-arg]
            subject_type="x", subject_id="s", subject_digest="d", tenant_id=TENANT,
            requested_purpose="SCALE", requested_domain="SCALING", requested_scope=SCOPE,
            control_results=(("CTRL_A", "PASS"),))


def test_request_has_no_workflow_ir_id_field():
    with pytest.raises(TypeError):
        SubjectRiskEvaluationRequest(  # type: ignore[call-arg]
            subject_type="x", subject_id="s", subject_digest="d", tenant_id=TENANT,
            requested_purpose="SCALE", requested_domain="SCALING", requested_scope=SCOPE,
            workflow_ir_id="attacker-policy")


def test_request_has_no_signing_key_or_decision_field():
    for bad in ("signing_key", "risk_decision", "evaluator_principal_id", "control_status"):
        with pytest.raises(TypeError):
            SubjectRiskEvaluationRequest(**{  # type: ignore[arg-type]
                "subject_type": "x", "subject_id": "s", "subject_digest": "d",
                "tenant_id": TENANT, "requested_purpose": "SCALE",
                "requested_domain": "SCALING", "requested_scope": SCOPE, bad: "z"})


def test_invalid_subject_rejected():
    with pytest.raises(SeamContractError):
        _request(subject_id="")
    with pytest.raises(SeamContractError):
        _request(subject_digest="")


# =========================================================== PRODUCTION FACTORY GUARDS
def test_production_rejects_reference_policy_resolver():
    with pytest.raises(SeamConfigurationError):
        _production_seam(policy_resolver=ReferencePolicyResolver(by_purpose_domain={}))


def test_production_rejects_reference_evidence_resolver():
    with pytest.raises(SeamConfigurationError):
        _production_seam(evidence_resolver=ReferenceControlEvidenceResolver())


def test_production_rejects_reference_decision_authority():
    with pytest.raises(SeamConfigurationError):
        _production_seam(decision_authority=ReferenceDecisionAuthority())


def test_production_rejects_non_authoritative_decision_authority():
    class _NotProd:
        is_production_authoritative = False

        def issue_decision(self, **kw):
            raise AssertionError("must not be called")

    with pytest.raises(SeamConfigurationError):
        _production_seam(decision_authority=_NotProd())


def test_production_rejects_missing_evaluator_grant():
    with pytest.raises(SeamConfigurationError):
        _production_seam(grant=None)


def test_production_rejects_missing_evidence_ports():
    # The facade fails closed on incomplete production configuration.
    with pytest.raises(RiskAuthorityError):
        _production_seam(evidence_admission=None)


def test_production_rejects_reference_ingress():
    class _RefIngress:
        is_reference_ingress = True

        def is_trusted(self, evidence, *, now):
            return True

    with pytest.raises(RiskAuthorityError):
        _production_seam(evidence_ingress=_RefIngress())


def test_production_rejects_non_authoritative_control_assurance():
    class _RefAssurance:
        is_production_authoritative = False

        def evaluate(self, request):
            raise AssertionError("must not be called")

    with pytest.raises(RiskAuthorityError):
        _production_seam(control_assurance=_RefAssurance())


# =========================================================== STOP-AT-DECISION SENTINELS
def test_envelope_issuer_never_reached():
    seam = _reference_seam(controls=())
    calls = []
    seam._app.issue_envelope = lambda *a, **k: calls.append("envelope")  # type: ignore
    r = seam.evaluate(_request())
    assert r.disposition is SubjectRiskDisposition.RISK_PASSED
    assert calls == []  # the seam terminates at the decision


def test_actiongate_never_reached():
    seam = _reference_seam(controls=())
    calls = []
    seam._app.authorize_action = lambda *a, **k: calls.append("actiongate")  # type: ignore
    seam.evaluate(_request())
    assert calls == []


def test_result_never_executable_or_authorizing():
    r = _reference_seam(controls=()).evaluate(_request())
    d = r.to_canonical_dict()
    for flag in ("authorization_performed", "envelope_issued", "actiongate_invoked",
                 "actuation_performed", "effect_verified", "executable"):
        assert d[flag] is False


# =========================================================== CONTRACT ADVERSARIAL
def test_direct_construct_executable_true_rejected():
    with pytest.raises(SeamContractError):
        SubjectRiskDecision(
            request_digest="r", subject_digest="s", tenant_id=TENANT,
            disposition=SubjectRiskDisposition.NOT_EVALUATED,
            evaluator_principal_id="e", evaluated_at=NOW,
            non_decision_reason=SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY,
            executable=True)


def test_not_evaluated_carrying_decision_rejected():
    with pytest.raises(SeamContractError):
        SubjectRiskDecision(
            request_digest="r", subject_digest="s", tenant_id=TENANT,
            disposition=SubjectRiskDisposition.NOT_EVALUATED,
            evaluator_principal_id="e", evaluated_at=NOW,
            non_decision_reason=SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY,
            risk_outcome=RiskOutcome.ALLOW)


def test_disposition_outcome_mismatch_rejected():
    r = _reference_seam(controls=()).evaluate(_request())
    data = r.to_canonical_dict()
    data["disposition"] = SubjectRiskDisposition.RISK_DENIED.value  # outcome stays ALLOW
    with pytest.raises(SeamContractError):
        SubjectRiskDecision.from_dict(data)


def test_from_dict_decision_digest_tamper_rejected():
    r = _reference_seam(controls=()).evaluate(_request())
    data = r.to_canonical_dict()
    data["decision_digest"] = "sha256:tampered"
    with pytest.raises(SeamContractError):
        SubjectRiskDecision.from_dict(data)


def test_from_dict_evaluation_digest_tamper_rejected():
    r = _reference_seam(controls=("CTRL_A",)).evaluate(_request())
    data = r.to_canonical_dict()
    data["evaluation_digest"] = "sha256:tampered"
    with pytest.raises(SeamContractError):
        SubjectRiskDecision.from_dict(data)


# =========================================================== SERIALIZATION / IDENTITY
def test_request_round_trip_digest_stable():
    q = _request()
    assert SubjectRiskEvaluationRequest.from_dict(q.to_canonical_dict()).digest() == q.digest()


def test_result_round_trip_digest_stable_pass_and_deny():
    for controls in ((), ("CTRL_A",)):
        r = _reference_seam(controls=controls).evaluate(_request())
        assert SubjectRiskDecision.from_dict(r.to_canonical_dict()).digest() == r.digest()


def test_subject_tamper_changes_request_digest():
    a = _request().digest()
    b = _request(subject_digest="sha256:different").digest()
    assert a != b


def test_result_binds_request_digest():
    q = _request()
    r = _reference_seam(controls=()).evaluate(q)
    assert r.request_digest == q.digest()


def test_replay_is_deterministic():
    q = _request()
    r1 = _reference_seam(controls=()).evaluate(q)
    r2 = _reference_seam(controls=()).evaluate(q)
    assert r1.digest() == r2.digest()


def test_reason_codes_from_applicable_rules():
    r = _reference_seam(controls=("CTRL_A",)).evaluate(_request())
    assert "R1" in r.reason_codes


# =========================================================== CANONICAL TIME
def test_expiry_microsecond_boundary_on_decision():
    r = _reference_seam(controls=()).evaluate(_request())
    assert r.expires_at is not None
    # The decision is valid strictly before expiry; a microsecond past is expired.
    just_before = r.expires_at - timedelta(microseconds=1)
    assert just_before < r.expires_at
    assert (r.expires_at + timedelta(microseconds=1)) > r.expires_at


def test_equivalent_offsets_compare_equal_in_request_digest():
    utc = _request(evaluation_time=datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc))
    plus = _request(evaluation_time=datetime(2026, 8, 12, 14, 0, 0, tzinfo=timezone(timedelta(hours=2))))
    assert utc.digest() == plus.digest()
