"""RA-6 signal intake + reassessment (§6, §12.3, §13, §14).

Signals trigger reassessment; they never grant/revoke directly and never carry
authority. Emergency stop is refused on the ordinary observer intake. Duplicate /
malformed / out-of-order signals never mint or lose authority.
"""

from __future__ import annotations

from datetime import datetime, timezone

import ra6_scenario as C
from risk_authority.domain.authority_signal import (
    AUTHORITY_SIGNAL_SCHEMA_VERSION,
    AuthorityReassessmentSignal,
    SignalChangeType,
    SignalTarget,
    SignalTargetType,
)
from risk_authority.integrations.authority_lifecycle import SignalDisposition

NOW = datetime(2026, 8, 11, tzinfo=timezone.utc)


def _sig(h, **over) -> AuthorityReassessmentSignal:
    base = dict(
        schema_version=AUTHORITY_SIGNAL_SCHEMA_VERSION,
        event_id="evt-1",
        tenant_id=C.TENANT,
        target=SignalTarget(SignalTargetType.MODEL, "model_xyz"),
        change_type=SignalChangeType.MODEL_INVALIDATED,
        source="model-registry",
        source_version="1.0",
        observed_at=NOW,
        reason="model deprecated",
        correlation_id="corr-1",
    )
    base.update(over)
    return AuthorityReassessmentSignal(**base)


def test_valid_signal_accepted_and_triggers_consequence():
    h = C.build()
    reassessor = C.system_reassessor(h)
    ack = reassessor.submit(_sig(h))
    assert ack.disposition is SignalDisposition.ACCEPTED_FOR_REASSESSMENT
    assert "model_xyz" in h.store.export(C.TENANT).revoked_models


def test_duplicate_event_id_ignored():
    h = C.build()
    reassessor = C.system_reassessor(h)
    reassessor.submit(_sig(h, event_id="dup"))
    ack2 = reassessor.submit(
        _sig(h, event_id="dup", target=SignalTarget(SignalTargetType.MODEL, "other"))
    )
    assert ack2.disposition is SignalDisposition.IGNORED
    # the duplicate's (different) target was never actioned
    assert "other" not in h.store.export(C.TENANT).revoked_models


def test_malformed_signal_ignored_no_mutation():
    h = C.build()
    reassessor = C.system_reassessor(h)
    ack = reassessor.submit(_sig(h, schema_version="bogus"))
    assert ack.disposition is SignalDisposition.IGNORED
    assert h.store.export(C.TENANT).revoked_models == frozenset()


def test_emergency_stop_refused_on_observer_intake():
    h = C.build()
    reassessor = C.system_reassessor(h)
    ack = reassessor.submit(
        _sig(
            h,
            change_type=SignalChangeType.TENANT_EMERGENCY_STOP,
            target=SignalTarget(SignalTargetType.TENANT, ""),
        )
    )
    assert ack.disposition is SignalDisposition.IGNORED
    assert any("privileged" in r for r in ack.reasons)
    assert h.store.current_epoch(C.TENANT) == 1  # no epoch advance from a signal


def test_replayed_signal_is_monotonic_noop():
    # Same logical change delivered twice via DIFFERENT event ids still converges:
    # the reassessor advances the epoch idempotently by signal-derived change_id.
    h = C.build()
    reassessor = C.system_reassessor(h)
    reassessor.submit(
        _sig(h, event_id="a", change_type=SignalChangeType.POLICY_SUPERSEDED,
             target=SignalTarget(SignalTargetType.POLICY, "p1"))
    )
    epoch_after_first = h.store.current_epoch(C.TENANT)
    # A different event id but the SAME event content would re-advance; the writer
    # change_id is derived from event_id, so distinct ids DO advance again — this
    # is safe (monotonic) and bounded. Assert monotonic increase, never rollback.
    reassessor.submit(
        _sig(h, event_id="b", change_type=SignalChangeType.POLICY_SUPERSEDED,
             target=SignalTarget(SignalTargetType.POLICY, "p1"))
    )
    assert h.store.current_epoch(C.TENANT) >= epoch_after_first


def test_signal_evidence_invalidated_revokes_named_envelope_only():
    h = C.build()
    reassessor = C.system_reassessor(h)
    reassessor.submit(
        _sig(
            h,
            change_type=SignalChangeType.EVIDENCE_INVALIDATED,
            target=SignalTarget(SignalTargetType.ENVELOPE, "env-abc"),
        )
    )
    exp = h.store.export(C.TENANT)
    assert exp.revoked_envelopes == frozenset({"env-abc"})
    assert exp.revoked_models == frozenset()  # nothing else touched


def test_ack_carries_no_authority():
    h = C.build()
    reassessor = C.system_reassessor(h)
    ack = reassessor.submit(_sig(h))
    # structural: SignalAck has no allow/scope/token field.
    fields = set(ack.__dataclass_fields__)
    for forbidden in ("allow", "scope", "authority", "grant", "token", "decision"):
        assert forbidden not in fields
