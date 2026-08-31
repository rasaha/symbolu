"""RA-6 last-mile TOCTOU + resume/recovery regressions (task §16, §17, §20 S–V).

These exercise the pre-effect authority re-verification through the **actual**
Agent Runtime clearance seam (``validate_clearance`` with the neutral
``authority_recheck`` hook wired to :func:`make_pre_effect_recheck`). The runtime
imports nothing from Risk Authority — it only calls a neutral callable — so the
seam stays concrete-free while RA-6 supplies the authority meaning.

Scenarios:
  S. revoke between the ActionGate check and the consequential side effect → blocked
  T. epoch advance between check and side effect → blocked
  U. expiry between check and side effect → blocked
  V. revoke/epoch/expiry while checkpointed (suspended) → resume blocked
  W. a fresh replacement envelope after reassessment → proceeds
"""

from __future__ import annotations

from datetime import timedelta

import ra6_scenario as C
from risk_authority.services.authority_status import StalenessPolicy
from ugence_agent_runtime.governance.decisions import (
    CLEAR_REJECTED_AUTHORITY_STALE,
    validate_clearance,
)
from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
)
from ugence_agent_runtime.models.proposal import TransitionProposal
from ugence_risk_authority_status_runtime import (
    PreEffectContext,
    make_pre_effect_recheck,
)


def _proposal() -> TransitionProposal:
    return TransitionProposal.build(
        workflow_id="wf",
        instance_id="inst",
        task_id="task",
        provider_id="prov",
        operation="refund.prepare",
        arguments={"amount": 100},
        correlation_id="corr-1",
    )


def _clear(proposal: TransitionProposal, *, valid_until=None) -> GovernanceEvaluation:
    return GovernanceEvaluation(
        disposition=GovernanceDisposition.CLEAR,
        proposal_fingerprint=proposal.fingerprint,
        authorization_reference="rae_1",
        valid_until=valid_until,
        correlation_reference=proposal.correlation_id,
    )


def _recheck_for(h, *, clock, sync=None):
    """Build the neutral last-mile hook bound to this harness' envelope."""

    def resolve(evaluation, proposal):
        return PreEffectContext(
            envelope=h.envelope,
            tier=h.residual_risk,
            expected_tenant=C.TENANT,
            expected_session=C.SESSION,
        )

    return make_pre_effect_recheck(
        reader=h.cache,
        policy=StalenessPolicy.fail_closed_defaults(),
        key_ring=h.key_ring,
        clock=clock,
        resolve=resolve,
        sync=sync,
    )


def _validate(h, *, recheck):
    proposal = _proposal()
    evaluation = _clear(proposal)
    # Agent Runtime's own logical float clock — independent of the RA-6 datetime
    # clock the recheck uses; here we only need a valid non-expired float.
    return validate_clearance(evaluation, proposal, now=0.0, authority_recheck=recheck)


def _base_time_clock(h):
    """A datetime clock the recheck reads; defaults to the harness 'now'."""

    box = {"t": h.now}
    return box, (lambda: box["t"])


# --------------------------------------------------------------------------- #
def test_S_revoke_between_check_and_effect_blocks():
    h = C.build()
    box, clock = _base_time_clock(h)
    # sync() the cache at recheck time so the newly-landed revoke is observed.
    recheck = _recheck_for(h, clock=clock, sync=lambda: h.cache.sync())

    # First: with nothing revoked, the pre-effect recheck permits.
    ok, _ = _validate(h, recheck=recheck)
    assert ok

    # Now a revoke lands AFTER the initial CLEAR but before the effect.
    h.writer.revoke_envelope(
        principal=h.admin(), tenant_id=C.TENANT, envelope_id=h.envelope.envelope_id,
        reason="revoked mid-flight", correlation_id="x",
    )
    ok2, reasons = _validate(h, recheck=recheck)
    assert not ok2
    assert reasons[0] == CLEAR_REJECTED_AUTHORITY_STALE
    assert any("revoked" in r for r in reasons)


def test_T_epoch_advance_between_check_and_effect_blocks():
    h = C.build()
    box, clock = _base_time_clock(h)
    recheck = _recheck_for(h, clock=clock, sync=lambda: h.cache.sync())
    assert _validate(h, recheck=recheck)[0]

    h.writer.advance_epoch(
        principal=h.admin(), tenant_id=C.TENANT, change_id="c", reason="r",
        correlation_id="x",
    )
    ok, reasons = _validate(h, recheck=recheck)
    assert not ok
    assert any("stale authority epoch" in r for r in reasons)


def test_U_expiry_between_check_and_effect_blocks():
    h = C.build()
    box, clock = _base_time_clock(h)
    recheck = _recheck_for(h, clock=clock, sync=lambda: h.cache.sync())
    assert _validate(h, recheck=recheck)[0]

    # Advance the RA-6 clock past the envelope expiry AND keep the cache fresh so
    # expiry (not staleness) is the blocking reason.
    box["t"] = h.envelope.expires_at + timedelta(seconds=1)
    h.clock.value = box["t"]
    ok, reasons = _validate(h, recheck=recheck)
    assert not ok
    assert any("expired" in r for r in reasons)


def test_V_revoke_while_checkpointed_blocks_resume():
    # Model resume/recovery: a clearance is captured (checkpointed) as CLEAR, then
    # authority is revoked while suspended; on resume the pre-effect recheck runs
    # again and blocks. A checkpointed CLEAR must never become durable executable
    # authority (task §17).
    h = C.build()
    box, clock = _base_time_clock(h)
    recheck = _recheck_for(h, clock=clock, sync=lambda: h.cache.sync())

    proposal = _proposal()
    evaluation = _clear(proposal)  # this is what a checkpoint would persist

    # ... suspend ... revoke lands ... resume:
    h.writer.revoke_subject(
        principal=h.admin(), tenant_id=C.TENANT, subject_id=h.envelope.subject,
        reason="revoked while suspended", correlation_id="x",
    )
    ok, reasons = validate_clearance(evaluation, proposal, now=0.0, authority_recheck=recheck)
    assert not ok and any("subject revoked" in r for r in reasons)


def test_V_epoch_advanced_while_suspended_blocks_resume():
    h = C.build()
    box, clock = _base_time_clock(h)
    recheck = _recheck_for(h, clock=clock, sync=lambda: h.cache.sync())
    proposal = _proposal()
    evaluation = _clear(proposal)
    h.writer.advance_epoch(
        principal=h.admin(), tenant_id=C.TENANT, change_id="c", reason="r",
        correlation_id="x",
    )
    ok, reasons = validate_clearance(evaluation, proposal, now=0.0, authority_recheck=recheck)
    assert not ok and any("stale authority epoch" in r for r in reasons)


def test_V_expired_while_suspended_blocks_resume():
    h = C.build()
    box, clock = _base_time_clock(h)
    recheck = _recheck_for(h, clock=clock, sync=lambda: h.cache.sync())
    proposal = _proposal()
    evaluation = _clear(proposal)
    box["t"] = h.envelope.expires_at + timedelta(seconds=1)
    h.clock.value = box["t"]
    ok, reasons = validate_clearance(evaluation, proposal, now=0.0, authority_recheck=recheck)
    assert not ok and any("expired" in r for r in reasons)


def test_W_fresh_replacement_envelope_after_reassessment_proceeds():
    # The suspended-then-revoked slice cannot resume; but a NEW envelope minted by
    # a fresh reassessment is not revoked and passes the same recheck.
    h = C.build()
    box, clock = _base_time_clock(h)
    recheck = _recheck_for(h, clock=clock, sync=lambda: h.cache.sync())
    # revoke original -> blocked
    h.writer.revoke_envelope(
        principal=h.admin(), tenant_id=C.TENANT, envelope_id=h.envelope.envelope_id,
        reason="r", correlation_id="x",
    )
    assert not _validate(h, recheck=recheck)[0]

    # a fresh slice = new envelope id, its own store/cache → proceeds
    h2 = C.build()
    box2, clock2 = _base_time_clock(h2)
    recheck2 = _recheck_for(h2, clock=clock2, sync=lambda: h2.cache.sync())
    assert _validate(h2, recheck=recheck2)[0]


def test_non_authority_action_passes_through():
    # A recheck whose resolver returns None (not an authority-bound action) is a
    # low-latency pass-through — non-consequential behavior is preserved (§8).
    h = C.build()
    _box, clock = _base_time_clock(h)
    passthrough = make_pre_effect_recheck(
        reader=h.cache,
        policy=StalenessPolicy.fail_closed_defaults(),
        key_ring=h.key_ring,
        clock=clock,
        resolve=lambda e, p: None,
    )
    assert _validate(h, recheck=passthrough)[0]
