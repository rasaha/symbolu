"""Specification §5 — fit outcomes, quality results, deltas, the fit assessment.

A bare ``ReasoningMethodFitAssessment`` outside a ``ReadinessComparisonResult``
is not a governed object (§7): its internal invariants are engine obligations.
The constructor here checks shape and settles the digest only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from ..errors import ContractError, ContractErrorCode
from ._util import (
    digest_of,
    require_decimal_string,
    require_digest,
    require_member,
    require_nonblank,
    require_str_tuple,
    require_tzaware,
    settle_digest,
)
from .catalog import ReasoningMethodRef
from .task_class import RESOURCE_DIMENSION_ORDER, AggregationRef, ResourceDimension

FIT_SCHEMA_VERSION = "reasoning_method.fit_assessment.v1"
EVIDENCE_STATUS_SOURCE_V1 = "RECORD_CONSTANTS_V1"
USAGE_SCOPE_RESEARCH_ONLY = "RESEARCH_ONLY"


class FitOutcome(str, Enum):
    INSUFFICIENT_QUALITY = "INSUFFICIENT_QUALITY"
    SUFFICIENT_RESOURCE_DOMINATED = "SUFFICIENT_RESOURCE_DOMINATED"
    SUFFICIENT_PARETO_EFFICIENT = "SUFFICIENT_PARETO_EFFICIENT"
    COMPARISON_EVIDENCE_ABSENT = "COMPARISON_EVIDENCE_ABSENT"


class QualityDirection(str, Enum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


@dataclass(frozen=True)
class QualityResult:
    method: ReasoningMethodRef
    claim_ref: str
    governed_unit: str
    value: str
    aggregation: Optional[AggregationRef]

    def __post_init__(self) -> None:
        if not isinstance(self.method, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "QualityResult.method must be a ReasoningMethodRef")
        require_nonblank(self.claim_ref, "QualityResult.claim_ref")
        require_nonblank(self.governed_unit, "QualityResult.governed_unit")
        # The value is carried verbatim; the ENGINE refuses a non-decimal with
        # SCALE_UNSUPPORTED (§5 rule 1), so the constructor only requires a string.
        if not isinstance(self.value, str) or not self.value.strip():
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "QualityResult.value must be a non-blank string")
        if self.aggregation is not None and not isinstance(self.aggregation, AggregationRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "QualityResult.aggregation must be an AggregationRef or None")


@dataclass(frozen=True)
class ResourceDelta:
    dimension: ResourceDimension
    relative_to: ReasoningMethodRef
    delta: str

    def __post_init__(self) -> None:
        require_member(self.dimension, ResourceDimension, "ResourceDelta.dimension", ContractErrorCode.DIMENSIONS_UNSORTED)
        if not isinstance(self.relative_to, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ResourceDelta.relative_to must be a ReasoningMethodRef")
        require_decimal_string(self.delta, "ResourceDelta.delta")


@dataclass(frozen=True)
class DominationRecord:
    dominator: ReasoningMethodRef
    deltas: Tuple[ResourceDelta, ...]
    quality_delta: Optional[str]

    def __post_init__(self) -> None:
        if not isinstance(self.dominator, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "DominationRecord.dominator must be a ReasoningMethodRef")
        _require_delta_order(self.deltas, "DominationRecord.deltas")
        for d in self.deltas:
            if d.relative_to != self.dominator:
                raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "DominationRecord.deltas must be relative to the dominator")
        if self.quality_delta is not None:
            require_decimal_string(self.quality_delta, "DominationRecord.quality_delta")


def _require_delta_order(deltas: object, name: str) -> None:
    if not isinstance(deltas, tuple) or not all(isinstance(d, ResourceDelta) for d in deltas):
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be a tuple of ResourceDelta")
    order = [RESOURCE_DIMENSION_ORDER.index(d.dimension) for d in deltas]
    if order != sorted(order) or len(set(order)) != len(order):
        raise ContractError(ContractErrorCode.DIMENSIONS_UNSORTED, f"{name} must follow ResourceDimension member order without repeats")


@dataclass(frozen=True)
class ReasoningMethodFitAssessment:
    schema_version: str
    assessment_id: str
    task_class_ref: str
    task_class_digest: str
    binding_digest: str
    selection_policy_ref: str
    method: ReasoningMethodRef
    baseline: ReasoningMethodRef
    outcome: FitOutcome
    quality_direction: Optional[QualityDirection]
    quality_margin: Optional[str]
    deltas_vs_baseline: Tuple[ResourceDelta, ...]
    dominated_by: Tuple[DominationRecord, ...]
    dimensions_compared: Tuple[ResourceDimension, ...]
    comparison_policy_id: str
    comparison_policy_version: str
    quality_result_ref: str
    input_record_digests: Tuple[str, ...]
    evidence_status_source: str
    usage_scope: str
    assessor_identity: str
    engine_version: str
    assessed_at: datetime
    reason: str
    assessment_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "ReasoningMethodFitAssessment.schema_version")
        require_nonblank(self.assessment_id, "ReasoningMethodFitAssessment.assessment_id")
        require_nonblank(self.task_class_ref, "ReasoningMethodFitAssessment.task_class_ref")
        require_digest(self.task_class_digest, "ReasoningMethodFitAssessment.task_class_digest")
        require_digest(self.binding_digest, "ReasoningMethodFitAssessment.binding_digest")
        if not isinstance(self.selection_policy_ref, str):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "selection_policy_ref must be a string (may be empty)")
        for name in ("method", "baseline"):
            if not isinstance(getattr(self, name), ReasoningMethodRef):
                raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"ReasoningMethodFitAssessment.{name} must be a ReasoningMethodRef")
        require_member(self.outcome, FitOutcome, "ReasoningMethodFitAssessment.outcome", ContractErrorCode.REF_BLANK_FIELD)
        if self.quality_direction is not None:
            require_member(self.quality_direction, QualityDirection, "quality_direction", ContractErrorCode.REF_BLANK_FIELD)
        if self.quality_margin is not None:
            require_decimal_string(self.quality_margin, "ReasoningMethodFitAssessment.quality_margin")
        _require_delta_order(self.deltas_vs_baseline, "ReasoningMethodFitAssessment.deltas_vs_baseline")
        for d in self.deltas_vs_baseline:
            if d.relative_to != self.baseline:
                raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "deltas_vs_baseline must be relative to the baseline")
        if not isinstance(self.dominated_by, tuple) or not all(isinstance(x, DominationRecord) for x in self.dominated_by):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "dominated_by must be a tuple of DominationRecord")
        keys = [x.dominator.sort_key for x in self.dominated_by]
        if keys != sorted(keys):
            raise ContractError(ContractErrorCode.DIMENSIONS_UNSORTED, "dominated_by must be ordered by (method_id, method_version)")
        if not isinstance(self.dimensions_compared, tuple) or not all(isinstance(d, ResourceDimension) for d in self.dimensions_compared):
            raise ContractError(ContractErrorCode.DIMENSIONS_UNSORTED, "dimensions_compared must be a tuple of ResourceDimension")
        require_nonblank(self.comparison_policy_id, "comparison_policy_id")
        require_nonblank(self.comparison_policy_version, "comparison_policy_version")
        if not isinstance(self.quality_result_ref, str):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "quality_result_ref must be a string (may be empty when absent)")
        require_str_tuple(self.input_record_digests, "input_record_digests")
        for d in self.input_record_digests:
            require_digest(d, "input_record_digests item")
        if self.evidence_status_source != EVIDENCE_STATUS_SOURCE_V1:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"evidence_status_source is fixed at {EVIDENCE_STATUS_SOURCE_V1} in slice 1")
        if self.usage_scope != USAGE_SCOPE_RESEARCH_ONLY:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"usage_scope is fixed at {USAGE_SCOPE_RESEARCH_ONLY} in slice 1")
        require_nonblank(self.assessor_identity, "assessor_identity")
        require_nonblank(self.engine_version, "engine_version")
        require_tzaware(self.assessed_at, "assessed_at")
        if not isinstance(self.reason, str):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "reason must be a string")
        settle_digest(self, "assessment_digest", digest_of(self, exclude=("assessment_digest",)))

    def stable_payload(self) -> dict:
        """The assessment with time and self-digest removed, for result digests."""
        from ._util import payload

        return payload(self, exclude=("assessment_digest", "assessed_at"))


__all__ = [
    "FIT_SCHEMA_VERSION",
    "EVIDENCE_STATUS_SOURCE_V1",
    "USAGE_SCOPE_RESEARCH_ONLY",
    "FitOutcome",
    "QualityDirection",
    "QualityResult",
    "ResourceDelta",
    "DominationRecord",
    "ReasoningMethodFitAssessment",
]
