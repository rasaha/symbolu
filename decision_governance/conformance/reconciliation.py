"""Reconciliation dimension — outcome reconciled through the kernel service."""
from __future__ import annotations

from ..audit import AuditEventType
from ..execution import ReconciliationStatus
from .results import fail, ok


def check(fixture, platform, outcome):
    results = []
    valid_status = outcome.reconciliation_status in {s.value for s in ReconciliationStatus}
    results.append(
        ok("reconciliation", "valid_status") if valid_status
        else fail("reconciliation", "valid_status",
                  f"{outcome.reconciliation_status} is not a ReconciliationStatus"))
    emitted = {e.event_type for e in outcome.audit_events}
    results.append(
        ok("reconciliation", "reconciled_event")
        if AuditEventType.EXECUTION_RECONCILED in emitted
        else fail("reconciliation", "reconciled_event", "no EXECUTION_RECONCILED event"))
    return results
