"""Shared builders. Every instant is explicit; no test reads a clock either."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from ugence_governance_contracts.api import Validity

from ugence_data_use_admission import (
    AssessedSystemBinding,
    DataClassificationLabel,
    DataUseDeclaration,
    declaration_id_for,
)

TENANT = "tenant-a"
DATA = "dataset://hr/applicants-2026"
OTHER_DATA = "dataset://finance/ledger"
LABEL = DataClassificationLabel("confidential")
OTHER_LABEL = DataClassificationLabel("public")
PURPOSE = "candidate-screening"
OTHER_PURPOSE = "analytics"

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


def declaration(bound: AssessedSystemBinding | None = None, *, tenant: str | None = None,
                data_ref: str = DATA, label: DataClassificationLabel = LABEL,
                purpose: str = PURPOSE, validity: Validity | None = None,
                residency: str = "", supersedes: str = "",
                declared_by: str = "admin-1") -> DataUseDeclaration:
    b = bound or binding()
    v = validity or window()
    return DataUseDeclaration(
        declaration_id=declaration_id_for(b, data_ref, label, purpose, v),
        tenant_id=tenant if tenant is not None else b.tenant_id, binding=b,
        data_ref=data_ref, classification=label, purpose_label=purpose, validity=v,
        residency_label=residency, supersedes=supersedes, declared_by=declared_by)
