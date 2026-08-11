"""RA-6 deny-heavy conformance matrix (task §20 A–Z; SPEC §17).

Every row drives a **real** signed envelope through the RA-6 status-aware gate or
the store/writer/reassessor, asserting the ratified fail-closed outcome. The
suite is deliberately deny-heavy: the default posture is DENY and only the
explicitly-valid rows ALLOW.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

import ra6_scenario as C
from risk_authority.domain.enums import ActionGateDecision
from risk_authority.services.authority_status import (
    ALLOW,
    ALLOW_WITH_BOUNDED_STALE_STATUS,
    DENY,
)


def _authorized(result) -> bool:
    return result.decision is ActionGateDecision.AUTHORIZED


def _denied(result) -> bool:
    return result.decision is ActionGateDecision.DENIED


# A. valid envelope + initialized fresh status -> ALLOW
def test_A_valid_fresh_allows():
    h = C.build(residual_risk=C.RiskClass.LOW)
    r = h.authorize()
    assert _authorized(r) and r.status.outcome == ALLOW


# B. envelope expired -> DENY (status fresh, so expiry is the reason)
def test_B_expired_denies():
    h = C.build()
    when = h.envelope.expires_at + timedelta(seconds=1)
    h.refresh_at(when)  # keep status fresh so expiry is isolated
    r = h.authorize(now=when)
    assert _denied(r)
    assert any("expired" in code for code in r.reason_codes)


# C. envelope epoch < current tenant epoch -> DENY
def test_C_stale_epoch_denies():
    h = C.build()
    h.writer.advance_epoch(
        principal=h.admin(), tenant_id=C.TENANT, change_id="c", reason="r",
        correlation_id="x",
    )
    h.cache.sync()
    r = h.authorize()
    assert _denied(r)
    assert any("stale authority epoch" in code for code in r.reason_codes)


# D. targeted envelope revoked -> DENY
def test_D_envelope_revoked_denies():
    h = C.build()
    h.writer.revoke_envelope(
        principal=h.admin(), tenant_id=C.TENANT, envelope_id=h.envelope.envelope_id,
        reason="r", correlation_id="x",
    )
    h.cache.sync()
    r = h.authorize()
    assert _denied(r) and any("explicitly revoked" in c for c in r.reason_codes)


# E. subject revoked -> DENY
def test_E_subject_revoked_denies():
    h = C.build()
    h.writer.revoke_subject(
        principal=h.admin(), tenant_id=C.TENANT, subject_id=h.envelope.subject,
        reason="r", correlation_id="x",
    )
    h.cache.sync()
    r = h.authorize()
    assert _denied(r) and any("subject revoked" in c for c in r.reason_codes)


# F. model revoked -> DENY
def test_F_model_revoked_denies():
    h = C.build()
    h.writer.revoke_model(
        principal=h.admin(), tenant_id=C.TENANT, model_id=h.envelope.model_id,
        reason="r", correlation_id="x",
    )
    h.cache.sync()
    r = h.authorize()
    assert _denied(r) and any("model revoked" in c for c in r.reason_codes)


# G. uninitialized status cache -> DENY (all tiers)
def test_G_uninitialized_denies_all_tiers():
    for tier in C.RiskClass:
        h = C.build(residual_risk=tier, synced=False)  # never synced
        r = h.authorize(tier=tier)
        assert _denied(r), tier
        assert any("uninitialized" in c for c in r.reason_codes)


# H. stale beyond tier bound -> DENY
def test_H_stale_beyond_bound_denies():
    h = C.build(residual_risk=C.RiskClass.LOW)  # LOW bound 300s
    # status as_of stays at build time; check 1000s later (no re-sync)
    when = h.now + timedelta(seconds=1000)
    r = h.authorize(now=when)
    assert _denied(r) and any("stale" in c for c in r.reason_codes)


# I. bounded stale where policy permits -> ALLOW_WITH_BOUNDED_STALE_STATUS
def test_I_bounded_stale_low_allows_annotated():
    h = C.build(residual_risk=C.RiskClass.LOW)
    when = h.now + timedelta(seconds=100)  # within LOW 300 bound, no re-sync
    r = h.authorize(now=when)
    assert _authorized(r) and r.status.outcome == ALLOW_WITH_BOUNDED_STALE_STATUS
    # ... and a HIGH-tier envelope at the same age denies (tighter bound).
    h2 = C.build(residual_risk=C.RiskClass.HIGH)
    r2 = h2.authorize(now=h2.now + timedelta(seconds=100), tier=C.RiskClass.HIGH)
    assert _denied(r2)


# J. epoch rollback attempt -> rejected (no-op, no resurrection)
def test_J_epoch_rollback_rejected():
    h = C.build()
    h.writer.advance_epoch(
        principal=h.admin(), tenant_id=C.TENANT, change_id="c1", reason="r",
        correlation_id="x",
    )
    assert h.store.current_epoch(C.TENANT) == 2
    # A replicated export carrying a LOWER epoch must not lower the watermark.
    from ugence_risk_authority_status_runtime import AuthorityStateExport

    changed = h.store.merge(AuthorityStateExport(tenant_id=C.TENANT, epoch=1))
    assert changed is False
    assert h.store.current_epoch(C.TENANT) == 2


# K. duplicate epoch command -> idempotent
def test_K_duplicate_epoch_idempotent():
    h = C.build()
    r1 = h.writer.advance_epoch(
        principal=h.admin(), tenant_id=C.TENANT, change_id="same", reason="r",
        correlation_id="x",
    )
    r2 = h.writer.advance_epoch(
        principal=h.admin(), tenant_id=C.TENANT, change_id="same", reason="r",
        correlation_id="y",
    )
    assert r1.outcome.value == "APPLIED" and r2.outcome.value == "NO_STATE_CHANGE"
    assert h.store.current_epoch(C.TENANT) == 2  # advanced exactly once


# L. duplicate targeted revoke -> idempotent
def test_L_duplicate_revoke_idempotent():
    h = C.build()
    r1 = h.writer.revoke_envelope(
        principal=h.admin(), tenant_id=C.TENANT, envelope_id="env-x", reason="r",
        correlation_id="x",
    )
    r2 = h.writer.revoke_envelope(
        principal=h.admin(), tenant_id=C.TENANT, envelope_id="env-x", reason="r",
        correlation_id="y",
    )
    assert r1.outcome.value == "APPLIED" and r2.outcome.value == "NO_STATE_CHANGE"


# M. cross-tenant revoke attempt -> rejected
def test_M_cross_tenant_revoke_rejected():
    h = C.build()
    foreign = C.WriterPrincipal(
        principal_id="attacker", tenant_id="other-tenant",
        capabilities=frozenset({C.LIFECYCLE_WRITE_CAPABILITY}),
    )
    r = h.writer.revoke_envelope(
        principal=foreign, tenant_id=C.TENANT, envelope_id=h.envelope.envelope_id,
        reason="r", correlation_id="x",
    )
    assert r.outcome.value == "ERROR_NON_EXECUTABLE"
    assert any("cross-tenant" in c for c in r.reasons)


# N. unauthorized lifecycle writer -> rejected
def test_N_unauthorized_writer_rejected():
    h = C.build()
    powerless = C.WriterPrincipal(
        principal_id="nobody", tenant_id=C.TENANT, capabilities=frozenset()
    )
    r = h.writer.advance_epoch(
        principal=powerless, tenant_id=C.TENANT, change_id="c", reason="r",
        correlation_id="x",
    )
    assert r.outcome.value == "ERROR_NON_EXECUTABLE"
    assert h.store.current_epoch(C.TENANT) == 1  # no state change
    # a None principal also fails closed
    r2 = h.writer.advance_epoch(
        principal=None, tenant_id=C.TENANT, change_id="c", reason="r",
        correlation_id="x",
    )
    assert r2.outcome.value == "ERROR_NON_EXECUTABLE"


# O. malformed reassessment signal -> no authority mutation
def test_O_malformed_signal_no_mutation():
    h = C.build()
    reassessor = C.system_reassessor(h)
    bad = C.AuthorityReassessmentSignal(
        schema_version="999", event_id="", tenant_id="",
        target=C.SignalTarget(C.SignalTargetType.ENVELOPE, ""),
        change_type=C.SignalChangeType.EVIDENCE_INVALIDATED, source="", source_version="",
        observed_at=h.now, reason="", correlation_id="",
    )
    ack = reassessor.submit(bad)
    assert ack.disposition.value == "IGNORED"
    assert h.store.current_epoch(C.TENANT) == 1
    assert h.store.export(C.TENANT).revoked_envelopes == frozenset()


# P. forged/untrusted signal -> no authority mutation
#    (a signal from an unknown source but structurally valid still cannot mint
#     authority; at most it triggers a fail-closed reassessment consequence, and
#     a signal referencing a bogus envelope only revokes that bogus id.)
def test_P_forged_signal_cannot_widen_authority():
    h = C.build()
    reassessor = C.system_reassessor(h)
    forged = _signal(h, target=C.SignalTarget(C.SignalTargetType.ENVELOPE, "ghost-env"))
    ack = reassessor.submit(forged)
    # It can only ever subtract: the real envelope remains valid; the ghost id is
    # the only thing added to the revoke set. No ALLOW/scope was created.
    assert h.authorize().decision is ActionGateDecision.AUTHORIZED
    assert "ghost-env" in h.store.export(C.TENANT).revoked_envelopes


# Q. evidence-invalidation signal -> reassessment -> revoke consequence
def test_Q_evidence_invalidated_revokes_envelope():
    h = C.build()
    reassessor = C.system_reassessor(h)
    sig = _signal(
        h,
        change_type=C.SignalChangeType.EVIDENCE_INVALIDATED,
        target=C.SignalTarget(C.SignalTargetType.ENVELOPE, h.envelope.envelope_id),
    )
    ack = reassessor.submit(sig)
    assert ack.disposition.value == "ACCEPTED_FOR_REASSESSMENT"
    h.cache.sync()
    assert h.authorize().decision is ActionGateDecision.DENIED


# R. policy supersession -> epoch/revoke consequence
def test_R_policy_supersession_advances_epoch():
    h = C.build()
    reassessor = C.system_reassessor(h)
    sig = _signal(
        h,
        change_type=C.SignalChangeType.POLICY_SUPERSEDED,
        target=C.SignalTarget(C.SignalTargetType.POLICY, "pol-1"),
    )
    reassessor.submit(sig)
    assert h.store.current_epoch(C.TENANT) == 2  # broad invalidation
    h.cache.sync()
    assert h.authorize().decision is ActionGateDecision.DENIED  # prior-epoch envelope


# W. new valid envelope after reassessment -> succeeds
def test_W_new_envelope_after_reassessment_succeeds():
    h = C.build()
    # revoke the current envelope
    h.writer.revoke_envelope(
        principal=h.admin(), tenant_id=C.TENANT, envelope_id=h.envelope.envelope_id,
        reason="r", correlation_id="x",
    )
    h.cache.sync()
    assert h.authorize().decision is ActionGateDecision.DENIED
    # a freshly minted envelope (different id) is not in the revoke set → ALLOW
    h2 = C.build()  # independent slice = new envelope id
    assert h2.authorize().decision is ActionGateDecision.AUTHORIZED


# X. old envelope replay after new epoch -> DENY
def test_X_old_envelope_replay_after_epoch_denies():
    h = C.build()
    h.writer.advance_epoch(
        principal=h.admin(), tenant_id=C.TENANT, change_id="c", reason="r",
        correlation_id="x",
    )
    h.cache.sync()
    # replay the original (epoch-1) envelope now that tenant epoch is 2
    r = h.authorize()
    assert _denied(r) and any("stale authority epoch" in c for c in r.reason_codes)


# Y. out-of-order replication -> no authority resurrection
def test_Y_out_of_order_replication_converges_max_epoch():
    h = C.build()
    from ugence_risk_authority_status_runtime import AuthorityStateExport

    # apply epoch 5 then a stale epoch 3 export; watermark stays 5, union grows
    h.store.merge(AuthorityStateExport(tenant_id=C.TENANT, epoch=5,
                                       revoked_envelopes=frozenset({"e5"})))
    h.store.merge(AuthorityStateExport(tenant_id=C.TENANT, epoch=3,
                                       revoked_envelopes=frozenset({"e3"})))
    assert h.store.current_epoch(C.TENANT) == 5
    exp = h.store.export(C.TENANT)
    assert exp.revoked_envelopes == frozenset({"e5", "e3"})  # grow-only union


# Z. revocation/status source unavailable -> ratified failure behavior
def test_Z_status_source_unavailable_fails_by_tier():
    # Model the outage as a cache that cannot refresh: LOW within bound honors a
    # still-valid envelope; HIGH/CRITICAL fail closed past the (tight) bound.
    h_low = C.build(residual_risk=C.RiskClass.LOW)
    when = h_low.now + timedelta(seconds=100)  # store 'unavailable' → no re-sync
    assert h_low.authorize(now=when).decision is ActionGateDecision.AUTHORIZED
    h_high = C.build(residual_risk=C.RiskClass.HIGH)
    assert (
        h_high.authorize(now=h_high.now + timedelta(seconds=100), tier=C.RiskClass.HIGH).decision
        is ActionGateDecision.DENIED
    )


# --------------------------------------------------------------------------- #
def _signal(h, **over) -> "C.AuthorityReassessmentSignal":
    base = dict(
        schema_version=C.AUTHORITY_SIGNAL_SCHEMA_VERSION,
        event_id="evt-1",
        tenant_id=C.TENANT,
        target=C.SignalTarget(C.SignalTargetType.ENVELOPE, h.envelope.envelope_id),
        change_type=C.SignalChangeType.EVIDENCE_INVALIDATED,
        source="evidence-assurance",
        source_version="1.0",
        observed_at=h.now,
        reason="material change",
        correlation_id="corr-1",
    )
    base.update(over)
    return C.AuthorityReassessmentSignal(**base)
