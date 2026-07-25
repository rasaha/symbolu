"""Rubric validation — deterministic contract checks (no scoring).

Validates a rubric against the ontology and the frozen vocabularies. Returns a
typed result with issues; it does not raise (callers decide). Publishing requires
a valid result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..errors import CapabilityCycleError
from ..ontology.capability import CapabilityStatus
from ..ontology.registry import build_graph
from ..repositories.ontology_repository import OntologyRepository
from ..rubrics.rubric import Rubric
from ..rubrics.scoring_scale import is_standard_scale

WEIGHT_TOLERANCE = 1e-6


class IssueCode(str, Enum):
    NO_CAPABILITIES = "NO_CAPABILITIES"
    DUPLICATE_CAPABILITY = "DUPLICATE_CAPABILITY"
    WEIGHT_TOTAL_INVALID = "WEIGHT_TOTAL_INVALID"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    CAPABILITY_VERSION_MISMATCH = "CAPABILITY_VERSION_MISMATCH"
    UNPUBLISHED_CAPABILITY = "UNPUBLISHED_CAPABILITY"
    UNKNOWN_SCORING_SCALE = "UNKNOWN_SCORING_SCALE"
    CIRCULAR_ONTOLOGY = "CIRCULAR_ONTOLOGY"
    REASON_CODE_NOT_ALLOWED = "REASON_CODE_NOT_ALLOWED"


@dataclass(frozen=True)
class ValidationIssue:
    code: IssueCode
    message: str


@dataclass(frozen=True)
class RubricValidationResult:
    valid: bool
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(i.code.value for i in self.issues)


class RubricValidationService:
    def __init__(self, ontology_repository: OntologyRepository) -> None:
        self._ontology = ontology_repository

    def validate(self, rubric: Rubric) -> RubricValidationResult:
        issues: list[ValidationIssue] = []

        # scale ids known to this rubric (standard + declared custom)
        custom_ids = {s.scale_id for s in rubric.custom_scales}

        def scale_known(scale_id: str) -> bool:
            return is_standard_scale(scale_id) or scale_id in custom_ids

        if not rubric.capabilities:
            issues.append(ValidationIssue(IssueCode.NO_CAPABILITIES,
                                          "rubric declares no capabilities"))

        # duplicate capabilities
        seen: set[str] = set()
        for rc in rubric.capabilities:
            if rc.capability_id in seen:
                issues.append(ValidationIssue(
                    IssueCode.DUPLICATE_CAPABILITY,
                    f"capability '{rc.capability_id}' appears more than once"))
            seen.add(rc.capability_id)

        # weight total
        if rubric.capabilities:
            total = sum(rc.weight for rc in rubric.capabilities)
            if abs(total - 1.0) > WEIGHT_TOLERANCE:
                issues.append(ValidationIssue(
                    IssueCode.WEIGHT_TOTAL_INVALID,
                    f"capability weights sum to {total:.4f}, expected 1.0"))

        # default + per-capability scoring scales
        if not scale_known(rubric.default_scoring_scale_id):
            issues.append(ValidationIssue(
                IssueCode.UNKNOWN_SCORING_SCALE,
                f"unknown default scale '{rubric.default_scoring_scale_id}'"))

        # capability references + reason codes + scales
        rubric_reason_codes = set(rubric.allowed_reason_codes)
        for rc in rubric.capabilities:
            if not scale_known(rc.scoring_scale_id):
                issues.append(ValidationIssue(
                    IssueCode.UNKNOWN_SCORING_SCALE,
                    f"capability '{rc.capability_id}' references unknown scale "
                    f"'{rc.scoring_scale_id}'"))
            if not self._ontology.exists(rc.capability_id):
                issues.append(ValidationIssue(
                    IssueCode.UNKNOWN_CAPABILITY,
                    f"unknown capability '{rc.capability_id}'"))
            else:
                try:
                    cap = self._ontology.get_version(rc.capability_id, rc.capability_version)
                except Exception:  # noqa: BLE001
                    issues.append(ValidationIssue(
                        IssueCode.CAPABILITY_VERSION_MISMATCH,
                        f"capability '{rc.capability_id}' has no version "
                        f"{rc.capability_version}"))
                    cap = None
                if cap is not None and cap.status is not CapabilityStatus.PUBLISHED:
                    issues.append(ValidationIssue(
                        IssueCode.UNPUBLISHED_CAPABILITY,
                        f"capability '{rc.capability_id}' v{rc.capability_version} "
                        f"is {cap.status.value}, not PUBLISHED"))
            # per-capability reason codes must be a subset of the rubric's
            for code in rc.allowed_reason_codes:
                if rubric_reason_codes and code not in rubric_reason_codes:
                    issues.append(ValidationIssue(
                        IssueCode.REASON_CODE_NOT_ALLOWED,
                        f"reason code '{code.value}' for '{rc.capability_id}' is not "
                        "in the rubric's allowed set"))

        # circular ontology (the ontology as a whole must be acyclic)
        try:
            build_graph(self._ontology.list_latest()).validate()
        except CapabilityCycleError as exc:
            issues.append(ValidationIssue(IssueCode.CIRCULAR_ONTOLOGY, str(exc)))
        except Exception:  # noqa: BLE001 - missing parents are not this check's concern
            pass

        return RubricValidationResult(valid=not issues, issues=tuple(issues))
