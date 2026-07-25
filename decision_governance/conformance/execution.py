"""Execution dimension — the kernel execution stage dispatched via the port."""
from __future__ import annotations

from ..audit import AuditEventType
from .results import fail, ok


def check(fixture, platform, outcome):
    results = []
    emitted = {e.event_type for e in outcome.audit_events}
    for required in (AuditEventType.EXECUTION_INTENT_CREATED,
                     AuditEventType.EXECUTION_DISPATCH_SUBMITTED):
        results.append(
            ok("execution", f"has:{required.value}") if required in emitted
            else fail("execution", f"has:{required.value}", "execution stage did not run"))
    svc_types = fixture.expected_service_types()
    if "execution_service" in svc_types:
        obj = getattr(platform, "execution_service", None)
        results.append(
            ok("execution", "kernel_service")
            if isinstance(obj, svc_types["execution_service"])
            else fail("execution", "kernel_service", "not the kernel execution service"))
    return results
