"""Shared builders. Every instant is explicit; no test reads a clock either."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from ugence_governance_contracts.api import Validity

from ugence_vendor_dependency import (
    LEGACY_CONTRACT_VERSION,
    AssessedSystemBinding,
    VendorDependencyDeclaration,
    VocabularyBinding,
    VendorRiskLabel,
    declaration_id_for,
)

TENANT = "tenant-a"
VENDOR = "vendor://acme-llm"
OTHER_VENDOR = "vendor://beta-vision"
POSTURE = VendorRiskLabel("elevated")
OTHER_POSTURE = VendorRiskLabel("approved-with-conditions")
#: The published vocabulary a current declaration cites. The digest is fixture-shaped
#: rather than the real published one on purpose: this package never resolves a binding,
#: so a test using the real digest would look like it was checking something it is
#: forbidden to check.
POSTURE_VOCABULARY = VocabularyBinding(
    vocabulary="vendor-dependency-assessment-state", version="1.0.0",
    specification_digest="sha256:" + "1a" * 32)
NEXT_POSTURE_VOCABULARY = VocabularyBinding(
    vocabulary="vendor-dependency-assessment-state", version="2.0.0",
    specification_digest="sha256:" + "3c" * 32)

POLICY = "policy://vendor-standard/v3"
OTHER_POLICY = "policy://vendor-standard/v4"

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
                vendor: str = VENDOR, posture: VendorRiskLabel = POSTURE,
                policy: str = POLICY, validity: Validity | None = None,
                supersedes: str = "", declared_by: str = "admin-1",
                posture_vocabulary: VocabularyBinding | None = None,
                ) -> VendorDependencyDeclaration:
    b = bound or binding()
    v = validity or window()
    pv = posture_vocabulary or POSTURE_VOCABULARY
    return VendorDependencyDeclaration(
        declaration_id=declaration_id_for(b, vendor, posture, policy, v, pv),
        tenant_id=tenant if tenant is not None else b.tenant_id, binding=b,
        vendor_ref=vendor, risk_posture=posture, policy_ref=policy, validity=v,
        posture_vocabulary=pv, supersedes=supersedes, declared_by=declared_by)


def legacy_declaration(bound: AssessedSystemBinding | None = None, *,
                       vendor: str = VENDOR, posture: VendorRiskLabel = POSTURE,
                       policy: str = POLICY, validity: Validity | None = None,
                       declared_by: str = "admin-1") -> VendorDependencyDeclaration:
    """A record of the shape written before the binding, for the read path only.

    Nothing constructs one of these in anger — the store refuses to write it. It exists
    so the v1 projection can be exercised against a record that really does predate the
    field.
    """

    b = bound or binding()
    v = validity or window()
    return VendorDependencyDeclaration(
        declaration_id=declaration_id_for(b, vendor, posture, policy, v),
        tenant_id=b.tenant_id, binding=b, vendor_ref=vendor, risk_posture=posture,
        policy_ref=policy, validity=v, record_version=LEGACY_CONTRACT_VERSION,
        declared_by=declared_by)
