"""§6.1 Coverage report with validated integer counts and the anti-gaming rule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from ugence_reasoning_method_governance.api import ChallengerSamplingPolicy, ContractError, ContractErrorCode, FitOutcome, ReasoningMethodRef

from .._canon import require_digest
from ..errors import PilotError, PilotErrorCode
from .benchmark import require_count
from .manifest import PilotRole, PilotStudyManifest, ValidatedManifest


@dataclass(frozen=True)
class ChallengerCoverageReport:
    manifest_digest: str
    admissible_method_count: int
    methods_assigned: int
    methods_with_record: int
    baseline_has_record: bool
    qualified_declared: int
    qualified_with_record: int
    challengers_declared: int
    challengers_with_record: int
    methods_without_record: Tuple[ReasoningMethodRef, ...]
    sampling: ChallengerSamplingPolicy
    summary_permitted: bool

    def __post_init__(self) -> None:
        require_digest(self.manifest_digest, "ChallengerCoverageReport.manifest_digest")
        for name in ("admissible_method_count", "methods_assigned", "methods_with_record", "qualified_declared", "qualified_with_record", "challengers_declared", "challengers_with_record"):
            require_count(getattr(self, name), f"ChallengerCoverageReport.{name}")
        for name in ("baseline_has_record", "summary_permitted"):
            if not isinstance(getattr(self, name), bool):
                raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"ChallengerCoverageReport.{name} must be a bool")
        if not isinstance(self.methods_without_record, tuple) or not all(isinstance(m, ReasoningMethodRef) for m in self.methods_without_record):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "methods_without_record must be a tuple of ReasoningMethodRef")
        if not isinstance(self.sampling, ChallengerSamplingPolicy):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "sampling must be a ChallengerSamplingPolicy")
        if self.qualified_with_record > self.qualified_declared or self.challengers_with_record > self.challengers_declared or self.methods_with_record > self.methods_assigned:
            raise PilotError(PilotErrorCode.COUNT_INVALID, "a with_record count cannot exceed its declared count")
        expected = self.methods_with_record == self.methods_assigned and self.methods_assigned == self.admissible_method_count
        if self.summary_permitted != expected:
            raise PilotError(PilotErrorCode.COUNT_INVALID, "summary_permitted must be derived: every assigned method has a record and the assignment covers the admissible catalog")


def build_coverage_report(manifest: PilotStudyManifest, validated: ValidatedManifest, methods_with_record: Tuple[ReasoningMethodRef, ...]) -> ChallengerCoverageReport:
    if validated.manifest_digest != manifest.manifest_digest:
        raise PilotError(PilotErrorCode.MANIFEST_NOT_VALIDATED, "coverage report requires this manifest's ValidatedManifest")
    recorded = frozenset(methods_with_record)
    assigned = [m.method for m in manifest.methods]
    unknown = recorded - frozenset(assigned)
    if unknown:
        raise PilotError(PilotErrorCode.ROLE_INCONSISTENT, "a record exists for a method the manifest never assigned")
    qualified = manifest.methods_with_role(PilotRole.ADVISOR_QUALIFIED)
    challengers = manifest.methods_with_role(PilotRole.CHALLENGER)
    baseline = manifest.methods_with_role(PilotRole.GOVERNED_BASELINE)[0]
    admissible_count = len(validated.admissible_methods)
    return ChallengerCoverageReport(
        manifest_digest=manifest.manifest_digest,
        admissible_method_count=admissible_count,
        methods_assigned=len(assigned),
        methods_with_record=len([m for m in assigned if m in recorded]),
        baseline_has_record=baseline in recorded,
        qualified_declared=len(qualified),
        qualified_with_record=len([m for m in qualified if m in recorded]),
        challengers_declared=len(challengers),
        challengers_with_record=len([m for m in challengers if m in recorded]),
        methods_without_record=tuple(m for m in assigned if m not in recorded),
        sampling=manifest.plan.challengers,
        summary_permitted=(len([m for m in assigned if m in recorded]) == len(assigned) and len(assigned) == admissible_count),
    )


@dataclass(frozen=True)
class SuccessSummary:
    """Printed only when the coverage report permits it. Precision divides by qualified_declared."""

    qualified_declared: int
    admissible_method_count: int
    qualified_pareto_efficient: int
    challengers_with_record: int
    challengers_declared: int

    def line(self) -> str:
        return (
            f"qualifying-set success: {self.qualified_pareto_efficient} of {self.qualified_declared} qualified methods SUFFICIENT_PARETO_EFFICIENT | "
            f"qualifying-set size {self.qualified_declared}/{self.admissible_method_count} | set precision {self.qualified_pareto_efficient}/{self.qualified_declared} | "
            f"challenger coverage {self.challengers_with_record}/{self.challengers_declared} | RESEARCH_ONLY"
        )


def success_summary(report: ChallengerCoverageReport, manifest: PilotStudyManifest, outcomes: Mapping[ReasoningMethodRef, FitOutcome]) -> Optional[SuccessSummary]:
    """None when the report forbids a summary. Counts SUFFICIENT_PARETO_EFFICIENT only."""
    if not report.summary_permitted:
        return None
    qualified = manifest.methods_with_role(PilotRole.ADVISOR_QUALIFIED)
    efficient = len([m for m in qualified if outcomes.get(m) is FitOutcome.SUFFICIENT_PARETO_EFFICIENT])
    return SuccessSummary(report.qualified_declared, report.admissible_method_count, efficient, report.challengers_with_record, report.challengers_declared)


__all__ = ["ChallengerCoverageReport", "build_coverage_report", "SuccessSummary", "success_summary"]
