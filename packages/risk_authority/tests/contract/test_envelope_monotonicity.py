"""Envelope scope can never exceed decision scope (spec §29, AC-04; CI gate).

This is one of the strongest invariants in the package and the user brief calls
for an explicit test proving the envelope cannot contain authority the decision
did not grant.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.domain import (
    MonotonicityViolationError,
    RiskClass,
    RiskDecision,
    RiskOutcome,
    Scope,
)
from risk_authority.services import EnvelopeIssuer, RevocationState, validate_envelope_subset

NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
KEY = SigningKeyRecord("k", SigningKey.from_seed(bytes(range(32))))


def _decision(scope: Scope) -> RiskDecision:
    return RiskDecision(
        decision_id="risk_dec_1",
        tenant_id="t",
        case_id="rdc_1",
        outcome=RiskOutcome.ALLOW_WITH_CONDITIONS,
        authority_principal_id="p",
        risk_class=RiskClass.HIGH,
        domain="FINANCE",
        scope=scope,
        workflow_ir_digest="sha256:w",
        issued_at=NOW,
    )


DECISION_SCOPE = Scope(
    purposes=("CUSTOMER_REFUND_REVIEW",),
    tools_allow=("crm.read", "refund.prepare"),
    tools_deny=("refund.execute",),
    data_allow=("CUSTOMER_PII",),
    max_autonomy_level=2,
    max_transaction_minor_units=500000,
)


def test_equal_scope_is_allowed():
    validate_envelope_subset(DECISION_SCOPE, DECISION_SCOPE)  # no raise


def test_narrower_scope_is_allowed():
    narrower = Scope(
        purposes=("CUSTOMER_REFUND_REVIEW",),
        tools_allow=("crm.read",),
        tools_deny=("refund.execute", "email.external"),
        data_allow=(),
        max_autonomy_level=1,
        max_transaction_minor_units=100000,
    )
    validate_envelope_subset(narrower, DECISION_SCOPE)  # no raise


def test_extra_tool_is_rejected():
    broader = Scope(
        purposes=("CUSTOMER_REFUND_REVIEW",),
        tools_allow=("crm.read", "refund.prepare", "refund.execute"),
        tools_deny=("refund.execute",),
        data_allow=("CUSTOMER_PII",),
        max_autonomy_level=2,
        max_transaction_minor_units=500000,
    )
    with pytest.raises(MonotonicityViolationError):
        validate_envelope_subset(broader, DECISION_SCOPE)


def test_issuer_refuses_to_sign_broader_envelope():
    issuer = EnvelopeIssuer()
    broader = Scope(
        purposes=("CUSTOMER_REFUND_REVIEW", "PAYROLL"),  # extra purpose
        tools_allow=("crm.read", "refund.prepare"),
        tools_deny=("refund.execute",),
        data_allow=("CUSTOMER_PII",),
        max_autonomy_level=2,
        max_transaction_minor_units=500000,
    )
    with pytest.raises(MonotonicityViolationError):
        issuer.issue(
            envelope_id="rae_1",
            decision=_decision(DECISION_SCOPE),
            audience="rt",
            subject="a",
            model_id="m",
            session_id="s",
            nonce="n",
            key_record=KEY,
            revocation_state=RevocationState(),
            now=NOW,
            envelope_scope=broader,
        )


def test_higher_amount_ceiling_is_rejected():
    broader = Scope(
        purposes=("CUSTOMER_REFUND_REVIEW",),
        tools_allow=("crm.read", "refund.prepare"),
        tools_deny=("refund.execute",),
        data_allow=("CUSTOMER_PII",),
        max_autonomy_level=2,
        max_transaction_minor_units=999999,  # higher than decision
    )
    with pytest.raises(MonotonicityViolationError):
        validate_envelope_subset(broader, DECISION_SCOPE)
