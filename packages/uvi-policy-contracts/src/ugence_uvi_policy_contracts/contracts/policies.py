"""The five first-class UVI policy shapes (ADR §15, D-2, D-13, §20).

``GeographyPolicy``, ``DomainPolicy``, ``IntendedOutcomePolicy``,
``ValuationPolicy``, and ``ReadinessPolicy`` are **schema + IR only** — immutable
contract shapes governed by the Policy Authority. They mint no authority,
implement no evaluator or calculator, and (critically) express **no
caller-controlled numeric ROI/value multiplier**: geography and domain express
currency, jurisdiction, benchmarks (by reference), and thresholds, never a
scalar knob a caller can turn to inflate a result (ADR §23 invariant 1, D-13).

Each policy embeds a :class:`PolicyArtifactMetadata` envelope whose
``policy_family`` must match the policy's family.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ugence_governance_contracts.api import (
    AttributionStatus,
    BenchmarkReference,
    SourceBasis,
    VerificationStatus,
)

from ._util import canonical_digest, coerce_tuple, normalize_tokens, require_nonempty
from .enums import (
    HeadlineClassificationPolicy,
    MissingComponentBehavior,
    PolicyFamily,
    ReadinessTarget,
    RequirementClass,
    ValueComponent,
)
from .errors import PolicyContractError
from .metadata import PolicyArtifactMetadata, PolicyReference
from .thresholds import GovernedThreshold, PolicyGate

__all__ = [
    "ComponentEvidenceRequirement",
    "GeographyPolicy",
    "DomainPolicy",
    "IntendedOutcomePolicy",
    "ValuationPolicy",
    "ReadinessPolicy",
]


# --------------------------------------------------------------------------- #
# Shared structural helpers
# --------------------------------------------------------------------------- #
def _set(obj, name: str, value) -> None:
    """Store a normalized value on a frozen dataclass during ``__post_init__``."""

    object.__setattr__(obj, name, value)


def _require_family(meta: PolicyArtifactMetadata, family: PolicyFamily, owner: str) -> None:
    if not isinstance(meta, PolicyArtifactMetadata):
        raise PolicyContractError(f"{owner}.metadata must be a PolicyArtifactMetadata")
    if meta.policy_family is not family:
        raise PolicyContractError(
            f"{owner}.metadata.policy_family must be {family.value} (got {meta.policy_family.value})"
        )


def _require_currency(code: str, name: str) -> None:
    require_nonempty(code, name)
    if not (code.isupper() and code.isalpha() and len(code) == 3):
        raise PolicyContractError(f"{name} must be a 3-letter uppercase currency code (e.g. 'USD')")


# Each of these coerces the caller's sequence into an immutable tuple (rejecting
# str/bytes/mapping/non-iterable), validates every element's type and the
# collection-level uniqueness rule, and returns the normalized tuple for the
# constructor to store back via ``object.__setattr__`` — so later mutation of a
# caller-owned list can never reach the frozen contract.
def _norm_thresholds(values, owner: str) -> tuple[GovernedThreshold, ...]:
    coerced = coerce_tuple(values, owner)
    ids = []
    for t in coerced:
        if not isinstance(t, GovernedThreshold):
            raise PolicyContractError(f"{owner} entries must be GovernedThreshold")
        ids.append(t.threshold_id)
    normalize_tokens(tuple(ids), f"{owner} threshold_id")
    return coerced


def _norm_gates(values, owner: str) -> tuple[PolicyGate, ...]:
    coerced = coerce_tuple(values, owner)
    ids = []
    for g in coerced:
        if not isinstance(g, PolicyGate):
            raise PolicyContractError(f"{owner} entries must be PolicyGate")
        ids.append(g.gate_id)
    normalize_tokens(tuple(ids), f"{owner} gate_id")
    return coerced


def _norm_benchmarks(values, owner: str) -> tuple[BenchmarkReference, ...]:
    coerced = coerce_tuple(values, owner)
    keys = []
    for r in coerced:
        if not isinstance(r, BenchmarkReference):
            raise PolicyContractError(f"{owner} entries must be BenchmarkReference")
        keys.append(f"{r.benchmark_id}@{r.version}")
    normalize_tokens(tuple(keys), owner)
    return coerced


def _norm_ref_family(values, family: PolicyFamily, owner: str) -> tuple[PolicyReference, ...]:
    coerced = coerce_tuple(values, owner)
    keys = []
    for r in coerced:
        if not isinstance(r, PolicyReference):
            raise PolicyContractError(f"{owner} entries must be PolicyReference")
        if r.policy_family is not family:
            raise PolicyContractError(
                f"{owner} entries must reference a {family.value} policy (got {r.policy_family.value})"
            )
        keys.append(f"{r.policy_id}@{r.version}")
    normalize_tokens(tuple(keys), owner)
    return coerced


# --------------------------------------------------------------------------- #
# GeographyPolicy (ADR §15 col 1) — NO ROI multiplier field exists.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GeographyPolicy:
    """Jurisdiction, currency, localization, and regional benchmarks/thresholds.

    Anti-gaming: this shape has **no field capable of expressing a
    caller-controlled ROI or value multiplier**. The only monetary levers are
    ``reporting_currency`` / ``functional_currency`` (declared currency, not a
    scaling factor) and ``cost_benchmark_refs`` (references into
    Policy-Authority-governed benchmark data). Regional performance bars are
    :class:`GovernedThreshold`s, never scalars a caller can inflate.
    """

    metadata: PolicyArtifactMetadata
    jurisdiction: str
    reporting_currency: str
    functional_currency: str
    applicable_regulations: tuple[str, ...] = ()
    language_requirements: tuple[str, ...] = ()
    residency_requirements: tuple[str, ...] = ()
    cost_benchmark_refs: tuple[BenchmarkReference, ...] = ()
    regional_thresholds: tuple[GovernedThreshold, ...] = ()
    valuation_policy_refs: tuple[PolicyReference, ...] = ()

    def __post_init__(self) -> None:
        _require_family(self.metadata, PolicyFamily.GEOGRAPHY, "GeographyPolicy")
        require_nonempty(self.jurisdiction, "GeographyPolicy.jurisdiction")
        _require_currency(self.reporting_currency, "GeographyPolicy.reporting_currency")
        _require_currency(self.functional_currency, "GeographyPolicy.functional_currency")
        _set(self, "applicable_regulations", normalize_tokens(self.applicable_regulations, "GeographyPolicy.applicable_regulations"))
        _set(self, "language_requirements", normalize_tokens(self.language_requirements, "GeographyPolicy.language_requirements"))
        _set(self, "residency_requirements", normalize_tokens(self.residency_requirements, "GeographyPolicy.residency_requirements"))
        _set(self, "cost_benchmark_refs", _norm_benchmarks(self.cost_benchmark_refs, "GeographyPolicy.cost_benchmark_refs"))
        _set(self, "regional_thresholds", _norm_thresholds(self.regional_thresholds, "GeographyPolicy.regional_thresholds"))
        _set(self, "valuation_policy_refs", _norm_ref_family(self.valuation_policy_refs, PolicyFamily.VALUATION, "GeographyPolicy.valuation_policy_refs"))

    @property
    def reference(self) -> PolicyReference:
        return self.metadata.to_reference()

    def canonical_digest(self) -> str:
        return canonical_digest(self)


# --------------------------------------------------------------------------- #
# DomainPolicy (ADR §15 col 2)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DomainPolicy:
    """Governed outcome units, taxonomies, domain benchmarks, and gates."""

    metadata: PolicyArtifactMetadata
    governed_outcome_unit: str
    task_taxonomy: tuple[str, ...] = ()
    benefit_taxonomy: tuple[str, ...] = ()
    loss_taxonomy: tuple[str, ...] = ()
    permitted_valuation_methods: tuple[str, ...] = ()
    domain_benchmark_refs: tuple[BenchmarkReference, ...] = ()
    gates: tuple[PolicyGate, ...] = ()
    criticality_class: str = ""

    def __post_init__(self) -> None:
        _require_family(self.metadata, PolicyFamily.DOMAIN, "DomainPolicy")
        require_nonempty(self.governed_outcome_unit, "DomainPolicy.governed_outcome_unit")
        _set(self, "task_taxonomy", normalize_tokens(self.task_taxonomy, "DomainPolicy.task_taxonomy"))
        _set(self, "benefit_taxonomy", normalize_tokens(self.benefit_taxonomy, "DomainPolicy.benefit_taxonomy"))
        _set(self, "loss_taxonomy", normalize_tokens(self.loss_taxonomy, "DomainPolicy.loss_taxonomy"))
        _set(self, "permitted_valuation_methods", normalize_tokens(self.permitted_valuation_methods, "DomainPolicy.permitted_valuation_methods"))
        _set(self, "domain_benchmark_refs", _norm_benchmarks(self.domain_benchmark_refs, "DomainPolicy.domain_benchmark_refs"))
        _set(self, "gates", _norm_gates(self.gates, "DomainPolicy.gates"))

    @property
    def reference(self) -> PolicyReference:
        return self.metadata.to_reference()

    def canonical_digest(self) -> str:
        return canonical_digest(self)


# --------------------------------------------------------------------------- #
# IntendedOutcomePolicy (ADR §15 col 3)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class IntendedOutcomePolicy:
    """Target outcome, success criteria, counterfactual, and acceptance bars.

    Realization lag is carried as a qualitative/period *descriptor* — never a
    money value or a multiplier.
    """

    metadata: PolicyArtifactMetadata
    target_outcome: str
    task_definition: str
    success_criteria: tuple[str, ...] = ()
    value_function_ref: str = ""
    counterfactual_specification: str = ""
    realization_lag: str = ""
    attribution_method: str = ""
    normalization_basis: str = ""
    required_effect_evidence: tuple[str, ...] = ()
    acceptance_thresholds: tuple[GovernedThreshold, ...] = ()
    valuation_policy_refs: tuple[PolicyReference, ...] = ()

    def __post_init__(self) -> None:
        _require_family(self.metadata, PolicyFamily.INTENDED_OUTCOME, "IntendedOutcomePolicy")
        require_nonempty(self.target_outcome, "IntendedOutcomePolicy.target_outcome")
        require_nonempty(self.task_definition, "IntendedOutcomePolicy.task_definition")
        _set(self, "success_criteria", normalize_tokens(self.success_criteria, "IntendedOutcomePolicy.success_criteria"))
        _set(self, "required_effect_evidence", normalize_tokens(self.required_effect_evidence, "IntendedOutcomePolicy.required_effect_evidence"))
        _set(self, "acceptance_thresholds", _norm_thresholds(self.acceptance_thresholds, "IntendedOutcomePolicy.acceptance_thresholds"))
        _set(self, "valuation_policy_refs", _norm_ref_family(self.valuation_policy_refs, PolicyFamily.VALUATION, "IntendedOutcomePolicy.valuation_policy_refs"))

    @property
    def reference(self) -> PolicyReference:
        return self.metadata.to_reference()

    def canonical_digest(self) -> str:
        return canonical_digest(self)


# --------------------------------------------------------------------------- #
# ValuationPolicy (D-11, D-12) — eligibility & headline rule, not calculation.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ComponentEvidenceRequirement:
    """A per-component evidential requirement declared by a ValuationPolicy.

    States *which* value component is required and to what evidential standard,
    reusing the neutral GV-2E-a axes (``SourceBasis`` / ``AttributionStatus`` /
    ``VerificationStatus``). This is a **policy requirement**, not a metric
    claim; it carries no measured value.
    """

    component: ValueComponent
    requirement_class: RequirementClass = RequirementClass.MANDATORY
    required_source_basis: Optional[SourceBasis] = None
    required_attribution: Optional[AttributionStatus] = None
    required_verification: Optional[VerificationStatus] = None

    def __post_init__(self) -> None:
        if not isinstance(self.component, ValueComponent):
            raise PolicyContractError("ComponentEvidenceRequirement.component must be a ValueComponent")
        if not isinstance(self.requirement_class, RequirementClass):
            raise PolicyContractError(
                "ComponentEvidenceRequirement.requirement_class must be a RequirementClass"
            )
        if self.required_source_basis is not None and not isinstance(self.required_source_basis, SourceBasis):
            raise PolicyContractError("ComponentEvidenceRequirement.required_source_basis must be a SourceBasis")
        if self.required_attribution is not None and not isinstance(self.required_attribution, AttributionStatus):
            raise PolicyContractError(
                "ComponentEvidenceRequirement.required_attribution must be an AttributionStatus"
            )
        if self.required_verification is not None and not isinstance(self.required_verification, VerificationStatus):
            raise PolicyContractError(
                "ComponentEvidenceRequirement.required_verification must be a VerificationStatus"
            )

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class ValuationPolicy:
    """Eligibility, permitted methods, required components, and headline rule.

    Owns the *policy* that governs financial valuation (D-11): which methods are
    permitted, which components are required and to what evidential standard, the
    conservative headline-classification rule (D-12), and the missing-component
    behavior. The financial **calculation** and the ``ValuationEvidenceManifest``
    themselves belong to ``governed-value`` and are not implemented here.
    """

    metadata: PolicyArtifactMetadata
    permitted_valuation_methods: tuple[str, ...] = ()
    required_components: tuple[ComponentEvidenceRequirement, ...] = ()
    headline_classification: HeadlineClassificationPolicy = (
        HeadlineClassificationPolicy.WEAKEST_REQUIRED_COMPONENT
    )
    missing_component_behavior: MissingComponentBehavior = MissingComponentBehavior.FAIL_CLOSED
    acceptance_thresholds: tuple[GovernedThreshold, ...] = ()

    def __post_init__(self) -> None:
        _require_family(self.metadata, PolicyFamily.VALUATION, "ValuationPolicy")
        _set(self, "permitted_valuation_methods", normalize_tokens(self.permitted_valuation_methods, "ValuationPolicy.permitted_valuation_methods"))
        if not isinstance(self.headline_classification, HeadlineClassificationPolicy):
            raise PolicyContractError(
                "ValuationPolicy.headline_classification must be a HeadlineClassificationPolicy"
            )
        if not isinstance(self.missing_component_behavior, MissingComponentBehavior):
            raise PolicyContractError(
                "ValuationPolicy.missing_component_behavior must be a MissingComponentBehavior"
            )
        required_components = coerce_tuple(self.required_components, "ValuationPolicy.required_components")
        seen: set[ValueComponent] = set()
        for req in required_components:
            if not isinstance(req, ComponentEvidenceRequirement):
                raise PolicyContractError(
                    "ValuationPolicy.required_components entries must be ComponentEvidenceRequirement"
                )
            if req.component in seen:
                raise PolicyContractError(
                    f"ValuationPolicy.required_components duplicates component {req.component.value}"
                )
            seen.add(req.component)
        _set(self, "required_components", required_components)
        _set(self, "acceptance_thresholds", _norm_thresholds(self.acceptance_thresholds, "ValuationPolicy.acceptance_thresholds"))

    @property
    def reference(self) -> PolicyReference:
        return self.metadata.to_reference()

    def canonical_digest(self) -> str:
        return canonical_digest(self)


# --------------------------------------------------------------------------- #
# ReadinessPolicy (D-4, D-5, D-6, §10) — schema only, no evaluator.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ReadinessPolicy:
    """Non-financial readiness gates and target applicability (schema only).

    Encodes the anti-gaming locks structurally: the composite is advisory and
    can never change a tier (``composite_is_advisory`` must be ``True``, D-5),
    and mandatory gates are non-waivable (enforced by :class:`PolicyGate`, D-6).
    No state machine or evaluator is implemented here.
    """

    metadata: PolicyArtifactMetadata
    gates: tuple[PolicyGate, ...] = ()
    readiness_targets: tuple[ReadinessTarget, ...] = (
        ReadinessTarget.PILOT,
        ReadinessTarget.PRODUCTION,
    )
    composite_is_advisory: bool = True

    def __post_init__(self) -> None:
        _require_family(self.metadata, PolicyFamily.READINESS, "ReadinessPolicy")
        _set(self, "gates", _norm_gates(self.gates, "ReadinessPolicy.gates"))
        readiness_targets = coerce_tuple(self.readiness_targets, "ReadinessPolicy.readiness_targets")
        if not readiness_targets:
            raise PolicyContractError("ReadinessPolicy.readiness_targets must name at least one target")
        seen: set[ReadinessTarget] = set()
        for t in readiness_targets:
            if not isinstance(t, ReadinessTarget):
                raise PolicyContractError("ReadinessPolicy.readiness_targets entries must be ReadinessTarget")
            if t in seen:
                raise PolicyContractError(f"ReadinessPolicy.readiness_targets duplicates {t.value}")
            seen.add(t)
        _set(self, "readiness_targets", readiness_targets)
        if self.composite_is_advisory is not True:
            raise PolicyContractError(
                "ReadinessPolicy.composite_is_advisory must be True — the composite is advisory "
                "only and can never change a readiness tier (D-5)"
            )

    @property
    def reference(self) -> PolicyReference:
        return self.metadata.to_reference()

    def canonical_digest(self) -> str:
        return canonical_digest(self)
