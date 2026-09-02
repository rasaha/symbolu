"""Specification §8 — the research comparison plan shape.

``recommended`` records which methods the plan intends to exercise. It is not
a selection, an endorsement, an eligibility statement or an advisor output,
and no consumer may read it as one. No approval, pilot state, revision
lineage or reassessment trigger is specified in slice 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Tuple

from ..errors import ContractError, ContractErrorCode
from ._util import digest_of, require_member, require_nonblank, require_tzaware, settle_digest
from .assessment import USAGE_SCOPE_RESEARCH_ONLY
from .catalog import ReasoningMethodCatalogRef, ReasoningMethodRef
from .record import BindingRef
from .task_class import TaskClassIdentity

RESEARCH_PLAN_SCHEMA_VERSION = "reasoning_method.research_plan.v1"


class SamplingKind(str, Enum):
    PREREGISTERED = "PREREGISTERED"
    RISK_BASED = "RISK_BASED"
    RANDOMIZED = "RANDOMIZED"


@dataclass(frozen=True)
class ChallengerSamplingPolicy:
    kind: SamplingKind
    policy_ref: str
    declared_coverage_ref: str

    def __post_init__(self) -> None:
        require_member(self.kind, SamplingKind, "ChallengerSamplingPolicy.kind", ContractErrorCode.REF_BLANK_FIELD)
        require_nonblank(self.policy_ref, "ChallengerSamplingPolicy.policy_ref")
        require_nonblank(self.declared_coverage_ref, "ChallengerSamplingPolicy.declared_coverage_ref")


@dataclass(frozen=True)
class ResearchComparisonPlan:
    schema_version: str
    plan_id: str
    task_class: TaskClassIdentity
    binding: BindingRef
    catalog: ReasoningMethodCatalogRef
    baseline: ReasoningMethodRef
    recommended: Tuple[ReasoningMethodRef, ...]
    challengers: ChallengerSamplingPolicy
    usage_scope: str
    preregistered_by: str
    preregistered_at: datetime
    plan_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "ResearchComparisonPlan.schema_version")
        require_nonblank(self.plan_id, "ResearchComparisonPlan.plan_id")
        if not isinstance(self.task_class, TaskClassIdentity):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ResearchComparisonPlan.task_class must be a TaskClassIdentity")
        if not isinstance(self.binding, BindingRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ResearchComparisonPlan.binding must be a BindingRef")
        if not isinstance(self.catalog, ReasoningMethodCatalogRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ResearchComparisonPlan.catalog must be a ReasoningMethodCatalogRef")
        if not isinstance(self.baseline, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ResearchComparisonPlan.baseline must be a ReasoningMethodRef")
        if not isinstance(self.recommended, tuple) or not all(isinstance(r, ReasoningMethodRef) for r in self.recommended):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ResearchComparisonPlan.recommended must be a tuple of ReasoningMethodRef (may be empty)")
        if not isinstance(self.challengers, ChallengerSamplingPolicy):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ResearchComparisonPlan.challengers must be a ChallengerSamplingPolicy")
        if self.usage_scope != USAGE_SCOPE_RESEARCH_ONLY:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"usage_scope is fixed at {USAGE_SCOPE_RESEARCH_ONLY} in slice 1")
        require_nonblank(self.preregistered_by, "ResearchComparisonPlan.preregistered_by")
        require_tzaware(self.preregistered_at, "ResearchComparisonPlan.preregistered_at")
        settle_digest(self, "plan_digest", digest_of(self, exclude=("plan_digest",)))


__all__ = ["RESEARCH_PLAN_SCHEMA_VERSION", "SamplingKind", "ChallengerSamplingPolicy", "ResearchComparisonPlan"]
