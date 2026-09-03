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
from .calibration import CalibrationProvenance, PilotRunRole, require_canonical_decimal
from .evaluator import QualityEvaluatorDeclaration

PILOT_MANIFEST_SCHEMA_VERSION = "workflow_fit_pilot.manifest.v1"
PILOT_MANIFEST_SCHEMA_VERSION_V1 = PILOT_MANIFEST_SCHEMA_VERSION
PILOT_MANIFEST_SCHEMA_VERSION_V2 = "workflow_fit_pilot.manifest.v2"
SUPPORTED_MANIFEST_SCHEMA_VERSIONS = (PILOT_MANIFEST_SCHEMA_VERSION_V1, PILOT_MANIFEST_SCHEMA_VERSION_V2)
PREREGISTRATION_DECLARED_UNVERIFIED = "DECLARED_UNVERIFIED"


class PreregistrationStatus(str, Enum):
    DECLARED_UNVERIFIED = "DECLARED_UNVERIFIED"   # the only value in 4A
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
    preregistration_status: PreregistrationStatus
    usage_scope: str
    preregistered_by: str
    preregistered_at: datetime
    manifest_digest: str = ""
    # v2 only. Appended after manifest_digest so every existing v1 call site keeps its
    # positional shape, and excluded from the v1 digest payload so historical
    # mechanism-validation artifacts keep the digests they were issued with.
    run_role: Optional[PilotRunRole] = None
    calibration_provenance: Optional[CalibrationProvenance] = None

    def __post_init__(self) -> None:
        if self.schema_version not in SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
            raise PilotError(PilotErrorCode.SCHEMA_VERSION_UNSUPPORTED, f"PilotStudyManifest.schema_version must be one of {SUPPORTED_MANIFEST_SCHEMA_VERSIONS}")
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
        if self.preregistration_status is not PreregistrationStatus.DECLARED_UNVERIFIED:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"preregistration_status is fixed at {PREREGISTRATION_DECLARED_UNVERIFIED} in 4A")
        if self.usage_scope != USAGE_SCOPE_RESEARCH_ONLY:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"usage_scope is fixed at {USAGE_SCOPE_RESEARCH_ONLY}")
        require_nonblank(self.preregistered_by, "PilotStudyManifest.preregistered_by")
        require_tzaware(self.preregistered_at, "PilotStudyManifest.preregistered_at")
        self._validate_run_role()
        excluded = ("manifest_digest",) if self.is_v2 else ("manifest_digest", "run_role", "calibration_provenance")
        settle_digest(self, "manifest_digest", digest_of(self, exclude=excluded))

    @property
    def is_v2(self) -> bool:
        return self.schema_version == PILOT_MANIFEST_SCHEMA_VERSION_V2

    def _validate_run_role(self) -> None:
        """v1 carries no role and never acquires one; v2 requires one and is validated
        against it. A missing role is never read as CONFIRMATORY."""
        if not self.is_v2:
            if self.run_role is not None or self.calibration_provenance is not None:
                raise PilotError(PilotErrorCode.RUN_ROLE_INVALID, "a v1 manifest carries no run role and no calibration provenance")
            return
        if not isinstance(self.run_role, PilotRunRole):
            raise PilotError(PilotErrorCode.RUN_ROLE_INVALID, "a v2 manifest requires an explicit PilotRunRole; none is inferred")
        # A31: the pilot package never assigns a threshold value; it only reads the
        # governed reference the task class already carries.
        threshold_ref = self.plan.task_class.comparison_policy.sufficiency.threshold
        has_literal = bool(threshold_ref.literal_value and threshold_ref.literal_value.strip())
        if self.run_role is PilotRunRole.CALIBRATION:
            self._validate_calibration_shape(threshold_ref, has_literal)
        else:
            self._validate_confirmatory_shape(threshold_ref, has_literal)

    def _validate_calibration_shape(self, threshold_ref, has_literal: bool) -> None:
        if len(self.methods) != 1:
            raise PilotError(PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT, "a CALIBRATION manifest assigns exactly one method")
        assignment = self.methods[0]
        # Restated for locality. The general rule above already forces the single
        # assignment to be plan.baseline, so this branch cannot fire; it is kept because
        # the baseline-only identity is the load-bearing calibration invariant and a
        # future change to the general rule must not silently widen calibration.
        if assignment.method != self.plan.baseline:
            raise PilotError(PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT, "the CALIBRATION method must be plan.baseline")
        # F1, ratified in revision 16: the baseline-only set was fixed before execution,
        # so PREREGISTERED is the truthful sampling kind. Risk-based and randomized
        # selection would misdescribe a composition that was never sampled.
        if self.plan.challengers.kind is not SamplingKind.PREREGISTERED:
            raise PilotError(
                PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT,
                "a CALIBRATION plan declares SamplingKind.PREREGISTERED; its baseline-only composition is not sampled",
            )
        if tuple(assignment.roles) != (PilotRole.GOVERNED_BASELINE,):
            raise PilotError(PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT, "the CALIBRATION assignment carries exactly the GOVERNED_BASELINE role")
        if self.plan.recommended:
            raise PilotError(PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT, "a CALIBRATION manifest recommends no method")
        if threshold_ref.benchmark_ref is None or has_literal:
            raise PilotError(PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT, "a CALIBRATION threshold carries a benchmark_ref and no literal_value")
        if self.calibration_provenance is not None:
            raise PilotError(PilotErrorCode.CALIBRATION_PROVENANCE_INVALID, "a CALIBRATION manifest carries no calibration provenance")

    def _validate_confirmatory_shape(self, threshold_ref, has_literal: bool) -> None:
        if not has_literal or threshold_ref.benchmark_ref is not None:
            raise PilotError(PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT, "a CONFIRMATORY threshold carries a literal_value and no benchmark_ref")
        # F2, ratified in revision 16. The bar a confirmatory run is judged against must
        # carry the same canonical spelling the calibration statistic and the provenance
        # literal carry, so slice 3 can reconcile all three by code-point equality. This
        # reads the governed literal the task class already holds; it assigns nothing and
        # normalises nothing (A31).
        require_canonical_decimal(threshold_ref.literal_value, "a CONFIRMATORY threshold literal_value")
        if not isinstance(self.calibration_provenance, CalibrationProvenance):
            raise PilotError(PilotErrorCode.CALIBRATION_PROVENANCE_INVALID, "a CONFIRMATORY manifest requires complete CalibrationProvenance")

    def require_phase_4c_eligible(self) -> "PilotStudyManifest":
        """Historical v1 artifacts stay verifiable but are never eligible for a genuine
        Phase 4C run: they carry no committed role, and inferring one would be exactly
        the silent upgrade revision 14 forbids.

        **F3, slice-3 obligation (revision 16).** Nothing in this package calls this
        method: it makes ineligibility *expressible*, not *enforced*. Until slice 3 calls
        it from the run entry point, a v1 manifest is refused only by callers that ask."""
        if not self.is_v2:
            raise PilotError(
                PilotErrorCode.RUN_ROLE_INVALID,
                f"{self.schema_version} is historical mechanism validation and is not eligible for a Phase 4C run",
            )
        return self

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
    """§3.1 pre-execution validation. Receives the full catalog, rule set and advisory.

    Run-role-aware since revision 16: a v2 CALIBRATION manifest preregisters the
    baseline-only set, a CONFIRMATORY manifest preregisters the exhaustive admissible
    set, and a v1 manifest keeps exactly the behaviour it has always had."""
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
        if manifest.is_v2 and manifest.run_role is PilotRunRole.CALIBRATION:
            # F1, ratified in revision 16. Calibration and confirmation both preregister
            # their composition; they preregister *different* sets. A calibration run
            # measures one statistic from the governed baseline alone, so its complete
            # preregistered set is exactly {plan.baseline} — applying the confirmatory
            # "every admissible method is assigned" rule to it would refuse the very shape
            # the manifest contract requires. The confirmatory rule below is unchanged.
            if assigned != frozenset({manifest.plan.baseline}):
                raise PilotError(PilotErrorCode.COMPOSITION_INCOMPLETE, "under CALIBRATION the preregistered assigned set is exactly {plan.baseline}")
            if PilotRole.CHALLENGER in manifest.methods[0].roles:
                raise PilotError(PilotErrorCode.COMPOSITION_INCOMPLETE, "a CALIBRATION run assigns no challenger")
        else:
            if assigned != frozenset(admissible):
                raise PilotError(PilotErrorCode.COMPOSITION_INCOMPLETE, "under exhaustive preregistered composition the assigned methods must equal the admissible catalog set")
            for m in manifest.methods:
                is_challenger = PilotRole.CHALLENGER in m.roles
                if (m.method in qualified) == is_challenger:
                    raise PilotError(PilotErrorCode.COMPOSITION_INCOMPLETE, f"{m.method.method_id}: CHALLENGER iff admissible and not qualified")
    return ValidatedManifest(manifest.manifest_digest, catalog.catalog_digest, rule_set.rule_set_digest, manifest.advisory_digest, admissible, __version__)


__all__ = [
    "PILOT_MANIFEST_SCHEMA_VERSION", "PILOT_MANIFEST_SCHEMA_VERSION_V1", "PILOT_MANIFEST_SCHEMA_VERSION_V2",
    "SUPPORTED_MANIFEST_SCHEMA_VERSIONS",
    "PREREGISTRATION_DECLARED_UNVERIFIED", "ATTESTABLE_TELEMETRY_FIELDS", "LLM_CALLS_FIELD",
    "PreregistrationStatus", "PilotRole", "sorted_roles", "PilotMethodAssignment", "CaptureBoundaryDeclaration", "PilotStudyManifest", "ValidatedManifest",
    "admissible_methods", "validate_manifest",
]
