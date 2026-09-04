"""Audit corrections: production Decision-Authority requirement, envelope/ActionGate
containment, and strict seam serialization.

Group A — construction boundaries; Group B — production authority containment;
Group D — serialization strictness. (Group C seam invariants live in
``test_evaluation_seam.py``.)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from risk_authority.api.dependencies import RiskAuthorityApplication
from risk_authority.api.schemas import AuthorizeActionRequest, IssueEnvelopeRequest
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.domain import Scope, WorkflowIR, WorkflowStatus
from risk_authority.domain.errors import ProductionContainmentError, RiskAuthorityError
from risk_authority.integrations import InMemoryWorkflowIRSource
from risk_authority.integrations.evaluation_contracts import (
    SubjectRiskDecision,
    SubjectRiskDisposition,
    SubjectRiskEvaluationRequest,
    SubjectRiskNonDecisionReason,
    SeamContractError,
)
from risk_authority.services.decision_authority import ReferenceDecisionAuthority
from tests.scenario import durable_store

NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)
KEY = SigningKeyRecord("k1", SigningKey.from_seed(bytes(range(32))))


def _wf():
    return WorkflowIR(workflow_ir_id="w", version="1", status=WorkflowStatus.ACTIVE,
                      rules=(), source_refs=(), effective_at=NOW).with_digest()


def _src():
    s = InMemoryWorkflowIRSource(); s.register(_wf()); return s


class _ProdIngress:
    def is_trusted(self, evidence, *, now): return True


class _ProdAdmission:
    def is_admissible(self, record, *, now): return True


class _ProdControlAssurance:
    is_production_authoritative = True

    def evaluate(self, request):  # pragma: no cover - not reached with zero controls
        raise AssertionError("not reached")


class _ProdDecisionAuthority:
    is_production_authoritative = True

    def __init__(self): self._inner = ReferenceDecisionAuthority()

    def issue_decision(self, **kw): return self._inner.issue_decision(**kw)


def _prod_kwargs(**over):
    kw = dict(
        workflow_source=_src(), key_record=KEY, clock=lambda: NOW,
        evidence_admission=_ProdAdmission(), control_assurance=_ProdControlAssurance(),
        evidence_ingress=_ProdIngress(), decision_authority=_ProdDecisionAuthority(),
        persistence=durable_store(), production_mode=True,
    )
    kw.update(over)
    return kw


# ============================================================ A. CONSTRUCTION BOUNDARIES
def test_production_none_decision_authority_fails_closed():
    with pytest.raises(RiskAuthorityError):
        RiskAuthorityApplication(**_prod_kwargs(decision_authority=None))


def test_production_reference_decision_authority_fails_closed():
    with pytest.raises(RiskAuthorityError):
        RiskAuthorityApplication(**_prod_kwargs(decision_authority=ReferenceDecisionAuthority()))


def test_production_non_authoritative_decision_authority_fails_closed():
    class _NotProd:
        is_production_authoritative = False

        def issue_decision(self, **kw):  # pragma: no cover
            raise AssertionError

    with pytest.raises(RiskAuthorityError):
        RiskAuthorityApplication(**_prod_kwargs(decision_authority=_NotProd()))


def test_reference_mode_no_decision_authority_still_works():
    # production_mode=False keeps the reference ruler available (no injection needed).
    app = RiskAuthorityApplication(workflow_source=_src(), key_record=KEY, clock=lambda: NOW)
    assert isinstance(app._authority_service, ReferenceDecisionAuthority)


def test_production_with_approved_authority_constructs():
    app = RiskAuthorityApplication(**_prod_kwargs())
    assert app._production_mode is True
    assert not isinstance(app._authority_service, ReferenceDecisionAuthority)


# ============================================================ B. PRODUCTION CONTAINMENT
def test_production_issue_envelope_fails_closed():
    app = RiskAuthorityApplication(**_prod_kwargs())
    with pytest.raises(ProductionContainmentError):
        app.issue_envelope("t", "c", IssueEnvelopeRequest(
            decision_id="d", audience="a", session_id="s", nonce="n"))


def test_production_authorize_action_fails_closed():
    app = RiskAuthorityApplication(**_prod_kwargs())
    with pytest.raises(ProductionContainmentError):
        app.authorize_action(AuthorizeActionRequest(
            envelope_id="e", tenant_id="t", actor_id="a", model_id="m", session_id="s",
            action_type="x", target_id="y", purpose="p"))


def test_production_reference_actiongate_never_invoked():
    app = RiskAuthorityApplication(**_prod_kwargs())
    called = []
    app._gate.authorize = lambda *a, **k: called.append("gate")  # type: ignore
    with pytest.raises(ProductionContainmentError):
        app.authorize_action(AuthorizeActionRequest(
            envelope_id="e", tenant_id="t", actor_id="a", model_id="m", session_id="s",
            action_type="x", target_id="y", purpose="p"))
    assert called == []  # containment fires before the reference gate is ever reached


def test_production_issue_envelope_produces_no_signed_artifact():
    app = RiskAuthorityApplication(**_prod_kwargs())
    signed = []
    app._issuer_service.issue = lambda *a, **k: signed.append("env")  # type: ignore
    with pytest.raises(ProductionContainmentError):
        app.issue_envelope("t", "c", IssueEnvelopeRequest(
            decision_id="d", audience="a", session_id="s", nonce="n"))
    assert signed == []  # no signed envelope is minted


# ============================================================ D. SERIALIZATION STRICTNESS
def _request():
    return SubjectRiskEvaluationRequest(
        subject_type="x", subject_id="s", subject_digest="d", tenant_id="t",
        requested_purpose="P", requested_domain="D", requested_scope=Scope(),
        evaluation_time=NOW)


def _not_evaluated_result():
    return SubjectRiskDecision(
        request_digest="r", subject_digest="s", tenant_id="t",
        disposition=SubjectRiskDisposition.NOT_EVALUATED,
        evaluator_principal_id="e", evaluated_at=NOW,
        non_decision_reason=SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY)


def test_request_from_dict_rejects_unknown_field():
    data = _request().to_canonical_dict()
    data["attacker_control_pass"] = True
    with pytest.raises(SeamContractError):
        SubjectRiskEvaluationRequest.from_dict(data)


def test_request_from_dict_requires_schema_version():
    data = _request().to_canonical_dict()
    del data["schema_version"]
    with pytest.raises(SeamContractError):
        SubjectRiskEvaluationRequest.from_dict(data)


def test_result_from_dict_rejects_unknown_field():
    data = _not_evaluated_result().to_canonical_dict()
    data["forged_authority"] = "yes"
    with pytest.raises(SeamContractError):
        SubjectRiskDecision.from_dict(data)


def test_result_from_dict_requires_schema_version():
    data = _not_evaluated_result().to_canonical_dict()
    del data["schema_version"]
    with pytest.raises(SeamContractError):
        SubjectRiskDecision.from_dict(data)


def test_result_from_dict_forged_executable_flag_rejected():
    data = _not_evaluated_result().to_canonical_dict()
    data["executable"] = True  # a forged execution-capability claim
    with pytest.raises(SeamContractError):
        SubjectRiskDecision.from_dict(data)


def test_request_from_dict_parity_and_digest_stable():
    q = _request()
    rebuilt = SubjectRiskEvaluationRequest.from_dict(q.to_canonical_dict())
    assert rebuilt == q and rebuilt.digest() == q.digest()


def test_result_from_dict_parity_not_evaluated():
    r = _not_evaluated_result()
    rebuilt = SubjectRiskDecision.from_dict(r.to_canonical_dict())
    assert rebuilt.digest() == r.digest()
