"""The closed set of issuable UVI policy families (GV-2C-b).

The authority issues **exactly** the five merged UVI policy families and
introduces none of its own. The mapping below is the closed union: a runtime
type that is not one of these five exact dataclasses cannot be issued, and a
type whose declared ``PolicyFamily`` disagrees with its runtime class cannot be
issued either.

The check is an **exact type identity** test, not ``isinstance``. A subclass of
a supported policy could add fields that the contracts never validate, so it is
refused rather than silently issued under its parent's family.
"""

from __future__ import annotations

from typing import Union

from ugence_uvi_policy_contracts.api import (
    DomainPolicy,
    GeographyPolicy,
    IntendedOutcomePolicy,
    PolicyArtifactMetadata,
    PolicyFamily,
    ReadinessPolicy,
    ValuationPolicy,
)

from .errors import UnsupportedPolicyFamilyError

__all__ = [
    "UVIPolicy",
    "SUPPORTED_POLICY_FAMILIES",
    "policy_family_of",
    "require_supported_policy",
]

#: The closed union of issuable UVI policy artifacts.
UVIPolicy = Union[
    GeographyPolicy,
    DomainPolicy,
    IntendedOutcomePolicy,
    ValuationPolicy,
    ReadinessPolicy,
]

#: Family -> the one exact dataclass that may carry it.
SUPPORTED_POLICY_FAMILIES: dict[PolicyFamily, type] = {
    PolicyFamily.GEOGRAPHY: GeographyPolicy,
    PolicyFamily.DOMAIN: DomainPolicy,
    PolicyFamily.INTENDED_OUTCOME: IntendedOutcomePolicy,
    PolicyFamily.VALUATION: ValuationPolicy,
    PolicyFamily.READINESS: ReadinessPolicy,
}

_FAMILY_BY_TYPE: dict[type, PolicyFamily] = {
    cls: family for family, cls in SUPPORTED_POLICY_FAMILIES.items()
}


def policy_family_of(policy: object) -> PolicyFamily:
    """Return the family of a supported policy, refusing anything else."""

    family = _FAMILY_BY_TYPE.get(type(policy))
    if family is None:
        raise UnsupportedPolicyFamilyError(
            f"{type(policy).__name__!r} is not one of the five supported UVI policy "
            f"families ({', '.join(sorted(c.__name__ for c in _FAMILY_BY_TYPE))})"
        )
    return family


def require_supported_policy(policy: object) -> PolicyFamily:
    """Validate a policy artifact is issuable and return its family.

    Proves, structurally, that:

    * the runtime type is one of the five exact supported dataclasses;
    * it carries a real :class:`PolicyArtifactMetadata` envelope;
    * the declared ``metadata.policy_family`` matches that runtime type.

    The contracts already enforce the third rule at construction; it is
    re-checked here because the authority must never rely on a caller-supplied
    object having been constructed through the contract's own validation.
    """

    family = policy_family_of(policy)

    metadata = getattr(policy, "metadata", None)
    if not isinstance(metadata, PolicyArtifactMetadata):
        raise UnsupportedPolicyFamilyError(
            f"{type(policy).__name__} must carry a PolicyArtifactMetadata envelope"
        )
    if metadata.policy_family is not family:
        raise UnsupportedPolicyFamilyError(
            f"{type(policy).__name__} declares family "
            f"{metadata.policy_family.value} but its runtime type is {family.value}"
        )
    return family
