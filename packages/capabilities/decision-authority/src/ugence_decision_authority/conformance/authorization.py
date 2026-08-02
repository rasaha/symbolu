"""Authorization dimension — the kernel authorization service ran and decided."""
from __future__ import annotations

from ..audit import AuditEventType
from .results import fail, ok

_AUTH_OUTCOME_EVENTS = {
    AuditEventType.ACTION_AUTHORIZATION_GRANTED,
    AuditEventType.ACTION_AUTHORIZATION_CONSTRAINED,
    AuditEventType.ACTION_AUTHORIZATION_DENIED,
    AuditEventType.ACTION_AUTHORIZATION_INDETERMINATE,
    AuditEventType.ACTION_AUTHORIZATION_EXPIRED,
}


def check(fixture, platform, outcome):
    results = []
    svc_types = fixture.expected_service_types()
    if "action_authorization_service" in svc_types:
        obj = getattr(platform, "action_authorization_service", None)
        good = isinstance(obj, svc_types["action_authorization_service"])
        results.append(
            ok("authorization", "kernel_service") if good
            else fail("authorization", "kernel_service", "not the kernel authz service"))
    emitted = {e.event_type for e in outcome.audit_events}
    submitted = AuditEventType.ACTION_AUTHORIZATION_SUBMITTED in emitted
    decided = bool(emitted & _AUTH_OUTCOME_EVENTS)
    results.append(
        ok("authorization", "submitted_and_decided") if submitted and decided
        else fail("authorization", "submitted_and_decided",
                  "authorization did not submit+decide via the control plane"))
    return results
