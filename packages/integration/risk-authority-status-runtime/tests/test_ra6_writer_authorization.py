"""RA-6 lifecycle-writer authorization + audit + emergency stop (§5, §11, §12).

The writer is the single authorized mutator. These tests prove the fail-closed
authorization seam, the RA-5 F-1 reference-rejection in production, tenant
isolation, audit attribution, and the privileged emergency-stop path.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import ra6_scenario as C
from risk_authority.domain.enums import GovernanceEventType
from risk_authority.integrations.authority_lifecycle import (
    LifecycleOutcome,
    WriterPrincipal,
)
from ugence_risk_authority_status_runtime import (
    AuthorityLifecycleService,
    ReferenceAuthorityStore,
    ReferenceWriterAuthorizer,
    ReferenceWriterRejectedError,
)
from ugence_risk_authority_status_runtime.writer import (
    EMERGENCY_STOP_CAPABILITY,
    LIFECYCLE_WRITE_CAPABILITY,
)

NOW = datetime(2026, 8, 11, tzinfo=timezone.utc)
TENANT = "t"


def _service(**kw):
    store = ReferenceAuthorityStore()
    store.seed_tenant(TENANT)
    events = []
    svc = AuthorityLifecycleService(
        store, ReferenceWriterAuthorizer(), event_sink=events.append,
        clock=lambda: NOW, **kw,
    )
    return svc, store, events


def _principal(caps=(LIFECYCLE_WRITE_CAPABILITY,), tenant=TENANT, **kw):
    return WriterPrincipal(
        principal_id="p", tenant_id=tenant, capabilities=frozenset(caps), **kw
    )


def test_no_principal_fails_closed():
    svc, store, _ = _service()
    r = svc.advance_epoch(
        principal=None, tenant_id=TENANT, change_id="c", reason="r", correlation_id="x"
    )
    assert r.outcome is LifecycleOutcome.ERROR_NON_EXECUTABLE
    assert store.current_epoch(TENANT) == 1


def test_missing_capability_rejected():
    svc, store, _ = _service()
    r = svc.advance_epoch(
        principal=_principal(caps=()), tenant_id=TENANT, change_id="c", reason="r",
        correlation_id="x",
    )
    assert r.outcome is LifecycleOutcome.ERROR_NON_EXECUTABLE
    assert store.current_epoch(TENANT) == 1


def test_cross_tenant_write_rejected():
    svc, store, _ = _service()
    r = svc.revoke_envelope(
        principal=_principal(tenant="other"), tenant_id=TENANT, envelope_id="e",
        reason="r", correlation_id="x",
    )
    assert r.outcome is LifecycleOutcome.ERROR_NON_EXECUTABLE
    assert store.export(TENANT).revoked_envelopes == frozenset()


def test_authorized_write_applies_and_audits():
    svc, store, events = _service()
    r = svc.revoke_envelope(
        principal=_principal(), tenant_id=TENANT, envelope_id="env-9",
        reason="policy breach", correlation_id="corr-77",
    )
    assert r.outcome is LifecycleOutcome.APPLIED
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type is GovernanceEventType.ENVELOPE_REVOKED
    assert ev.actor == "p"
    assert ev.correlation_id == "corr-77"
    assert ev.attributes["target_id"] == "env-9"
    assert ev.attributes["reason"] == "policy breach"
    assert ev.attributes["idempotency_key"] == "ENVELOPE:env-9"


def test_epoch_advance_audits_with_change_id():
    svc, store, events = _service()
    r = svc.advance_epoch(
        principal=_principal(), tenant_id=TENANT, change_id="chg-1", reason="rotate",
        correlation_id="c",
    )
    assert r.outcome is LifecycleOutcome.APPLIED and r.epoch == 2
    assert events[0].event_type is GovernanceEventType.AUTHORITY_EPOCH_ADVANCED
    assert events[0].attributes["idempotency_key"] == "chg-1"


def test_idempotent_noop_emits_no_event():
    svc, store, events = _service()
    svc.advance_epoch(
        principal=_principal(), tenant_id=TENANT, change_id="k", reason="r",
        correlation_id="c",
    )
    svc.advance_epoch(
        principal=_principal(), tenant_id=TENANT, change_id="k", reason="r",
        correlation_id="c",
    )
    # only the first (state-changing) write is audited; the idempotent no-op isn't.
    assert len(events) == 1


def test_reference_authorizer_refused_in_production():
    store = ReferenceAuthorityStore()
    with pytest.raises(ReferenceWriterRejectedError):
        AuthorityLifecycleService(
            store, ReferenceWriterAuthorizer(), clock=lambda: NOW, production_mode=True
        )


def test_none_authorizer_refused():
    store = ReferenceAuthorityStore()
    with pytest.raises(ReferenceWriterRejectedError):
        AuthorityLifecycleService(store, None, clock=lambda: NOW)


def test_reference_principal_refused_in_production():
    # A production writer with a real authorizer still refuses a reference-marked
    # principal (defense in depth).
    class _ProdAuthorizer:
        is_reference_authorizer = False

        def authorize(self, *, principal, tenant_id, operation, capability):
            return (capability in principal.capabilities, ())

    store = ReferenceAuthorityStore()
    store.seed_tenant(TENANT)
    svc = AuthorityLifecycleService(
        store, _ProdAuthorizer(), clock=lambda: NOW, production_mode=True
    )
    ref_principal = _principal(is_reference=True)
    r = svc.advance_epoch(
        principal=ref_principal, tenant_id=TENANT, change_id="c", reason="r",
        correlation_id="x",
    )
    assert r.outcome is LifecycleOutcome.ERROR_NON_EXECUTABLE


# -- Emergency stop (privileged, stronger capability) ----------------------- #
def test_emergency_stop_requires_stronger_capability():
    svc, store, _ = _service()
    # An ordinary lifecycle-write principal cannot invoke emergency stop.
    r = svc.emergency_stop(
        principal=_principal(caps=(LIFECYCLE_WRITE_CAPABILITY,)), tenant_id=TENANT,
        change_id="e", reason="halt", correlation_id="x",
    )
    assert r.outcome is LifecycleOutcome.ERROR_NON_EXECUTABLE
    assert store.current_epoch(TENANT) == 1


def test_emergency_stop_advances_epoch_with_capability():
    svc, store, events = _service()
    r = svc.emergency_stop(
        principal=_principal(caps=(EMERGENCY_STOP_CAPABILITY,)), tenant_id=TENANT,
        change_id="e", reason="halt", correlation_id="x",
    )
    assert r.outcome is LifecycleOutcome.APPLIED and store.current_epoch(TENANT) == 2
    assert events[0].event_type is GovernanceEventType.AUTHORITY_EPOCH_ADVANCED
    assert "EMERGENCY_STOP" in events[0].attributes["reason"]
