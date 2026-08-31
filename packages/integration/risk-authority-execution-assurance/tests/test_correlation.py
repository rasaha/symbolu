"""Execution correlation + intrinsic binding tuple (spec §5, §18, §24)."""

from __future__ import annotations

import pytest

from ugence_risk_authority_execution_assurance import ExecutionCorrelator, GovernedAuthorityContext

from ra8_scenario import default_context, make_observation
from ugence_decision_authority.execution.status import BusinessOutcome


def _corr(ctx=None, **kw):
    ctx = ctx or default_context()
    correlator = ExecutionCorrelator()
    return correlator, correlator.mint(ctx, attempt_id="idem-1#attempt-1", external_request_id="ext-req-1", **kw)


def test_mint_requires_complete_context():
    correlator = ExecutionCorrelator()
    bad = GovernedAuthorityContext(
        tenant_id="", workflow_instance_id="wf1", envelope_id="env",
        authorized_action_digest="pf1", correlation_id="c1",
    )
    with pytest.raises(ValueError):
        correlator.mint(bad, attempt_id="a1")


def test_mint_requires_attempt_id():
    correlator = ExecutionCorrelator()
    with pytest.raises(ValueError):
        correlator.mint(default_context(), attempt_id="")


def test_matching_observation_has_no_binding_mismatch():
    correlator, corr = _corr()
    obs = make_observation("o1", BusinessOutcome.SUCCEEDED)
    assert correlator.binding_mismatches(corr, obs) == ()


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("tenant_id", "tenantB", "wrong tenant"),
        ("workflow_instance_id", "wf_other", "wrong workflow"),
        ("envelope_id", "env_other", "wrong envelope"),
        ("authorized_action_digest", "pf-other", "wrong action digest"),
        ("attempt_id", "attempt-2", "wrong attempt"),
    ],
)
def test_wrong_binding_is_rejected(field, value, reason):
    correlator, corr = _corr()
    obs = make_observation("o1", BusinessOutcome.SUCCEEDED, **{field: value})
    mismatches = correlator.binding_mismatches(corr, obs)
    assert reason in mismatches


def test_old_receipt_on_new_external_request_rejected():
    correlator, corr = _corr()  # correlation bound to ext-req-1
    obs = make_observation("o1", BusinessOutcome.SUCCEEDED, external_request_id="ext-OLD")
    assert "wrong external_request_id" in correlator.binding_mismatches(corr, obs)


def test_non_observation_is_rejected():
    correlator, corr = _corr()
    assert correlator.binding_mismatches(corr, object()) != ()  # type: ignore[arg-type]
