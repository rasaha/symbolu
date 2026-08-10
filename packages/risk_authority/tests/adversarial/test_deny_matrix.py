"""Adversarial / negative conformance (spec §33.2, user brief §24).

The deny battery: UNKNOWN, STALE, wrong tenant/actor/model, expired, tampered
signature, expanded scope, changed payload, revocation, replay, unknown key.
Per the brief, denial tests deliberately outnumber approval tests.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from risk_authority.crypto import KeyRing, SigningKey
from risk_authority.domain import (
    ActionGateDecision,
    RiskAuthorityError,
    RiskCaseState,
    RiskOutcome,
    Scope,
)
from risk_authority.integrations import ReferenceActionGate, RuntimeIdentity
from risk_authority.services import RevocationState

from tests.scenario import (
    ACTOR,
    FINANCE_SCOPE,
    FIXED_NOW,
    MODEL,
    PRINCIPAL,
    TENANT,
    action_request,
    approved_envelope,
    build_application,
)
from risk_authority.api import (
    ControlResultInput,
    CreateCaseRequest,
    DecisionRequest,
    EvaluateRequest,
    IssueEnvelopeRequest,
)
from risk_authority.domain import RiskClass

BLOCK = ActionGateDecision.DENIED


def _d(app, envelope, **kw):
    return app.authorize_action(action_request(envelope, **kw)).decision


# ---------------------------------------------------------------------------
# Evidence / control-state denials (fail closed; no envelope may issue).
# ---------------------------------------------------------------------------
def _drive_to_decision(app, control_status: str, *, case_id="rdc_x"):
    app.create_case(
        CreateCaseRequest(
            tenant_id=TENANT, case_id=case_id, subject_id=ACTOR, model_id=MODEL,
            purpose="CUSTOMER_REFUND_REVIEW", domain="FINANCE", jurisdictions=("US",),
            tools=("crm.read", "refund.prepare"), autonomy_level=2,
            data_classes=("CUSTOMER_PII",), workflow_ir_id="finance-ai-risk",
            inherent_risk=RiskClass.HIGH, residual_risk=RiskClass.MEDIUM,
        )
    )
    evaluation = app.evaluate(
        TENANT, case_id,
        EvaluateRequest(control_results=(
            ControlResultInput("MODEL_PROVENANCE_VALID", "PASS"),
            ControlResultInput("HUMAN_OVERSIGHT_VALID", "PASS"),
            ControlResultInput("BIAS_EVALUATION_CURRENT", control_status),
        )),
    )
    decision = app.issue_decision(
        TENANT, case_id, evaluation,
        DecisionRequest(principal_id=PRINCIPAL, requested_scope=FINANCE_SCOPE),
    )
    return evaluation, decision


def test_deny_on_unknown_control():
    app = build_application()
    evaluation, decision = _drive_to_decision(app, "UNKNOWN")
    assert decision.outcome is RiskOutcome.DENY
    assert app.cases.get(TENANT, "rdc_x").state is RiskCaseState.DENIED
    with pytest.raises(RiskAuthorityError):
        app.issue_envelope(
            TENANT, "rdc_x",
            IssueEnvelopeRequest(decision_id=decision.decision_id,
                                 audience="rt", session_id="s", nonce="n"),
        )


def test_deny_on_missing_control():
    app = build_application()
    evaluation, decision = _drive_to_decision(app, "MISSING")
    assert decision.outcome is RiskOutcome.DENY


def test_deny_on_stale_control():
    # A BIAS_EVALUATION that is FAIL/STALE cannot be compensated by other PASSes.
    app = build_application()
    evaluation, decision = _drive_to_decision(app, "STALE")
    assert decision.outcome is RiskOutcome.DENY


# ---------------------------------------------------------------------------
# Runtime binding denials (envelope valid, action off-scope / mis-bound).
# ---------------------------------------------------------------------------
def test_deny_wrong_tenant_replay():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    assert _d(app, envelope, action_type="crm.read", tenant_id="tenant_999") is BLOCK


def test_deny_wrong_actor():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    assert _d(app, envelope, action_type="crm.read", actor_id="agent_intruder") is BLOCK


def test_deny_wrong_model():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    assert _d(app, envelope, action_type="crm.read", model_id="model_swapped") is BLOCK


def test_deny_wrong_session():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    assert _d(app, envelope, action_type="crm.read", session_id="sess_other") is BLOCK


def test_deny_expired_envelope():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    app._clock = lambda: FIXED_NOW + timedelta(hours=2)
    assert _d(app, envelope, action_type="crm.read") is BLOCK


def test_deny_prohibited_data_class():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    assert _d(app, envelope, action_type="crm.read", data_classes=("HEALTH_DATA",)) is BLOCK


def test_deny_off_scope_destination():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    assert _d(app, envelope, action_type="refund.prepare",
              amount_minor_units=100000, data_classes=("CUSTOMER_PII",),
              destination="external://vendor") is BLOCK


# ---------------------------------------------------------------------------
# Cryptographic denials.
# ---------------------------------------------------------------------------
def test_deny_tampered_envelope_scope():
    # Broadening the scope after signing invalidates the signature.
    app = build_application()
    _, _, envelope = approved_envelope(app)
    tampered = replace(
        envelope,
        scope=replace(envelope.scope, tools_allow=envelope.scope.tools_allow + ("refund.execute",)),
    )
    app.envelopes.save(tampered)
    # Even the newly allowed tool is denied because the signature no longer verifies.
    assert _d(app, tampered, action_type="refund.execute") is BLOCK
    assert not app.verify_envelope(TENANT, tampered.envelope_id).valid


def test_deny_unknown_signing_key():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    gate = ReferenceActionGate()
    empty_ring = KeyRing({})  # runtime has no key for this kid
    from tests.scenario import action_request as _ar

    req = _ar(envelope, action_type="crm.read")
    from risk_authority.domain import CanonicalAction

    action = CanonicalAction(
        tenant_id=TENANT, actor_id=ACTOR, model_id=MODEL,
        action_type="crm.read", target_id="txn", purpose="CUSTOMER_REFUND_REVIEW",
        destination="internal://finance",
    )
    authz = gate.authorize(
        authorization_id="auth_1", envelope=envelope, action=action,
        identity=RuntimeIdentity(TENANT, ACTOR, MODEL, "sess_1"),
        key_ring=empty_ring, revocation_state=RevocationState(), now=FIXED_NOW,
    )
    assert authz.decision is BLOCK
    assert any("unknown key" in r for r in authz.reason_codes)


# ---------------------------------------------------------------------------
# Payload binding (TOCTOU) — AC-07.
# ---------------------------------------------------------------------------
def test_payload_mutation_changes_digest():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    authz = app.authorize_action(action_request(
        envelope, action_type="refund.prepare",
        amount_minor_units=300000, data_classes=("CUSTOMER_PII",)))
    assert authz.authorized
    from risk_authority.domain import CanonicalAction

    mutated = CanonicalAction(
        tenant_id=TENANT, actor_id=ACTOR, model_id=MODEL,
        action_type="refund.prepare", target_id="txn_123",
        purpose="CUSTOMER_REFUND_REVIEW", data_classes=("CUSTOMER_PII",),
        destination="internal://finance", amount_minor_units=900000, currency="USD",
    )
    # An executor comparing digests rejects the mutated payload.
    assert mutated.digest != authz.action_digest


# ---------------------------------------------------------------------------
# Revocation — AC-05 / RA-6 seam.
# ---------------------------------------------------------------------------
def test_deny_after_epoch_advance():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    assert _d(app, envelope, action_type="crm.read") is ActionGateDecision.AUTHORIZED
    app.revocation.advance_epoch(TENANT)  # 1 -> 2, envelope bound to epoch 1
    assert _d(app, envelope, action_type="crm.read") is BLOCK


def test_deny_after_targeted_envelope_revocation():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    app.revocation.revoke_envelope(envelope.envelope_id)
    assert _d(app, envelope, action_type="crm.read") is BLOCK


def test_deny_after_subject_revocation():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    app.revocation.revoke_subject(TENANT, ACTOR)
    assert _d(app, envelope, action_type="crm.read") is BLOCK


def test_deny_after_model_revocation():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    app.revocation.revoke_model(TENANT, MODEL)
    assert _d(app, envelope, action_type="crm.read") is BLOCK


# ---------------------------------------------------------------------------
# Tenant isolation — spec §39.
# ---------------------------------------------------------------------------
def test_envelope_not_resolvable_cross_tenant():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    # A lookup under a different tenant cannot resolve the envelope.
    assert app.envelopes.get("tenant_999", envelope.envelope_id) is None
    # And an authorize request under the wrong tenant is denied.
    assert app.authorize_action(action_request(
        envelope, tenant_id="tenant_999", action_type="crm.read")).decision is BLOCK
