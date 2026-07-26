"""API-facing contracts for H1 hiring product entities.

Dependency-light request/response DTOs (pure pydantic — no web framework) that
define the API surface for the product entities. The entity models themselves are
serializable responses; this module adds the request shapes and a few composite
view contracts (eligibility, readiness, reconstruction summary) so an HTTP layer
in a later phase can bind directly to stable contracts.
"""

from __future__ import annotations

from typing import Optional

from ..domain.base import DomainModel
from ..hiring_applications.eligibility import EligibilityResult
from ..hiring_applications.readiness import ReadinessResult
from ..intake.intake import IntakeSource


# --- Request contracts ------------------------------------------------------
class CreateRequisitionRequest(DomainModel):
    title: str
    department: str = ""
    employment_type: str = ""
    location: str = ""
    headcount: int = 1
    description: str = ""
    requisition_id: Optional[str] = None
    correlation_id: str = ""


class DraftJobDefinitionRequest(DomainModel):
    requisition_id: str
    rubric_id: str
    rubric_version: int
    required_capability_ids: tuple[str, ...] = ()
    required_evidence_types: tuple[str, ...] = ()
    job_definition_id: Optional[str] = None
    correlation_id: str = ""


class RegisterCandidateRequest(DomainModel):
    subject_id: str
    display_name: str = ""
    headline: str = ""
    location: str = ""
    contact_ref: str = ""
    candidate_id: Optional[str] = None
    correlation_id: str = ""


class SubmitApplicationRequest(DomainModel):
    candidate_id: str
    requisition_id: str
    job_definition_id: str
    application_id: Optional[str] = None
    correlation_id: str = ""


class IntakeEvidenceRequest(DomainModel):
    application_id: str
    evidence_type: str
    content_hash: str
    source: IntakeSource
    collected_by: str
    source_ref: str = ""
    source_note: str = ""
    intake_id: Optional[str] = None
    correlation_id: str = ""


# --- Composite view contracts ----------------------------------------------
class EligibilityView(DomainModel):
    eligible: bool
    reasons: tuple[str, ...] = ()

    @classmethod
    def of(cls, result: EligibilityResult) -> "EligibilityView":
        return cls(eligible=result.eligible, reasons=result.reasons)


class ReadinessView(DomainModel):
    ready: bool
    missing_evidence_types: tuple[str, ...] = ()
    satisfied_evidence_types: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    @classmethod
    def of(cls, result: ReadinessResult) -> "ReadinessView":
        return cls(
            ready=result.ready, missing_evidence_types=result.missing_evidence_types,
            satisfied_evidence_types=result.satisfied_evidence_types, reasons=result.reasons,
        )


class ReconstructionView(DomainModel):
    entity_type: str
    entity_id: str
    version_count: int
    event_count: int
    hash_chain_valid: bool
    state_lineage_consistent: bool
    reconstructed: bool
    final_state: Optional[str] = None
    issues: tuple[str, ...] = ()

    @classmethod
    def of(cls, result) -> "ReconstructionView":
        return cls(
            entity_type=result.entity_type, entity_id=result.entity_id,
            version_count=result.version_count, event_count=result.event_count,
            hash_chain_valid=result.hash_chain_valid,
            state_lineage_consistent=result.state_lineage_consistent,
            reconstructed=result.reconstructed, final_state=result.final_state,
            issues=result.issues,
        )
