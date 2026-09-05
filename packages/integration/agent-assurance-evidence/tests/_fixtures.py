"""Shared builders. Every instant is explicit; no test reads a clock either."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from ugence_governance_contracts.api import Validity

from ugence_agent_assurance_evidence import (
    AssessedSystemBinding,
    AssuranceFindingDeclaration,
    AssuranceFindingLabel,
    EvidenceReference,
    declaration_id_for,
)

TENANT = "tenant-a"
SUBJECT = "subject-1"
EXERCISE = "exercise://red-team/2026-q3-run-7"
OTHER_EXERCISE = "exercise://robustness/2026-q3-run-2"
FINDING = AssuranceFindingLabel("prompt-injection-succeeded")
OTHER_FINDING = AssuranceFindingLabel("no-finding")

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(minutes=5)
T2 = T0 + timedelta(minutes=10)
BEFORE_WINDOW = T0 - timedelta(days=1)
AFTER_WINDOW = T0 + timedelta(days=400)


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def binding(system_id: str = "hiring-screener", *, version: str = "1.2.0",
            tenant: str = TENANT, configuration: str = "cfg-a",
            subject: str = SUBJECT) -> AssessedSystemBinding:
    return AssessedSystemBinding(
        binding_id=f"bind-{system_id}-{version}-{configuration}", tenant_id=tenant,
        subject_id=subject, context_id="ctx-1", context_digest=_digest("ctx-1"),
        system_id=system_id, system_version=version, configuration_id=configuration,
        configuration_digest=_digest(configuration))


def evidence(evidence_id: str = "ev-run7-001", *, tenant: str = TENANT, subject: str = SUBJECT,
             kind: str = "assurance-exercise-report", content: str = "report-7") -> EvidenceReference:
    return EvidenceReference(evidence_id=evidence_id, tenant_id=tenant, subject_id=subject,
                             evidence_kind=kind, content_digest=_digest(content))


def window(issued: datetime = T0, *, days: int = 365) -> Validity:
    return Validity(issued_at=issued, expires_at=issued + timedelta(days=days))


def declaration(bound: AssessedSystemBinding | None = None, *, tenant: str | None = None,
                ev: EvidenceReference | None = None, finding: AssuranceFindingLabel = FINDING,
                exercise: str = EXERCISE, validity: Validity | None = None,
                supersedes: str = "", declared_by: str = "admin-1") -> AssuranceFindingDeclaration:
    b = bound or binding()
    e = ev or evidence(tenant=b.tenant_id, subject=b.subject_id)
    v = validity or window()
    return AssuranceFindingDeclaration(
        declaration_id=declaration_id_for(b, e, finding, exercise, v),
        tenant_id=tenant if tenant is not None else b.tenant_id, binding=b, evidence=e,
        finding=finding, exercise_ref=exercise, validity=v, supersedes=supersedes,
        declared_by=declared_by)
