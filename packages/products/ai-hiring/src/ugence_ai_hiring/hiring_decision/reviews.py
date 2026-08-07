"""Post-hire review and calibration models (1 / 3 / 6 / 12 month).

Every hire is a prediction measured against observed outcomes. Calibration
**proposes/versions Decision Contract or role-policy changes** — it never
retrains hidden model weights and never edits a past recommendation. A
calibration proposal recompiles the policy into the next contract version through
the governed authoring path (spec §12).
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field, model_validator

from ..common import new_id
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .enums import (
    CalibrationTarget,
    OutcomeEvidenceType,
    ReviewCheckpoint,
    Trajectory,
)
from .refs import ContractRef


class ReviewObservation(DomainModel):
    """Predicted vs observed for one dimension at a checkpoint."""

    dimension: str
    predicted: Optional[float] = None
    observed: Optional[float] = None
    outcome_evidence: tuple[OutcomeEvidenceType, ...] = ()

    @property
    def delta(self) -> Optional[float]:
        if self.predicted is None or self.observed is None:
            return None
        return round(self.observed - self.predicted, 9)


class ReviewRecord(DomainModel):
    """A post-hire review at one checkpoint."""

    review_id: str = Field(default_factory=lambda: new_id("hrev"))
    case_id: str
    checkpoint: ReviewCheckpoint
    contract_ref: ContractRef
    observations: tuple[ReviewObservation, ...] = ()
    trajectory: Trajectory = Trajectory.ON_TRACK

    @model_validator(mode="after")
    def _validate(self) -> "ReviewRecord":
        if not self.case_id.strip():
            raise DomainValidationError("case_id is required")
        return self


class CalibrationProposal(DomainModel):
    """A governed proposal to recompile the policy into the next contract version.

    Proposes/versions contract or role-policy changes only. Never retrains hidden
    weights; never edits history. Applies to a *future* contract version.
    """

    proposal_id: str = Field(default_factory=lambda: new_id("hcal"))
    source_case_id: str
    contract_ref: ContractRef
    targets: tuple[CalibrationTarget, ...]
    rationale: str
    recompile_policy_id: str
    proposed_contract_version: int
    status: str = "PROPOSED"

    @model_validator(mode="after")
    def _validate(self) -> "CalibrationProposal":
        if not self.targets:
            raise DomainValidationError("a calibration proposal must name at least one target")
        if not self.rationale.strip():
            raise DomainValidationError("rationale is required")
        if not self.recompile_policy_id.strip():
            raise DomainValidationError(
                "recompile_policy_id is required — calibration recompiles a policy, "
                "it never retrains hidden weights"
            )
        if self.proposed_contract_version <= self.contract_ref.version:
            raise DomainValidationError(
                "proposed_contract_version must be greater than the current version"
            )
        return self
