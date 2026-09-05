"""Shared builders. Every instant is explicit; no test reads a clock either."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ugence_governance_contracts.api import AuditReference

from ugence_control_plane_root import AuditLedger, LedgerEntry

TENANT = "tenant-a"
T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(minutes=5)
T2 = T0 + timedelta(minutes=10)


def ledger(path: str = ":memory:") -> AuditLedger:
    return AuditLedger(path)


def entry(*, tenant: str = TENANT, kind: str = "incident.opened",
          at: datetime = T0, by: str = "operator-1",
          payload: dict | None = None, correlation: str = "") -> LedgerEntry:
    return LedgerEntry(tenant_id=tenant, kind=kind, recorded_at=at, recorded_by=by,
                       payload={"subject_ref": "envelope:env-1"} if payload is None
                       else payload,
                       correlation_id=correlation)


def append(log: AuditLedger, e: LedgerEntry) -> AuditReference:
    """The one call this package exists for, with the real contract injected."""

    return log.append(e, reference_factory=AuditReference)
