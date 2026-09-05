"""Shared builders. Every instant is explicit; no test reads a clock either."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from ugence_governance_contracts.api import Validity

from ugence_ai_system_registry import (
    AssessedSystemBinding,
    SystemRegistration,
    registration_id_for,
)

TENANT = "tenant-a"
OWNER = "directory://people/system-owner-1"
LABEL = "high-risk"
OTHER_LABEL = "limited-risk"

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(minutes=5)
T2 = T0 + timedelta(minutes=10)
BEFORE_WINDOW = T0 - timedelta(days=1)
AFTER_WINDOW = T0 + timedelta(days=400)


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def binding(system_id: str = "hiring-screener", *, version: str = "1.2.0",
            tenant: str = TENANT, configuration: str = "cfg-a",
            subject: str = "subject-1") -> AssessedSystemBinding:
    return AssessedSystemBinding(
        binding_id=f"bind-{system_id}-{version}-{configuration}", tenant_id=tenant,
        subject_id=subject, context_id="ctx-1", context_digest=_digest("ctx-1"),
        system_id=system_id, system_version=version, configuration_id=configuration,
        configuration_digest=_digest(configuration))


def window(issued: datetime = T0, *, days: int = 365) -> Validity:
    return Validity(issued_at=issued, expires_at=issued + timedelta(days=days))


def registration(bound: AssessedSystemBinding | None = None, *, owner: str = OWNER,
                 label: str = LABEL, validity: Validity | None = None,
                 supersedes: str = "", registered_by: str = "admin-1") -> SystemRegistration:
    b = bound or binding()
    v = validity or window()
    return SystemRegistration(
        registration_id=registration_id_for(b, owner, v), binding=b, owner_ref=owner,
        classification_label=label, validity=v, supersedes=supersedes,
        registered_by=registered_by)
