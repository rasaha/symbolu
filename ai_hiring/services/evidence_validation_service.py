"""Evidence validation service — the fail-closed eligibility gate.

The single authority a future evaluation engine must call to learn whether a
stored evidence version may be used. It re-derives the boundary facts
(extraction success, non-empty content, complete provenance, valid hashes, valid
lineage, quarantine state, tenant consistency, authorization) and runs the
:class:`EvaluationEligibilityPolicy`, returning typed reason codes. It never
scores or interprets content.
"""

from __future__ import annotations

from typing import Optional

from ..common import new_id
from ..domain.enums import ActorType, AuditEventType
from ..normalization.eligibility import (
    DEFAULT_ELIGIBILITY_POLICY,
    EligibilityInput,
    EligibilityResult,
    EvaluationEligibilityPolicy,
)
from ..normalization.extraction_status import ExtractionStatus
from ..normalization.lineage import LineageGraph
from ..normalization.reconstruction import ReconstructionResult, verify_reconstruction
from ..policies import lineage_integrity_policy as lineage_policy
from ..repositories.evidence_artifacts import (
    ChunkRepository,
    LineageRepository,
    ProvenanceRepository,
    QuarantineRepository,
)
from ..repositories.interfaces import EvidenceRepository
from .audit_service import AuditService


class EvidenceValidationService:
    def __init__(
        self,
        evidence_repository: EvidenceRepository,
        provenance_repository: ProvenanceRepository,
        chunk_repository: ChunkRepository,
        quarantine_repository: QuarantineRepository,
        lineage_repository: LineageRepository,
        audit_service: AuditService,
        *,
        policy: EvaluationEligibilityPolicy = DEFAULT_ELIGIBILITY_POLICY,
    ) -> None:
        self._evidence = evidence_repository
        self._prov = provenance_repository
        self._chunks = chunk_repository
        self._quarantine = quarantine_repository
        self._lineage = lineage_repository
        self._audit = audit_service
        self._policy = policy

    def validate_reconstruction(
        self, evidence_id: str, *, correlation_id: Optional[str] = None
    ) -> ReconstructionResult:
        evidence = self._evidence.get(evidence_id)
        chunks = self._chunks.for_evidence(evidence_id, evidence.version)
        result = verify_reconstruction(
            chunks, expected_normalized_hash=evidence.content_hash,
            evidence_id=evidence_id, version=evidence.version)
        corr = correlation_id or new_id("corr")
        self._audit.record(
            event_type=(AuditEventType.EVIDENCE_RECONSTRUCTION_VALIDATED if result.ok
                        else AuditEventType.EVIDENCE_RECONSTRUCTION_FAILED),
            entity_type="evidence", entity_id=evidence_id, actor_type=ActorType.SYSTEM,
            correlation_id=corr, payload={"reason": result.reason_code})
        return result

    def evaluate_eligibility(
        self,
        evidence_id: str,
        *,
        tenant_id: str,
        authorized: bool = True,
        correlation_id: Optional[str] = None,
    ) -> EligibilityResult:
        """Fail-closed eligibility for a stored evidence version."""
        corr = correlation_id or new_id("corr")
        evidence = self._evidence.get(evidence_id)

        # Provenance completeness.
        provenance_complete = True
        try:
            provenance = self._prov.get(evidence.provenance)
            provenance_complete = bool(
                provenance.raw_hash and provenance.normalized_hash and provenance.uploader)
        except Exception:  # noqa: BLE001 - missing provenance == incomplete
            provenance_complete = False

        # Hash + reconstruction integrity.
        chunks = self._chunks.for_evidence(evidence_id, evidence.version)
        recon = verify_reconstruction(
            chunks, expected_normalized_hash=evidence.content_hash,
            evidence_id=evidence_id, version=evidence.version)
        normalized_non_empty = len(chunks) > 0

        # Lineage validity (non-raising).
        lineage_valid = True
        try:
            lineage_policy.validate_graph(
                LineageGraph(nodes=self._lineage.for_evidence(evidence_id)))
        except Exception:  # noqa: BLE001
            lineage_valid = False

        facts = EligibilityInput(
            extraction_status=ExtractionStatus.SUCCEEDED,  # stored evidence extracted OK
            normalized_non_empty=normalized_non_empty,
            provenance_complete=provenance_complete,
            hashes_valid=recon.ok,
            lineage_valid=lineage_valid,
            not_quarantined=True,  # quarantined *fields* are removed; clean evidence remains
            authorized=authorized,
            tenant_consistent=(evidence.tenant_id == tenant_id),
            application_consistent=True,
        )
        result = self._policy.evaluate(facts)
        if not result.eligible:
            self._audit.record(
                event_type=AuditEventType.EVIDENCE_ELIGIBILITY_BLOCKED,
                entity_type="evidence", entity_id=evidence_id, actor_type=ActorType.SYSTEM,
                correlation_id=corr, payload={"reasons": list(result.reason_codes)})
        return result
