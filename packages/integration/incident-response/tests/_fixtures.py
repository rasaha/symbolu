"""Shared builders. Every instant is explicit; no test reads a clock either."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from ugence_governance_contracts.api import AuditReference

from ugence_incident_response import (
    ContainmentLift,
    ContainmentRequest,
    IncidentRecord,
    RemediationProposal,
    incident_id_for,
)

TENANT = "tenant-a"
SUBJECT = "envelope:env-1"
SEVERITY = "sev-1"
TARGET = "envelope:env-1"

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(minutes=5)
T2 = T0 + timedelta(minutes=10)
T3 = T0 + timedelta(minutes=15)


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def audit_ref(entry: str = "e:1", *, store: str = "ugence_approval_workflow:ledger_events",
              tenant: str = TENANT, content: str = "entry-1") -> AuditReference:
    return AuditReference(tenant_id=tenant, store_ref=store, entry_ref=entry,
                          entry_digest=_digest(content))


def incident(*, tenant: str = TENANT, subject: str = SUBJECT, severity: str = SEVERITY,
             evidence=None, opened: datetime = T0, by: str = "operator-1") -> IncidentRecord:
    refs = tuple(evidence) if evidence is not None else (audit_ref(),)
    return IncidentRecord(
        incident_id=incident_id_for(tenant, subject, refs, opened), tenant_id=tenant,
        subject_ref=subject, severity_label=severity, evidence=refs, opened_at=opened,
        opened_by=by, summary="observed at the seam")


def containment(inc: IncidentRecord | None = None, *, target: str = TARGET,
                at: datetime = T1, by: str = "operator-1",
                reason: str = "authority in use after revocation") -> ContainmentRequest:
    i = inc or incident()
    return ContainmentRequest(incident_id=i.incident_id, tenant_id=i.tenant_id,
                              target_ref=target, reason=reason, requested_at=at,
                              requested_by=by)


def lift(request: ContainmentRequest, *, at: datetime = T3, by: str = "operator-2",
         justification: str = "root cause fixed and verified") -> ContainmentLift:
    return ContainmentLift(incident_id=request.incident_id, tenant_id=request.tenant_id,
                           target_ref=request.target_ref, justification=justification,
                           lifted_at=at, lifted_by=by,
                           request_digest=request.record_digest())


def proposal(inc: IncidentRecord | None = None, *, compensation: str = "",
             at: datetime = T2, by: str = "operator-1") -> RemediationProposal:
    i = inc or incident()
    return RemediationProposal(incident_id=i.incident_id, tenant_id=i.tenant_id,
                               proposed_action="re-issue the envelope at a new epoch",
                               justification="the prior envelope is revoked",
                               proposed_at=at, proposed_by=by, compensation_ref=compensation)
