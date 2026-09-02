"""Specification §3 — task profile, task-class identity, comparison policy.

The constructor checks SHAPE only. The high-consequence rule (Workflow-Fit
§11.3) requires a ``MATERIAL``/``SEVERE`` threshold-based class to carry an
``EvidenceAdmissionRef``; presence of that reference admits nothing — the
engine (§7) requires a matching ``ResolvedAdmission``, and even that is
requester-asserted in slice 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from ugence_uvi_policy_contracts.api import GovernedThreshold

from ..errors import ContractError, ContractErrorCode
from ._util import (
    digest_of,
    require_digest,
    require_member,
    require_nonblank,
    require_str_tuple,
    require_tzaware,
    settle_digest,
)
from .catalog import COMPLEXITY_SIGNAL_TOKENS

PROFILE_SCHEMA_VERSION = "reasoning_method.task_profile.v1"
TASK_CLASS_SCHEMA_VERSION = "reasoning_method.task_class.v1"


class TaskReversibility(str, Enum):
    """Task-class reversibility: whether the task's delivered OUTCOME can be
    undone. Distinct from action-level reversibility in the experimental
    runtime; not mirrored from it (spec 3.2-A)."""

    OUTCOME_REVERSIBLE = "OUTCOME_REVERSIBLE"
    OUTCOME_COMPENSATABLE = "OUTCOME_COMPENSATABLE"
    OUTCOME_IRREVERSIBLE = "OUTCOME_IRREVERSIBLE"
    UNDETERMINED = "UNDETERMINED"


class ConsequenceClass(str, Enum):
    NEGLIGIBLE = "NEGLIGIBLE"
    RECOVERABLE = "RECOVERABLE"
    MATERIAL = "MATERIAL"
    SEVERE = "SEVERE"


HIGH_CONSEQUENCE_CLASSES = frozenset({ConsequenceClass.MATERIAL, ConsequenceClass.SEVERE})


class SufficiencyKind(str, Enum):
    THRESHOLD_BASED = "THRESHOLD_BASED"
    IMPROVEMENT_VALUED = "IMPROVEMENT_VALUED"


class ResourceDimension(str, Enum):
    LLM_CALLS = "LLM_CALLS"
    TOTAL_TOKENS = "TOTAL_TOKENS"


RESOURCE_DIMENSION_ORDER: Tuple[ResourceDimension, ...] = tuple(ResourceDimension)


@dataclass(frozen=True)
class AggregationRef:
    aggregation_method_id: str
    aggregation_method_version: str
    calculation_ref: str

    def __post_init__(self) -> None:
        require_nonblank(self.aggregation_method_id, "AggregationRef.aggregation_method_id")
        require_nonblank(self.aggregation_method_version, "AggregationRef.aggregation_method_version")
        require_nonblank(self.calculation_ref, "AggregationRef.calculation_ref")


@dataclass(frozen=True)
class EvidenceAdmissionRef:
    authority_identity: str
    authority_result_ref: str
    admitted_digest: str

    def __post_init__(self) -> None:
        require_nonblank(self.authority_identity, "EvidenceAdmissionRef.authority_identity")
        require_nonblank(self.authority_result_ref, "EvidenceAdmissionRef.authority_result_ref")
        require_digest(self.admitted_digest, "EvidenceAdmissionRef.admitted_digest")


@dataclass(frozen=True)
class SufficiencyRule:
    rule_id: str
    rule_version: str
    kind: SufficiencyKind
    threshold: GovernedThreshold
    supporting_evidence_admission: Optional[EvidenceAdmissionRef] = None

    def __post_init__(self) -> None:
        require_nonblank(self.rule_id, "SufficiencyRule.rule_id")
        require_nonblank(self.rule_version, "SufficiencyRule.rule_version")
        require_member(self.kind, SufficiencyKind, "SufficiencyRule.kind", ContractErrorCode.REF_BLANK_FIELD)
        if not isinstance(self.threshold, GovernedThreshold):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "SufficiencyRule.threshold must be a GovernedThreshold")
        if self.supporting_evidence_admission is not None and not isinstance(
            self.supporting_evidence_admission, EvidenceAdmissionRef
        ):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "SufficiencyRule.supporting_evidence_admission must be an EvidenceAdmissionRef or None")


@dataclass(frozen=True)
class ComparisonPolicy:
    policy_id: str
    policy_version: str
    sufficiency: SufficiencyRule
    required_dimensions: Tuple[ResourceDimension, ...]
    quality_aggregation: Optional[AggregationRef]

    def __post_init__(self) -> None:
        require_nonblank(self.policy_id, "ComparisonPolicy.policy_id")
        require_nonblank(self.policy_version, "ComparisonPolicy.policy_version")
        if not isinstance(self.sufficiency, SufficiencyRule):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ComparisonPolicy.sufficiency must be a SufficiencyRule")
        dims = self.required_dimensions
        if not isinstance(dims, tuple) or not dims:
            raise ContractError(ContractErrorCode.DIMENSIONS_EMPTY, "ComparisonPolicy.required_dimensions must be a non-empty tuple")
        for d in dims:
            require_member(d, ResourceDimension, "ComparisonPolicy.required_dimensions item", ContractErrorCode.DIMENSIONS_UNSORTED)
        order = [RESOURCE_DIMENSION_ORDER.index(d) for d in dims]
        if len(set(order)) != len(order) or order != sorted(order):
            raise ContractError(ContractErrorCode.DIMENSIONS_UNSORTED, "ComparisonPolicy.required_dimensions must be unique and in ResourceDimension member order")
        if self.quality_aggregation is not None and not isinstance(self.quality_aggregation, AggregationRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ComparisonPolicy.quality_aggregation must be an AggregationRef or None")


def _validate_coordinates(obj: object, prefix: str) -> None:
    require_nonblank(getattr(obj, "domain_ref"), f"{prefix}.domain_ref")
    require_nonblank(getattr(obj, "intended_outcome_ref"), f"{prefix}.intended_outcome_ref")
    require_member(getattr(obj, "consequence_class"), ConsequenceClass, f"{prefix}.consequence_class", ContractErrorCode.REF_BLANK_FIELD)
    require_member(getattr(obj, "reversibility"), TaskReversibility, f"{prefix}.reversibility", ContractErrorCode.REF_BLANK_FIELD)
    require_str_tuple(getattr(obj, "evidence_requirement_refs"), f"{prefix}.evidence_requirement_refs")
    require_str_tuple(getattr(obj, "tool_requirement_refs"), f"{prefix}.tool_requirement_refs")
    tokens = require_str_tuple(getattr(obj, "structural_characteristics"), f"{prefix}.structural_characteristics")
    unknown = sorted(set(tokens) - COMPLEXITY_SIGNAL_TOKENS)
    if unknown:
        raise ContractError(ContractErrorCode.SIGNAL_TOKEN_UNKNOWN, f"{prefix}.structural_characteristics unknown token(s): {', '.join(unknown)}")
    require_nonblank(getattr(obj, "population_ref"), f"{prefix}.population_ref")


@dataclass(frozen=True)
class TaskProfile:
    schema_version: str
    profile_id: str
    domain_ref: str
    intended_outcome_ref: str
    consequence_class: ConsequenceClass
    reversibility: TaskReversibility
    evidence_requirement_refs: Tuple[str, ...]
    tool_requirement_refs: Tuple[str, ...]
    structural_characteristics: Tuple[str, ...]
    population_ref: str
    policy_refs: Tuple[str, ...] = ()
    declared_by: str = ""
    declared_at: Optional[datetime] = None
    assertion_basis: str = "DEVELOPER_REPORTED"

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "TaskProfile.schema_version")
        require_nonblank(self.profile_id, "TaskProfile.profile_id")
        _validate_coordinates(self, "TaskProfile")
        require_str_tuple(self.policy_refs, "TaskProfile.policy_refs")
        if self.declared_at is not None:
            require_tzaware(self.declared_at, "TaskProfile.declared_at")
        if self.assertion_basis != "DEVELOPER_REPORTED":
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "TaskProfile.assertion_basis is fixed at DEVELOPER_REPORTED")


@dataclass(frozen=True)
class TaskClassIdentity:
    schema_version: str
    task_class_id: str
    domain_ref: str
    intended_outcome_ref: str
    consequence_class: ConsequenceClass
    reversibility: TaskReversibility
    evidence_requirement_refs: Tuple[str, ...]
    tool_requirement_refs: Tuple[str, ...]
    structural_characteristics: Tuple[str, ...]
    population_ref: str
    benchmark_set_ref: str
    benchmark_set_digest: str
    comparison_policy: ComparisonPolicy
    task_class_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "TaskClassIdentity.schema_version")
        require_nonblank(self.task_class_id, "TaskClassIdentity.task_class_id")
        _validate_coordinates(self, "TaskClassIdentity")
        if self.reversibility is TaskReversibility.UNDETERMINED:
            raise ContractError(ContractErrorCode.REVERSIBILITY_UNDETERMINED_ON_CLASS, "a task class must state its outcome reversibility")
        require_nonblank(self.benchmark_set_ref, "TaskClassIdentity.benchmark_set_ref")
        require_digest(self.benchmark_set_digest, "TaskClassIdentity.benchmark_set_digest")
        if not isinstance(self.comparison_policy, ComparisonPolicy):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "TaskClassIdentity.comparison_policy must be a ComparisonPolicy")
        rule = self.comparison_policy.sufficiency
        if (
            self.consequence_class in HIGH_CONSEQUENCE_CLASSES
            and rule.kind is SufficiencyKind.THRESHOLD_BASED
            and rule.supporting_evidence_admission is None
        ):
            raise ContractError(
                ContractErrorCode.ADMISSION_REF_REQUIRED,
                "a MATERIAL or SEVERE class with threshold-based sufficiency must reference an evidence admission (Workflow-Fit §11.3); the reference is shape, not admission",
            )
        # Digest payload rule (§3): every field except the digest, with the ENTIRE
        # comparison policy including the GovernedThreshold's content.
        settle_digest(self, "task_class_digest", digest_of(self, exclude=("task_class_digest",)))


def compatible(a: TaskClassIdentity, b: TaskClassIdentity) -> bool:
    return a.task_class_digest == b.task_class_digest


__all__ = [
    "PROFILE_SCHEMA_VERSION",
    "TASK_CLASS_SCHEMA_VERSION",
    "TaskReversibility",
    "ConsequenceClass",
    "HIGH_CONSEQUENCE_CLASSES",
    "SufficiencyKind",
    "ResourceDimension",
    "RESOURCE_DIMENSION_ORDER",
    "AggregationRef",
    "EvidenceAdmissionRef",
    "SufficiencyRule",
    "ComparisonPolicy",
    "TaskProfile",
    "TaskClassIdentity",
    "compatible",
]
