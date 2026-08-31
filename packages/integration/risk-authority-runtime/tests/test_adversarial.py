"""Adversarial composition tests over the REAL Risk Authority enforcement path.

Each RA denial here is produced by Risk Authority itself (signature, expiry,
revocation, epoch, identity, scope, amount, and the F-A/F-B/F-E regressions) —
the additive governance kernels alone would ALLOW or ignore these, which is the
whole point: composition preserves RA authority, it does not re-derive it.

Every case pairs the genuine RA failure with permissive governance
(DA=ADVANCE, AG=ALLOW) and asserts the composed result is still non-executable —
demonstrating ``FinalAuthority ≤ RiskAuthority``.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from ugence_actiongate_provider.core import ActionGateDecision, ActionGateOutcome
from ugence_decision_authority.decisions.status import DecisionOutcome

from ugence_risk_authority_runtime import (
    ActionGatePolicyAdapter,
    DecisionAuthorityGovernanceAdapter,
    FinalDisposition,
    RiskAuthorityCompositionEngine,
)

DA = DecisionAuthorityGovernanceAdapter()
AG = ActionGatePolicyAdapter()
ENGINE = RiskAuthorityCompositionEngine()

PERMISSIVE_DA = DA.to_veto(DecisionOutcome.ADVANCE)
PERMISSIVE_AG = AG.to_veto(ActionGateDecision(outcome=ActionGateOutcome.ALLOW))


def _compose(ra_result):
    return ENGINE.compose(
        risk_authority=ra_result,
        decision_authority=PERMISSIVE_DA,
        actiongate=PERMISSIVE_AG,
    )


def test_happy_path_grants(ra):
    result = _compose(ra.enforce())
    assert result.final_disposition is FinalDisposition.GRANT


def test_bad_signature_denies(ra):
    tampered = replace(ra.envelope, signature=b"\x00" * 64)
    result = _compose(ra.enforce(envelope=tampered))
    assert result.final_disposition is FinalDisposition.DENY


def test_tampered_payload_denies(ra):
    # Mutate a signed field: the recomputed signing payload no longer verifies.
    tampered = replace(ra.envelope, audience="attacker-runtime")
    result = _compose(ra.enforce(envelope=tampered))
    assert result.final_disposition is FinalDisposition.DENY


def test_wrong_tenant_denies(ra):
    result = _compose(
        ra.enforce(
            action=ra.action(tenant_id="tenant_evil"),
            identity=ra.identity(tenant_id="tenant_evil"),
        )
    )
    assert result.final_disposition is FinalDisposition.DENY


def test_wrong_actor_denies(ra):
    result = _compose(
        ra.enforce(
            action=ra.action(actor_id="agent_evil"),
            identity=ra.identity(actor_id="agent_evil"),
        )
    )
    assert result.final_disposition is FinalDisposition.DENY


def test_wrong_model_denies(ra):
    result = _compose(
        ra.enforce(
            action=ra.action(model_id="model_evil"),
            identity=ra.identity(model_id="model_evil"),
        )
    )
    assert result.final_disposition is FinalDisposition.DENY


def test_off_scope_tool_denies(ra):
    # refund.execute is explicitly denied in the finance scope.
    result = _compose(ra.enforce(action=ra.action(action_type="refund.execute")))
    assert result.final_disposition is FinalDisposition.DENY


def test_amount_above_ra_ceiling_denies(ra):
    result = _compose(
        ra.enforce(
            action=ra.action(
                action_type="refund.prepare", amount_minor_units=600000
            )
        )
    )
    assert result.final_disposition is FinalDisposition.DENY


def test_amount_within_ceiling_grants(ra):
    result = _compose(
        ra.enforce(
            action=ra.action(
                action_type="refund.prepare", amount_minor_units=400000
            )
        )
    )
    assert result.final_disposition is FinalDisposition.GRANT


def test_expired_envelope_denies(ra):
    later = ra.envelope.expires_at + timedelta(hours=1)
    result = _compose(ra.enforce(now=later))
    assert result.final_disposition is FinalDisposition.DENY


def test_revoked_envelope_denies(ra):
    ra.revocation.revoke_envelope(ra.envelope.envelope_id)
    result = _compose(ra.enforce())
    assert result.final_disposition is FinalDisposition.DENY


def test_stale_epoch_denies(ra):
    # Advance the tenant authority epoch beyond the envelope's bound epoch: the
    # envelope's bound epoch is now behind the tenant epoch → stale.
    ra.revocation.advance_epoch(ra.envelope.tenant_id)
    result = _compose(ra.enforce())
    assert result.final_disposition is FinalDisposition.DENY


# --- F-A / F-B / F-E preservation over the composition path ---------------


def test_f_a_failed_control_cannot_be_overridden(make_harness):
    """F-A: a failed mandatory control yields no valid authority; DA ADVANCE +
    AG ALLOW cannot manufacture a GRANT."""

    harness = make_harness(
        controls=(
            ("MODEL_PROVENANCE_VALID", "FAIL"),  # mandatory control fails
            ("HUMAN_OVERSIGHT_VALID", "PASS"),
            ("BIAS_EVALUATION_CURRENT", "PASS"),
        )
    )
    # RA refused to mint any envelope for the failed-control decision.
    assert harness.envelope is None
    result = _compose(harness.enforce())
    assert result.final_disposition is not FinalDisposition.GRANT
    assert result.final_disposition is FinalDisposition.DENY


def test_f_e_duplicate_fail_then_pass_cannot_mask_failure(make_harness):
    """F-E: a duplicate PASS for a control that also FAILed cannot mask the
    failure — RA groups per control id and FAIL wins."""

    harness = make_harness(
        controls=(
            ("MODEL_PROVENANCE_VALID", "FAIL"),
            ("MODEL_PROVENANCE_VALID", "PASS"),  # duplicate PASS must not mask FAIL
            ("HUMAN_OVERSIGHT_VALID", "PASS"),
            ("BIAS_EVALUATION_CURRENT", "PASS"),
        )
    )
    result = _compose(harness.enforce())
    assert result.final_disposition is FinalDisposition.DENY


def test_f_e_pass_then_duplicate_fail_denies(make_harness):
    harness = make_harness(
        controls=(
            ("MODEL_PROVENANCE_VALID", "PASS"),
            ("MODEL_PROVENANCE_VALID", "FAIL"),
            ("HUMAN_OVERSIGHT_VALID", "PASS"),
            ("BIAS_EVALUATION_CURRENT", "PASS"),
        )
    )
    result = _compose(harness.enforce())
    assert result.final_disposition is FinalDisposition.DENY


def test_f_b_expired_envelope_is_never_refreshed_by_governance(ra):
    """F-B: an expired envelope cannot be refreshed by DA ADVANCE / AG ALLOW; the
    effective expiry is never extended past RA expiry."""

    later = ra.envelope.expires_at + timedelta(hours=2)
    result = _compose(ra.enforce(now=later))
    assert result.final_disposition is FinalDisposition.DENY
