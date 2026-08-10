"""Phase-1 exit / architecture acceptance test (user brief §26, spec §40).

Given an approved RiskDecisionCase authorizing agent_finance_07 for refund
review (crm.read, refund.prepare; max $5,000; internal only), assert the exact
PASS/BLOCK table and that every result reconstructs its lineage:

    Source Policy -> WorkflowIR rule -> RiskDecisionCase -> Control evidence
        -> RiskDecision -> RiskAuthorizationEnvelope -> ActionAuthorization
"""

from __future__ import annotations

from datetime import timedelta

from risk_authority.domain import ActionGateDecision

from tests.scenario import (
    FIXED_NOW,
    TENANT,
    action_request,
    approved_envelope,
    build_application,
)

PASS = ActionGateDecision.AUTHORIZED
BLOCK = ActionGateDecision.DENIED


def _d(app, envelope, **kw):
    return app.authorize_action(action_request(envelope, **kw)).decision


def test_phase1_acceptance_table():
    app = build_application()
    _, decision, envelope = approved_envelope(app)

    # crm.read                               PASS
    assert _d(app, envelope, action_type="crm.read") is PASS
    # refund.prepare($3,000)                 PASS
    assert _d(app, envelope, action_type="refund.prepare",
              amount_minor_units=300000, data_classes=("CUSTOMER_PII",)) is PASS
    # refund.prepare($8,000)                 BLOCK
    assert _d(app, envelope, action_type="refund.prepare",
              amount_minor_units=800000, data_classes=("CUSTOMER_PII",)) is BLOCK
    # refund.execute                         BLOCK
    assert _d(app, envelope, action_type="refund.execute") is BLOCK
    # email.external                         BLOCK
    assert _d(app, envelope, action_type="email.external", destination="") is BLOCK
    # same action under another tenant       BLOCK
    assert _d(app, envelope, action_type="crm.read", tenant_id="tenant_999") is BLOCK
    # same action with another model         BLOCK
    assert _d(app, envelope, action_type="crm.read", model_id="model_other") is BLOCK


def test_lineage_reconstruction():
    app = build_application()
    _, decision, envelope = approved_envelope(app)
    case = app.cases.get(TENANT, "rdc_1")

    # Source policy -> WorkflowIR rule
    workflow = app._workflow_source.get("finance-ai-risk")
    assert "FIN-12" in {r.rule_id for r in workflow.rules}
    # WorkflowIR rule -> case bound to that exact WorkflowIR digest
    assert case.workflow_ir_digest == workflow.digest
    # case -> decision bound to the same policy digest
    assert decision.workflow_ir_digest == workflow.digest
    assert decision.case_id == case.case_id
    # decision -> envelope
    assert envelope.decision_id == decision.decision_id
    assert envelope.bindings.workflow_ir_digest == workflow.digest
    # envelope -> action authorization bound to the exact action digest
    req = action_request(envelope, action_type="refund.prepare",
                         amount_minor_units=300000, data_classes=("CUSTOMER_PII",))
    authz = app.authorize_action(req)
    assert authz.envelope_id == envelope.envelope_id
    assert authz.action_digest.startswith("sha256:")
    assert authz.authorized


def test_expired_envelope_blocks_even_if_previously_valid():
    app = build_application()
    _, _, envelope = approved_envelope(app)
    # Advance the clock past the 30-minute envelope TTL.
    app._clock = lambda: FIXED_NOW + timedelta(hours=2)
    assert _d(app, envelope, action_type="crm.read") is BLOCK
