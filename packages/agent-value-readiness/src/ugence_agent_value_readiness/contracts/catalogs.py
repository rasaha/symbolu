"""Immutable, versioned indicator **catalogs** — the governed vocabulary (M-3R.3).

These answer M-3R.3's second question: *which governed indicator definitions may
describe this assessment?* Three **distinct** catalogs, one per ADR §10 family,
mirroring the three distinct ``*Result`` shapes of M-3R.1. The families are never
merged and their definitions are not interchangeable: an Adoption definition is
not a different value of one enum, it is a different **type**, so mislabelling one
as Intelligence is unrepresentable rather than runtime-detected.

What a catalog says, and what it does not
-----------------------------------------
A catalog entry says exactly one thing::

    "This is a recognized indicator definition."

It never says::

    "This result is true, observed, attributed or verified."

Catalog membership is **not evidence verification**. A supplied indicator result
carries its own ``MetricClaim`` with all five orthogonal evidence axes; admitting
it against a catalog leaves every one of those axes exactly as it was.

Requirements live in policy gates, never here
---------------------------------------------
A definition binds **descriptive/governance vocabulary only**. There is
deliberately no ``required`` flag, no weight, no multiplier, no score, no
threshold value, no benchmark value, no tier, no evidence-status field and no
monetary field. Whether an indicator is mandatory, conditional or advisory is a
property of the governing ``ReadinessPolicy``'s gates (ADR §6, §8, D-6) — a
catalog can neither create a requirement nor satisfy one. In particular, the mere
*existence* of an Intelligence, Capability or Adoption catalog makes **no** family
globally mandatory.

Domain-specific extension goes through the governed ``metric_id``, which is a
free identifier resolved by policy — never by inventing a new dimension enum
member at runtime. The dimension enums are closed, and a value outside them is
rejected.

Canonicalization rule (chosen, and single)
------------------------------------------
**Input order is not digest-significant.** Catalog ``entries`` are canonicalized
to ascending ``indicator_id`` at construction, so two catalogs supplied in
different orders are ``==`` and share a :meth:`canonical_digest`. Identifiers are
whitespace-stripped and compared by exact code points — the package performs **no**
Unicode case folding or NFC/NFKC folding anywhere, and catalogs do not introduce
an inconsistent second rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ugence_uvi_policy_contracts.api import ReadinessTarget

from ._util import canonical_digest, coerce_tuple, require_nonempty
from .enums import (
    AdoptionDimension,
    CapabilityDimension,
    IntelligenceDimension,
    ReadinessIndicatorClass,
)
from .errors import ReadinessContractError

__all__ = [
    "IntelligenceFitnessIndicatorDefinition",
    "CapabilityReadinessIndicatorDefinition",
    "AdoptionReadinessIndicatorDefinition",
    "IntelligenceFitnessCatalog",
    "CapabilityReadinessCatalog",
    "AdoptionReadinessCatalog",
    "ReadinessIndicatorCatalogSet",
]


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ReadinessContractError(f"{name} must be a string (got {type(value).__name__})")
    return value


def _normalized_identity(value: object, name: str) -> str:
    """A non-blank identity, stored whitespace-stripped.

    Normalization is deliberately shallow — strip only. No case folding and no
    Unicode NFC/NFKC folding is applied anywhere in this package, so two
    identifiers that differ by a code point are two different identifiers.
    """

    text = _require_str(value, name)
    require_nonempty(text, name)
    return text.strip()


def _normalized_optional(value: object, name: str) -> str:
    return _require_str(value, name).strip()


def _normalized_targets(value: object, name: str) -> tuple[ReadinessTarget, ...]:
    """Tuple-normalized, duplicate-free, deterministically ordered applicability.

    An **empty** tuple means the definition places no target restriction of its
    own — applicability for the assessment is then decided entirely by the
    governing policy's gates, never by the catalog.
    """

    coerced = coerce_tuple(value, name)
    seen: set[ReadinessTarget] = set()
    for target in coerced:
        if not isinstance(target, ReadinessTarget):
            raise ReadinessContractError(f"{name} entries must be ReadinessTarget")
        if target in seen:
            raise ReadinessContractError(f"{name} duplicates {target.value}")
        seen.add(target)
    # Sorted by value so a reordered caller tuple is the same applicability.
    return tuple(sorted(coerced, key=lambda t: t.value))


def _validate_definition(self, owner: str, dimension_type: type) -> None:
    """Validate + normalize the fields common to every indicator definition."""

    object.__setattr__(
        self, "indicator_id", _normalized_identity(self.indicator_id, f"{owner}.indicator_id")
    )
    if not isinstance(self.dimension, dimension_type):
        raise ReadinessContractError(
            f"{owner}.dimension must be a {dimension_type.__name__} — an indicator definition "
            "cannot borrow another readiness family's dimension"
        )
    object.__setattr__(
        self, "metric_id", _normalized_identity(self.metric_id, f"{owner}.metric_id")
    )
    object.__setattr__(
        self,
        "task_or_outcome_ref",
        _normalized_optional(self.task_or_outcome_ref, f"{owner}.task_or_outcome_ref"),
    )
    object.__setattr__(
        self,
        "applicable_targets",
        _normalized_targets(self.applicable_targets, f"{owner}.applicable_targets"),
    )
    _require_str(self.description, f"{owner}.description")


def _applies_to(self, target: ReadinessTarget) -> bool:
    if not isinstance(target, ReadinessTarget):
        raise ReadinessContractError("applies_to.target must be a ReadinessTarget")
    return not self.applicable_targets or target in self.applicable_targets


# --------------------------------------------------------------------------- #
# Definitions — one per ADR §10 family
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class IntelligenceFitnessIndicatorDefinition:
    """One recognized Intelligence-fitness indicator (ADR §10).

    Carries governance vocabulary only: a stable id, the family-specific
    dimension, the governed ``metric_id`` the result must report against, an
    optional task/outcome reference, optional target applicability, and a human
    description. It carries **no** requirement class, weight, threshold,
    benchmark value, tier or monetary field.
    """

    indicator_id: str
    dimension: IntelligenceDimension
    metric_id: str
    task_or_outcome_ref: str = ""
    applicable_targets: tuple[ReadinessTarget, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        _validate_definition(self, "IntelligenceFitnessIndicatorDefinition", IntelligenceDimension)

    @property
    def indicator_class(self) -> ReadinessIndicatorClass:
        return ReadinessIndicatorClass.INTELLIGENCE

    def applies_to(self, target: ReadinessTarget) -> bool:
        """Whether this definition restricts itself away from ``target``."""

        return _applies_to(self, target)

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class CapabilityReadinessIndicatorDefinition:
    """One recognized Capability-readiness indicator (ADR §10)."""

    indicator_id: str
    dimension: CapabilityDimension
    metric_id: str
    task_or_outcome_ref: str = ""
    applicable_targets: tuple[ReadinessTarget, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        _validate_definition(self, "CapabilityReadinessIndicatorDefinition", CapabilityDimension)

    @property
    def indicator_class(self) -> ReadinessIndicatorClass:
        return ReadinessIndicatorClass.CAPABILITY

    def applies_to(self, target: ReadinessTarget) -> bool:
        return _applies_to(self, target)

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class AdoptionReadinessIndicatorDefinition:
    """One recognized **pre-deployment** Adoption-readiness indicator (ADR §10).

    Pre-deployment prediction vocabulary, never post-deployment
    ``ObservedAdoption`` and never realized value.
    """

    indicator_id: str
    dimension: AdoptionDimension
    metric_id: str
    task_or_outcome_ref: str = ""
    applicable_targets: tuple[ReadinessTarget, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        _validate_definition(self, "AdoptionReadinessIndicatorDefinition", AdoptionDimension)

    @property
    def indicator_class(self) -> ReadinessIndicatorClass:
        return ReadinessIndicatorClass.ADOPTION

    def applies_to(self, target: ReadinessTarget) -> bool:
        return _applies_to(self, target)

    def canonical_digest(self) -> str:
        return canonical_digest(self)


# --------------------------------------------------------------------------- #
# Catalogs — immutable, versioned, one family each
# --------------------------------------------------------------------------- #
def _validate_catalog(self, owner: str, entry_type: type) -> None:
    object.__setattr__(
        self, "catalog_id", _normalized_identity(self.catalog_id, f"{owner}.catalog_id")
    )
    object.__setattr__(
        self,
        "catalog_version",
        _normalized_identity(self.catalog_version, f"{owner}.catalog_version"),
    )
    object.__setattr__(
        self, "tenant_id", _normalized_optional(self.tenant_id, f"{owner}.tenant_id")
    )
    _require_str(self.description, f"{owner}.description")

    # Coerce the caller's sequence into a real tuple first, rejecting scalar
    # substitutes and mappings, so a later mutation of a caller-owned list can
    # never inject, remove or replace an entry after validation.
    coerced = coerce_tuple(self.entries, f"{owner}.entries")
    seen: set[str] = set()
    for entry in coerced:
        if not isinstance(entry, entry_type):
            raise ReadinessContractError(
                f"{owner}.entries entries must be {entry_type.__name__} — Intelligence, "
                "Capability and Adoption definitions are never mixed in one catalog"
            )
        if entry.indicator_id in seen:
            raise ReadinessContractError(
                f"{owner}.entries duplicates indicator_id {entry.indicator_id!r}"
            )
        seen.add(entry.indicator_id)
    # Canonicalized order: input order is not digest-significant.
    object.__setattr__(self, "entries", tuple(sorted(coerced, key=lambda e: e.indicator_id)))


def _lookup(self, indicator_id: object):
    if not isinstance(indicator_id, str):
        return None
    wanted = indicator_id.strip()
    for entry in self.entries:
        if entry.indicator_id == wanted:
            return entry
    return None


@dataclass(frozen=True)
class IntelligenceFitnessCatalog:
    """An immutable, versioned catalog of Intelligence-fitness definitions.

    ``tenant_id`` is optional: an empty value is a **global** catalog, a non-empty
    value scopes the catalog to that tenant. Scope is checked where the catalog is
    bound to an assessment, not here.
    """

    catalog_id: str
    catalog_version: str
    entries: tuple[IntelligenceFitnessIndicatorDefinition, ...] = ()
    tenant_id: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        _validate_catalog(self, "IntelligenceFitnessCatalog", IntelligenceFitnessIndicatorDefinition)

    @property
    def family(self) -> ReadinessIndicatorClass:
        return ReadinessIndicatorClass.INTELLIGENCE

    @property
    def indicator_ids(self) -> tuple[str, ...]:
        return tuple(e.indicator_id for e in self.entries)

    def lookup(self, indicator_id: str) -> Optional[IntelligenceFitnessIndicatorDefinition]:
        """The definition of that id, or ``None`` — never a fabricated default."""

        return _lookup(self, indicator_id)

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class CapabilityReadinessCatalog:
    """An immutable, versioned catalog of Capability-readiness definitions."""

    catalog_id: str
    catalog_version: str
    entries: tuple[CapabilityReadinessIndicatorDefinition, ...] = ()
    tenant_id: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        _validate_catalog(self, "CapabilityReadinessCatalog", CapabilityReadinessIndicatorDefinition)

    @property
    def family(self) -> ReadinessIndicatorClass:
        return ReadinessIndicatorClass.CAPABILITY

    @property
    def indicator_ids(self) -> tuple[str, ...]:
        return tuple(e.indicator_id for e in self.entries)

    def lookup(self, indicator_id: str) -> Optional[CapabilityReadinessIndicatorDefinition]:
        return _lookup(self, indicator_id)

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class AdoptionReadinessCatalog:
    """An immutable, versioned catalog of Adoption-readiness definitions."""

    catalog_id: str
    catalog_version: str
    entries: tuple[AdoptionReadinessIndicatorDefinition, ...] = ()
    tenant_id: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        _validate_catalog(self, "AdoptionReadinessCatalog", AdoptionReadinessIndicatorDefinition)

    @property
    def family(self) -> ReadinessIndicatorClass:
        return ReadinessIndicatorClass.ADOPTION

    @property
    def indicator_ids(self) -> tuple[str, ...]:
        return tuple(e.indicator_id for e in self.entries)

    def lookup(self, indicator_id: str) -> Optional[AdoptionReadinessIndicatorDefinition]:
        return _lookup(self, indicator_id)

    def canonical_digest(self) -> str:
        return canonical_digest(self)


# --------------------------------------------------------------------------- #
# The catalog set bound to one assessment
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ReadinessIndicatorCatalogSet:
    """The catalogs bound to one assessment — **any subset of the three**.

    Every family is optional and an empty set is valid. Supplying an
    Intelligence catalog does **not** make Intelligence indicators required, and
    omitting one does not make that family forbidden: requirements come from the
    governing policy's gates, never from catalog presence (ADR §6, §8, D-6).

    Cross-family identity is kept unambiguous: one ``indicator_id`` may not name
    definitions in two families, and two families may not share a ``catalog_id``.
    Either would make "which definition is this result claiming?" ambiguous, and
    an ambiguous identity is exactly what a replay attack needs.
    """

    intelligence: Optional[IntelligenceFitnessCatalog] = None
    capability: Optional[CapabilityReadinessCatalog] = None
    adoption: Optional[AdoptionReadinessCatalog] = None

    def __post_init__(self) -> None:
        for name, expected in (
            ("intelligence", IntelligenceFitnessCatalog),
            ("capability", CapabilityReadinessCatalog),
            ("adoption", AdoptionReadinessCatalog),
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, expected):
                raise ReadinessContractError(
                    f"ReadinessIndicatorCatalogSet.{name} must be a {expected.__name__} or None"
                )

        seen_catalog_ids: set[str] = set()
        seen_indicator_ids: set[str] = set()
        for catalog in self.catalogs:
            if catalog.catalog_id in seen_catalog_ids:
                raise ReadinessContractError(
                    "ReadinessIndicatorCatalogSet binds catalog_id "
                    f"{catalog.catalog_id!r} in more than one family"
                )
            seen_catalog_ids.add(catalog.catalog_id)
            for indicator_id in catalog.indicator_ids:
                if indicator_id in seen_indicator_ids:
                    raise ReadinessContractError(
                        "ReadinessIndicatorCatalogSet binds indicator_id "
                        f"{indicator_id!r} in more than one readiness family"
                    )
                seen_indicator_ids.add(indicator_id)

    @property
    def catalogs(self) -> tuple:
        """Bound catalogs in fixed family order — never in caller order."""

        return tuple(
            c for c in (self.intelligence, self.capability, self.adoption) if c is not None
        )

    @property
    def families_present(self) -> tuple[ReadinessIndicatorClass, ...]:
        return tuple(c.family for c in self.catalogs)

    @property
    def is_empty(self) -> bool:
        return not self.catalogs

    def catalog_for(self, indicator_class: ReadinessIndicatorClass):
        """The catalog governing that family, or ``None`` when none is bound."""

        if not isinstance(indicator_class, ReadinessIndicatorClass):
            raise ReadinessContractError(
                "ReadinessIndicatorCatalogSet.catalog_for.indicator_class must be a "
                "ReadinessIndicatorClass"
            )
        return {
            ReadinessIndicatorClass.INTELLIGENCE: self.intelligence,
            ReadinessIndicatorClass.CAPABILITY: self.capability,
            ReadinessIndicatorClass.ADOPTION: self.adoption,
        }[indicator_class]

    def canonical_digest(self) -> str:
        return canonical_digest(self)
