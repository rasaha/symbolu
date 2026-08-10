"""Production evidence admission (RA-5 spec §4, §6, §11).

The production implementation behind Risk Authority's ``EvidenceAdmissionPort``.
It answers exactly one question — *"may this evidence enter the assurance
process?"* — over provenance, integrity, freshness and schema. It does **not**
decide whether a control passes, issue authority, invent missing evidence, or
silently accept stale evidence (RA-5 §4 ownership fence).

Admission is intrinsic and context-free by contract (``is_admissible(evidence,
*, now) -> bool``); the tenant/case/workflow/policy *binding* is enforced
downstream by the Control-Assurance request and RA's authoritative binding
re-check (RA-5 §8), so a high-integrity record still cannot cross into the wrong
case.

Fail-closed: a missing/failed check — not ``ADMITTED``, stale, unsupported
schema, tampered digest, missing required identifier, or missing producer
attribution — yields ``False``. Any exception is treated as inadmissible by the
caller (RA facade wraps the call).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Mapping, Optional

from risk_authority.domain.enums import EvidenceState
from risk_authority.domain.evidence import (
    SUPPORTED_EVIDENCE_SCHEMA_VERSIONS,
    ControlEvidenceRecord,
    EvidenceAdmission,
    evidence_integrity_digest,
)

__all__ = ["ProductionEvidenceAdmission", "stamp_admitted_evidence"]


class ProductionEvidenceAdmission:
    """Fail-closed evidence admitter (provenance / integrity / freshness / schema).

    Every check must pass for a record to be admissible:

    * ``schema_version`` is a supported version (§9);
    * the record claims ``EvidenceState.ADMITTED`` (a rejected/other state is
      never usable);
    * the record is current at ``now`` (stale evidence can never back a PASS);
    * the carried ``digest`` matches the recomputed content digest — tamper
      detection over the bound fields (§6);
    * every required identifier is present (evidence_id, tenant_id, source_type,
      source_identity, subject, workflow_ir_digest, policy_digest);
    * producer attribution is present (``producer`` + ``producer_version``) —
      accountability for the admission decision (§6, §13).
    """

    engine_id = "ra5-production-admission"
    engine_version = "1"

    def is_admissible(
        self, evidence: ControlEvidenceRecord, *, now: datetime
    ) -> bool:
        # Schema.
        if evidence.schema_version not in SUPPORTED_EVIDENCE_SCHEMA_VERSIONS:
            return False
        # Admission state.
        if evidence.admission.status is not EvidenceState.ADMITTED:
            return False
        # Freshness.
        if not evidence.is_current(now):
            return False
        # Integrity (tamper detection).
        if not evidence.integrity_ok():
            return False
        # Required identifiers / provenance context.
        for value in (
            evidence.evidence_id,
            evidence.tenant_id,
            evidence.type,
            evidence.issuer,
            evidence.subject_id,
            evidence.workflow_ir_digest,
            evidence.policy_digest,
        ):
            if not value:
                return False
        # Producer attribution (accountability).
        if not evidence.producer or not evidence.producer_version:
            return False
        return True


def stamp_admitted_evidence(
    *,
    evidence_id: str,
    tenant_id: str,
    source_type: str,
    source_identity: str,
    subject: str,
    workflow_ir_digest: str,
    policy_digest: str,
    observed_at: datetime,
    valid_until: Optional[datetime],
    admitted_at: datetime,
    producer: str,
    producer_version: str,
    provenance: Optional[Mapping[str, str]] = None,
    risk_case_id: Optional[str] = None,
    reason: str = "admitted",
) -> ControlEvidenceRecord:
    """Construct a well-formed AdmittedEvidence record with a correct integrity digest.

    Real producers and the reference/test harness both use this to build records
    the production admitter will accept: it computes the canonical integrity
    digest over the bound fields and stamps ``ADMITTED``. Tampering with any field
    afterward (e.g. ``dataclasses.replace(rec, tenant_id=...)`` or flipping the
    digest) breaks ``integrity_ok()`` and the admitter rejects it.
    """

    digest = evidence_integrity_digest(
        evidence_id=evidence_id,
        tenant_id=tenant_id,
        source_type=source_type,
        source_identity=source_identity,
        subject=subject,
        observed_at=observed_at,
        valid_until=valid_until,
        workflow_ir_digest=workflow_ir_digest,
        policy_digest=policy_digest,
        risk_case_id=risk_case_id,
        provenance=provenance,
    )
    return ControlEvidenceRecord(
        evidence_id=evidence_id,
        tenant_id=tenant_id,
        type=source_type,
        subject_id=subject,
        issuer=source_identity,
        created_at=observed_at,
        valid_until=valid_until,
        digest=digest,
        admission=EvidenceAdmission(status=EvidenceState.ADMITTED, reason=reason),
        provenance=dict(provenance or {}),
        workflow_ir_digest=workflow_ir_digest,
        policy_digest=policy_digest,
        admitted_at=admitted_at,
        producer=producer,
        producer_version=producer_version,
        risk_case_id=risk_case_id,
    )


def tamper(
    record: ControlEvidenceRecord, **changes: object
) -> ControlEvidenceRecord:
    """Return a copy of ``record`` with fields changed but the digest left intact.

    A convenience for adversarial tests: the returned record's ``digest`` no
    longer matches its (now-mutated) content, so ``integrity_ok()`` is false and
    the admitter rejects it. Kept here (not in tests) so the tampering path is
    exercised through the package's own surface.
    """

    return dataclasses.replace(record, **changes)  # type: ignore[arg-type]
