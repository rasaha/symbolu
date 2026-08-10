"""RA-4 milestone: the full authority spine, ALLOW/DENY matrix (user brief §13).

    WorkflowIR -> RiskDecisionCase -> ControlResult -> Decision Authority
        -> signed RiskAuthorizationEnvelope -> Canonical Action
        -> ActionGate -> ALLOW / DENY
"""

from __future__ import annotations

from risk_authority.domain import ActionGateDecision, RiskCaseState, RiskOutcome

from tests.scenario import (
    TENANT,
    action_request,
    approved_envelope,
    build_application,
)


def _authorize(app, envelope, **overrides) -> ActionGateDecision:
    return app.authorize_action(action_request(envelope, **overrides)).decision


def test_full_spine_reaches_active_authority():
    app = build_application()
    evaluation, decision, envelope = approved_envelope(app)
    assert evaluation.recommendation.value == "ALLOW_WITH_CONDITIONS"
    assert decision.outcome is RiskOutcome.ALLOW_WITH_CONDITIONS
    case = app.cases.get(TENANT, "rdc_1")
    assert case.state is RiskCaseState.ACTIVE
    assert app.verify_envelope(TENANT, envelope.envelope_id).valid


def test_actiongate_allow_deny_matrix():
    app = build_application()
    _, _, envelope = approved_envelope(app)

    A = ActionGateDecision.AUTHORIZED
    D = ActionGateDecision.DENIED

    # crm.read -> AUTHORIZED
    assert _authorize(app, envelope, action_type="crm.read") is A
    # refund.prepare $3,000 -> AUTHORIZED
    assert (
        _authorize(
            app,
            envelope,
            action_type="refund.prepare",
            amount_minor_units=300000,
            data_classes=("CUSTOMER_PII",),
        )
        is A
    )
    # refund.prepare $6,000 -> DENIED (over the $5,000 ceiling)
    assert (
        _authorize(
            app,
            envelope,
            action_type="refund.prepare",
            amount_minor_units=600000,
            data_classes=("CUSTOMER_PII",),
        )
        is D
    )
    # refund.execute -> DENIED (deny set)
    assert _authorize(app, envelope, action_type="refund.execute") is D
    # email.external -> DENIED (deny set)
    assert _authorize(app, envelope, action_type="email.external", destination="") is D
    # same request, different tenant -> DENIED
    assert _authorize(app, envelope, action_type="crm.read", tenant_id="tenant_999") is D
    # same envelope, different model -> DENIED
    assert _authorize(app, envelope, action_type="crm.read", model_id="model_evil") is D


def test_lineage_is_reconstructable():
    # Every material step emits an audit event chained to the case (AC-12).
    app = build_application()
    _, _, envelope = approved_envelope(app)
    app.authorize_action(action_request(envelope, action_type="crm.read"))
    events = app.events.all()
    types = {e.event_type.value for e in events}
    assert "CASE_CREATED" in types
    assert "DECISION_ISSUED" in types
    assert "ENVELOPE_ISSUED" in types
    assert "ACTION_AUTHORIZED" in types


def test_unauthorized_escape_rate_is_zero():
    # Spec §31: zero unauthorized-action escapes in deterministic conformance.
    app = build_application()
    _, _, envelope = approved_envelope(app)
    # Fire a battery of off-scope actions; none may be authorized.
    off_scope = [
        dict(action_type="refund.execute"),
        dict(action_type="email.external", destination=""),
        dict(action_type="db.delete"),
        dict(action_type="crm.read", data_classes=("HEALTH_DATA",)),
        dict(action_type="refund.prepare", amount_minor_units=10_000_000, data_classes=("CUSTOMER_PII",)),
    ]
    for kw in off_scope:
        assert _authorize(app, envelope, **kw) is ActionGateDecision.DENIED
    assert app.metrics.get("actiongate.authorized") == 0
