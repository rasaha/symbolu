"""Evidence & Scoring data-model contracts (per capability layer).

This phase defines and *validates* the scoring contract. It does not compute
scores, confidence, gaps, or fairness — those are later phases. The value here
is the enforced shape: every score is rubric-bound, reason-coded, and
evidence-linked, and every evaluation carries exactly the ten fixed layers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..errors import DomainValidationError
from .base import DomainModel
from .enums import CapabilityLayer, ConfidenceLevel, EvaluationStatus
from .evidence import EvidenceRef

MIN_SCORE = 0
MAX_SCORE = 4


class ReasonCode(DomainModel):
    """A coded, human-readable justification for a layer score.

    For any score > 0 a reason code must link to at least one evidence
    reference. For a score of 0 (No Evidence) a reason code may instead be
    flagged ``no_evidence=True``.
    """

    code: str
    description: str = ""
    evidence_refs: tuple[EvidenceRef, ...] = ()
    no_evidence: bool = False

    @model_validator(mode="after")
    def _require_code(self) -> "ReasonCode":
        if not self.code.strip():
            raise DomainValidationError("ReasonCode.code must be non-empty")
        return self


class Gap(DomainModel):
    """Explicitly missing evidence needed to reach a higher score level."""

    description: str
    target_layer: Optional[CapabilityLayer] = None
    missing: str = ""

    @model_validator(mode="after")
    def _require_description(self) -> "Gap":
        if not self.description.strip():
            raise DomainValidationError("Gap.description must be non-empty")
        return self


class Limitation(DomainModel):
    """A stated boundary of what the AI could reliably evaluate."""

    description: str

    @model_validator(mode="after")
    def _require_description(self) -> "Limitation":
        if not self.description.strip():
            raise DomainValidationError("Limitation.description must be non-empty")
        return self


class LayerScore(DomainModel):
    """A single capability-layer score with its full justification band."""

    layer_id: CapabilityLayer
    score: int
    confidence: ConfidenceLevel
    reason_codes: tuple[ReasonCode, ...]
    evidence_links: tuple[EvidenceRef, ...] = ()
    gaps: tuple[Gap, ...] = ()
    ai_limitations: tuple[Limitation, ...] = ()
    rubric_version: str
    model_version: str
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "LayerScore":
        if not (MIN_SCORE <= self.score <= MAX_SCORE):
            raise DomainValidationError(
                f"score must be an integer in [{MIN_SCORE}, {MAX_SCORE}], got {self.score}"
            )
        if len(self.reason_codes) < 1:
            raise DomainValidationError("every score must carry at least one reason code")
        if not self.rubric_version.strip():
            raise DomainValidationError("rubric_version is required")
        if not self.model_version.strip():
            raise DomainValidationError("model_version is required")

        if self.score > 0:
            if len(self.evidence_links) < 1:
                raise DomainValidationError(
                    "a score > 0 must link to at least one piece of evidence"
                )
            for rc in self.reason_codes:
                if len(rc.evidence_refs) < 1:
                    raise DomainValidationError(
                        f"reason code '{rc.code}' must link to evidence for a score > 0"
                    )
        else:  # score == 0 (No Evidence)
            has_gap = len(self.gaps) >= 1
            has_no_evidence_reason = any(rc.no_evidence for rc in self.reason_codes)
            if not (has_gap or has_no_evidence_reason):
                raise DomainValidationError(
                    "a score of 0 must contain an explicit gap or a no-evidence reason"
                )
        return self


class WeightedSummary(DomainModel):
    """A non-binding, non-decisional aggregate view of an evaluation.

    ``binding`` is pinned to ``False`` at the type level — a weighted summary
    can never be represented as a decision.
    """

    binding: Literal[False] = False
    disclaimer: str = (
        "ADVISORY — non-binding, non-decisional. A human decision is required."
    )
    note: str = ""


class FairnessReport(DomainModel):
    """Placeholder for the Consistency & Fairness Monitor output.

    Fairness/bias/standardization analysis is a later phase; this type only
    reserves the contract slot so evaluations can carry it once implemented.
    """

    generated: bool = False
    note: str = "Fairness analysis is deferred to a later phase."


class CandidateEvaluation(DomainModel):
    """A candidate's evaluation across all ten fixed capability layers."""

    evaluation_id: str
    candidate_id: str
    role_id: str
    rubric_version: str
    model_version: str
    layer_scores: tuple[LayerScore, ...]
    weighted_summary: WeightedSummary = WeightedSummary()
    fairness_report: Optional[FairnessReport] = None
    status: EvaluationStatus = EvaluationStatus.EVALUATED
    created_at: datetime = Field(default_factory=utc_now)
    version: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "CandidateEvaluation":
        if not self.evaluation_id.strip():
            raise DomainValidationError("evaluation_id is required")
        if not self.candidate_id.strip():
            raise DomainValidationError("candidate_id is required")
        if not self.role_id.strip():
            raise DomainValidationError("role_id is required")

        if len(self.layer_scores) != len(CapabilityLayer):
            raise DomainValidationError(
                f"exactly {len(CapabilityLayer)} layer scores are required, "
                f"got {len(self.layer_scores)}"
            )
        seen = [ls.layer_id for ls in self.layer_scores]
        if len(set(seen)) != len(CapabilityLayer):
            raise DomainValidationError(
                "each capability layer must appear exactly once"
            )
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    @property
    def is_blocked(self) -> bool:
        return self.status is EvaluationStatus.REVIEW_BLOCKED

    def as_status(self, status: EvaluationStatus, **changes: object) -> "CandidateEvaluation":
        """Return a new, higher-versioned evaluation with a changed status."""
        data = self.model_dump()
        data.update(changes)
        data["status"] = status
        data["version"] = self.version + 1
        return CandidateEvaluation(**data)
