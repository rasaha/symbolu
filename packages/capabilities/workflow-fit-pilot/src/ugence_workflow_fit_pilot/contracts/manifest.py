"""§3.1 Preregistered pilot manifest, its shape obligations, and pre-execution
validation against the full catalog, rule set and advisory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import FrozenSet, Optional, Tuple

from ugence_reasoning_method_advisor.api import ReasoningMethodAdvisory, RuleSet, RuleSetRef
from ugence_reasoning_method_governance.api import (
    AggregationRef,
    ContractError,
    ContractErrorCode,
    ReasoningMethodCatalog,
    ReasoningMethodRef,
    ResearchComparisonPlan,
    SamplingKind,
    USAGE_SCOPE_RESEARCH_ONLY,
)

from .._canon import digest_of, require_digest, require_member, require_nonblank, require_str_tuple, require_tzaware, settle_digest
from ..errors import PilotError, PilotErrorCode
from ..version import __version__
from .benchmark import BenchmarkManifest
from .evaluator import QualityEvaluatorDeclaration

PILOT_MANIFEST_SCHEMA_VERSION = "workflow_fit_pilot.manifest.v1"
PREREGISTRATION_DECLARED_UNVERIFIED = "DECLARED_UNVERIFIED"
ATTESTABLE_TELEMETRY_FIELDS: Tuple[str, ...] = (
    "telemetry.llm_calls",
    "telemetry.token_usage.input_tokens",
    "telemetry.token_usage.output_tokens",
    "telemetry.token_usage.total_tokens",
)
LLM_CALLS_FIELD = "telemetry.llm_calls"


class PilotRole(str, Enum):
    GOVERNED_BASELINE = "GOVERNED_BASELINE"
    ADVISOR_QUALIFIED = "ADVISOR_QUALIFIED"
    CHALLENGER = "CHALLENGER"


_ROLE_ORDER = tuple(PilotRole)


def sorted_roles(roles) -> Tuple[PilotRole, ...]:
    return tuple(sorted(set(roles), key=_ROLE_ORDER.index))


@dataclass(frozen=True)
class PilotMethodAssignment:
    method: ReasoningMethodRef
    roles: Tuple[PilotRole, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.method, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "PilotMethodAssignment.method must be a ReasoningMethodRef")
        if not isinstance(self.roles, tuple) or not self.roles or not all(isinstance(r, PilotRole) for r in self.roles):
            raise PilotError(PilotErrorCode.ROLE_INCONSISTENT, "roles must be a non-empty tuple of PilotRole")
        if self.roles != sorted_roles(self.roles):
            raise PilotError(PilotErrorCode.ROLE_INCONSISTENT, "roles must be in member order without repeats")


@dataclass(frozen=True)
class CaptureBoundaryDeclaration:
    boundary_identity: str
    boundary_version: str
    process_separation_ref: str
    port_ref: str
    allowed_attested_fields: Tuple[str, ...]

    def __post_init__(self) -> None:
        require_nonblank(self.boundary_identity, "CaptureBoundaryDeclaration.boundary_identity")
        require_nonblank(self.boundary_version, "CaptureBoundaryDeclaration.boundary_version")
        require_nonblank(self.process_separation_ref, "CaptureBoundaryDeclaration.process_separation_ref")
        require_nonblank(self.port_ref, "CaptureBoundaryDeclaration.port_ref")
        require_str_tuple(self.allowed_attested_fields, "CaptureBoundaryDeclaration.allowed_attested_fields")
        if not set(self.allowed_attested_fields) <= set(ATTESTABLE_TELEMETRY_FIELDS) or LLM_CALLS_FIELD not in self.allowed_attested_fields:
            raise PilotError(PilotErrorCode.ATTESTED_FIELDS_INVALID, "allowed_attested_fields must be a subset of ATTESTABLE_TELEMETRY_FIELDS containing telemetry.llm_calls")
        if len(set(self.allowed_attested_fields)) != len(self.allowed_attested_fields):
            raise PilotError(PilotErrorCode.ATTESTED_FIELDS_INVALID, "allowed_attested_fields must not repeat")


@dataclass(frozen=True)
class PilotStudyManifest:
    schema_version: str
    manifest_id: str
    plan: ResearchComparisonPlan
    advisory_digest: Optional[str]
    rule_set: Optional[RuleSetRef]
    methods: Tuple[PilotMethodAssignment, ...]
    benchmark: BenchmarkManifest
    capture_boundary: CaptureBoundaryDeclaration
    evaluator: QualityEvaluatorDeclaration
    resource_aggregation: AggregationRef
    quality_aggregation: AggregationRef
    preregistered_by: str
    preregistered_at: datetime
    preregistration_status: str = PREREGISTRATION_DECLARED_UNVERIFIED
    usage_scope: str = USAGE_SCOPE_RESEARCH_ONLY
    manifest_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "PilotStudyManifest.schema_version")
        require_nonblank(self.manifest_id, "PilotStudyManifest.manifest_id")
        if not isinstance(self.plan, ResearchComparisonPlan):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "PilotStudyManifest.plan must be a ResearchComparisonPlan")
        if self.advisory_digest is not None:
            require_digest(self.advisory_digest, "PilotStudyManifest.advisory_digest")
        if (self.rule_set is None) != (self.advisory_digest is None):
            raise PilotError(PilotErrorCode.ADVISORY_REQUIRED, "rule_set is present iff advisory_digest is present")
        if self.rule_set is not None and not isinstance(self.rule_set, RuleSetRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "PilotStudyManifest.rule_set must be a RuleSetRef or None")
        if not isinstance(self.methods, tuple) or not self.methods or not all(isinstance(m, PilotMethodAssignment) for m in self.methods):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "PilotStudyManifest.methods must be a non-empty tuple of PilotMethodAssignment")
        keys = [m.method.sort_key for m in self.methods]
        if len(set(keys)) != len(keys):
            raise PilotError(PilotErrorCode.METHOD_DUPLICATE, "a method appears twice in the manifest")
        if keys != sorted(keys):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "PilotStudyManifest.methods must be ordered by (method_id, method_version)")
        baselines = [m for m in self.methods if PilotRole.GOVERNED_BASELINE in m.roles]
        if len(baselines) != 1 or baselines[0].method != self.plan.baseline:
            raise PilotError(PilotErrorCode.ROLE_INCONSISTENT, "exactly one GOVERNED_BASELINE assignment whose method equals plan.baseline is required")
        if any(PilotRole.ADVISOR_QUALIFIED in m.roles for m in self.methods) and self.advisory_digest is None:
            raise PilotError(PilotErrorCode.ADVISORY_REQUIRED, "an ADVISOR_QUALIFIED role requires advisory_digest and rule_set")
        assigned = {m.method for m in self.methods}
        for r in self.plan.recommended:
            if r not in assigned:
                raise PilotError(PilotErrorCode.COMPOSITION_INCOMPLETE, f"plan.recommended member {r.method_id} is not assigned")
        if not isinstance(self.benchmark, BenchmarkManifest):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "PilotStudyManifest.benchmark must be a BenchmarkManifest")
        if self.benchmark.benchmark_manifest_digest != self.plan.task_class.benchmark_set_digest:
            raise PilotError(PilotErrorCode.BENCHMARK_MANIFEST_MISMATCH, "benchmark manifest digest must equal the task class's benchmark_set_digest")
        if not isinstance(self.capture_boundary, CaptureBoundaryDeclaration):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "PilotStudyManifest.capture_boundary must be a CaptureBoundaryDeclaration")
        if not isinstance(self.evaluator, QualityEvaluatorDeclaration):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "PilotStudyManifest.evaluator must be a QualityEvaluatorDeclaration")
        if self.evaluator.benchmark_manifest_digest != self.benchmark.benchmark_manifest_digest:
            raise PilotError(PilotErrorCode.BENCHMARK_MANIFEST_MISMATCH, "evaluator declaration names a different benchmark manifest")
        for name in ("resource_aggregation", "quality_aggregation"):
            if not isinstance(getattr(self, name), AggregationRef):
                raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"PilotStudyManifest.{name} must be an AggregationRef")
        declared = self.plan.task_class.comparison_policy.quality_aggregation
        if declared is not None and declared != self.quality_aggregation:
            raise PilotError(PilotErrorCode.AGGREGATION_MISMATCH, "quality_aggregation must equal the task class's declared aggregation")
        if self.preregistration_status != PREREGISTRATION_DECLARED_UNVERIFIED:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"preregistration_status is fixed at {PREREGISTRATION_DECLARED_UNVERIFIED} in 4A")
        if self.usage_scope != USAGE_SCOPE_RESEARCH_ONLY:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"usage_scope is fixed at {USAGE_SCOPE_RESEARCH_ONLY}")
        require_nonblank(self.preregistered_by, "PilotStudyManifest.preregistered_by")
        require_tzaware(self.preregistered_at, "PilotStudyManifest.preregistered_at")
        settle_digest(self, "manifest_digest", digest_of(self, exclude=("manifest_digest",)))

    def assignment(self, method: ReasoningMethodRef) -> Optional[PilotMethodAssignment]:
        for m in self.methods:
            if m.method == method:
                return m
        return None

    def methods_with_role(self, role: PilotRole) -> Tuple[ReasoningMethodRef, ...]:
        return tuple(m.method for m in self.methods if role in m.roles)


@dataclass(frozen=True)
class ValidatedManifest:
    manifest_digest: str
    catalog_digest: str
    rule_set_digest: str
    advisory_digest: Optional[str]
    admissible_methods: Tuple[ReasoningMethodRef, ...]
    validator_version: str
    validation_digest: str = ""

    def __post_init__(self) -> None:
        require_digest(self.manifest_digest, "ValidatedManifest.manifest_digest")
        require_digest(self.catalog_digest, "ValidatedManifest.catalog_digest")
        require_digest(self.rule_set_digest, "ValidatedManifest.rule_set_digest")
        if self.advisory_digest is not None:
            require_digest(self.advisory_digest, "ValidatedManifest.advisory_digest")
        if not isinstance(self.admissible_methods, tuple) or not all(isinstance(m, ReasoningMethodRef) for m in self.admissible_methods):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ValidatedManifest.admissible_methods must be a tuple of ReasoningMethodRef")
        require_nonblank(self.validator_version, "ValidatedManifest.validator_version")
        settle_digest(self, "validation_digest", digest_of(self, exclude=("validation_digest",)))


def admissible_methods(catalog: ReasoningMethodCatalog, rule_set: RuleSet) -> Tuple[ReasoningMethodRef, ...]:
    ref = catalog.ref()
    return tuple(ReasoningMethodRef(ref, e.method_id, e.method_version) for e in catalog.entries if rule_set.admissibility.match_entry(e) is not None)


def validate_manifest(manifest: PilotStudyManifest, *, catalog: ReasoningMethodCatalog, rule_set: RuleSet, advisory: Optional[ReasoningMethodAdvisory] = None) -> ValidatedManifest:
    """§3.1 pre-execution validation. Receives the full catalog, rule set and advisory."""
    if not isinstance(manifest, PilotStudyManifest) or not isinstance(catalog, ReasoningMethodCatalog) or not isinstance(rule_set, RuleSet):
        raise TypeError("validate_manifest(manifest, *, catalog, rule_set, advisory=None)")
    if catalog.ref() != manifest.plan.catalog:
        raise PilotError(PilotErrorCode.CATALOG_MISMATCH, "catalog ref differs from plan.catalog")
    if manifest.rule_set is not None and rule_set.ref() != manifest.rule_set:
        raise PilotError(PilotErrorCode.RULE_SET_MISMATCH, "rule set ref differs from manifest.rule_set")
    qualified: FrozenSet[ReasoningMethodRef] = frozenset()
    if manifest.advisory_digest is not None:
        if advisory is None:
            raise PilotError(PilotErrorCode.ADVISORY_REQUIRED, "manifest names an advisory; validate_manifest requires it")
        if not isinstance(advisory, ReasoningMethodAdvisory):
            raise TypeError("advisory must be a ReasoningMethodAdvisory")
        if advisory.advisory_digest != manifest.advisory_digest or advisory.rule_set != manifest.rule_set:
            raise PilotError(PilotErrorCode.ADVISORY_MISMATCH, "advisory digest or rule set differs from the manifest's")
        if advisory.catalog != manifest.plan.catalog:
            raise PilotError(PilotErrorCode.ADVISORY_MISMATCH, "advisory catalog ref differs from plan.catalog")
        if advisory.task_class_digest != manifest.plan.task_class.task_class_digest:
            raise PilotError(PilotErrorCode.ADVISORY_MISMATCH, "advisory task_class_digest differs from the plan's task class")
        qualified = frozenset(q.method for q in advisory.qualifying)
    elif advisory is not None:
        raise PilotError(PilotErrorCode.ADVISORY_MISMATCH, "manifest names no advisory but one was supplied")
    assigned_qualified = frozenset(manifest.methods_with_role(PilotRole.ADVISOR_QUALIFIED))
    if assigned_qualified != qualified or frozenset(manifest.plan.recommended) != qualified:
        raise PilotError(PilotErrorCode.ADVISORY_MISMATCH, "ADVISOR_QUALIFIED methods and plan.recommended must equal the advisory's complete qualifying set")
    admissible = admissible_methods(catalog, rule_set)
    catalog_methods = {ReasoningMethodRef(catalog.ref(), e.method_id, e.method_version) for e in catalog.entries}
    for m in manifest.methods:
        if m.method not in catalog_methods:
            raise PilotError(PilotErrorCode.METHOD_NOT_IN_CATALOG, f"{m.method.method_id}@{m.method.method_version} is not in the catalog")
    if manifest.plan.challengers.kind is SamplingKind.PREREGISTERED:
        assigned = frozenset(m.method for m in manifest.methods)
        if assigned != frozenset(admissible):
            raise PilotError(PilotErrorCode.COMPOSITION_INCOMPLETE, "under exhaustive preregistered composition the assigned methods must equal the admissible catalog set")
        for m in manifest.methods:
            is_challenger = PilotRole.CHALLENGER in m.roles
            if (m.method in qualified) == is_challenger:
                raise PilotError(PilotErrorCode.COMPOSITION_INCOMPLETE, f"{m.method.method_id}: CHALLENGER iff admissible and not qualified")
    return ValidatedManifest(manifest.manifest_digest, catalog.catalog_digest, rule_set.rule_set_digest, manifest.advisory_digest, admissible, __version__)


__all__ = [
    "PILOT_MANIFEST_SCHEMA_VERSION", "PREREGISTRATION_DECLARED_UNVERIFIED", "ATTESTABLE_TELEMETRY_FIELDS", "LLM_CALLS_FIELD",
    "PilotRole", "sorted_roles", "PilotMethodAssignment", "CaptureBoundaryDeclaration", "PilotStudyManifest", "ValidatedManifest",
    "admissible_methods", "validate_manifest",
]
