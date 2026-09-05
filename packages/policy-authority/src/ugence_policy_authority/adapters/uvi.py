"""The UVI policy-family adapter — the authority's **first** adapter.

UVI policy schemas are a *consumer* of the shared authority's boundary, not the
owner of it. This module is the only place in the distribution that imports or
reasons about a UVI policy type; the generic core knows nothing about
geography, domain, intended outcome, valuation, or readiness, and an automated
AST test enforces that.

It recognizes exactly the five merged UVI policy families and introduces none
of its own. Recognition is an **exact runtime type** test, not ``isinstance``:
a subclass could add fields the contracts never validate, so it is refused
rather than silently issued under its parent's family.

The canonical projection
------------------------
The merged UVI contracts document ``PolicyArtifactMetadata.content_digest`` as
"the authority-attested digest of the policy content" and deliberately leave
the computation to the Policy Authority — nothing in ``uvi-policy-contracts``
computes it. This adapter supplies that projection:

* the whole artifact is projected canonically, then **exactly one declared
  path**, ``metadata.content_digest``, is **removed** from the mapping;
* removal is by path, not by name: a nested ``content_digest`` on a
  ``BenchmarkReference`` or a referenced ``PolicyReference`` is **retained**
  and remains bound;
* the field is removed, never blanked — no sentinel value participates, no
  fixed-point iteration is needed, and setting the declaration to the computed
  result cannot change the result;
* a policy artifact has **no signature field**, so the projection is
  structurally incapable of depending on a signature.

The core frames this projection with the canonicalization version, the domain
tag, this adapter's id, and the exact policy type before hashing.
"""

from __future__ import annotations

from typing import Any, Optional

from ugence_uvi_policy_contracts.api import (
    DomainPolicy,
    GeographyPolicy,
    IntendedOutcomePolicy,
    PolicyArtifactMetadata,
    PolicyFamily,
    PolicyLifecycleState,
    PolicyReference,
    PolicyScope,
    ReadinessPolicy,
    ValuationPolicy,
)

from ..core.adapters import PolicyArtifactDescriptor, PolicyCoordinate
from ..core.canonical import to_canonical_obj
from ..core.codec import decode_dataclass
from ..core.errors import PolicyAuthorityRequestError, UnsupportedPolicyArtifactError

__all__ = [
    "UVI_ADAPTER_ID",
    "SUPPORTED_UVI_POLICY_FAMILIES",
    "UviPolicyFamilyAdapter",
    "UviPolicyArtifactCodec",
    "uvi_coordinate",
]

#: Stable adapter identity, bound into every body digest this adapter frames.
UVI_ADAPTER_ID = "ugence.uvi.policy-family/v1"

#: Family -> the one exact dataclass that may carry it. Exactly the five merged
#: UVI families; this adapter introduces none of its own.
SUPPORTED_UVI_POLICY_FAMILIES: dict[PolicyFamily, type] = {
    PolicyFamily.GEOGRAPHY: GeographyPolicy,
    PolicyFamily.DOMAIN: DomainPolicy,
    PolicyFamily.INTENDED_OUTCOME: IntendedOutcomePolicy,
    PolicyFamily.VALUATION: ValuationPolicy,
    PolicyFamily.READINESS: ReadinessPolicy,
}

_FAMILY_BY_TYPE: dict[type, PolicyFamily] = {
    cls: family for family, cls in SUPPORTED_UVI_POLICY_FAMILIES.items()
}


def uvi_coordinate(reference: PolicyReference) -> PolicyCoordinate:
    """Map a UVI :class:`PolicyReference` onto a family-neutral coordinate."""

    if not isinstance(reference, PolicyReference):
        raise PolicyAuthorityRequestError("uvi_coordinate requires a PolicyReference")
    return PolicyCoordinate(
        policy_family=reference.policy_family.value,
        policy_id=reference.policy_id,
        version=reference.version,
        content_digest=reference.content_digest,
        scope=reference.scope.value,
        tenant_id=reference.tenant_id,
    )


class UviPolicyFamilyAdapter:
    """Registers the five merged UVI policy families with the shared authority."""

    @property
    def adapter_id(self) -> str:
        return UVI_ADAPTER_ID

    # ------------------------------------------------------------------
    # Recognition
    # ------------------------------------------------------------------
    def recognizes(self, artifact: object) -> bool:
        """Exact runtime type match — a subclass is deliberately not recognized."""

        return type(artifact) in _FAMILY_BY_TYPE

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        if not isinstance(reference, PolicyReference):
            return None
        return uvi_coordinate(reference)

    # ------------------------------------------------------------------
    # Description
    # ------------------------------------------------------------------
    def describe(self, artifact: object) -> PolicyArtifactDescriptor:
        family = _FAMILY_BY_TYPE.get(type(artifact))
        if family is None:
            raise UnsupportedPolicyArtifactError(
                f"{type(artifact).__name__!r} is not one of the five supported UVI policy "
                f"families ({', '.join(sorted(c.__name__ for c in _FAMILY_BY_TYPE))})"
            )

        metadata = getattr(artifact, "metadata", None)
        if not isinstance(metadata, PolicyArtifactMetadata):
            raise UnsupportedPolicyArtifactError(
                f"{type(artifact).__name__} must carry a PolicyArtifactMetadata envelope"
            )
        # The contracts enforce this at construction; the authority re-checks it
        # because it must never rely on an object having been built that way.
        if metadata.policy_family is not family:
            raise UnsupportedPolicyArtifactError(
                f"{type(artifact).__name__} declares family {metadata.policy_family.value} "
                f"but its runtime type is {family.value}"
            )
        if not isinstance(metadata.scope, PolicyScope):
            raise UnsupportedPolicyArtifactError("metadata.scope must be a PolicyScope")
        if not isinstance(metadata.lifecycle_state, PolicyLifecycleState):
            raise UnsupportedPolicyArtifactError(
                "metadata.lifecycle_state must be a PolicyLifecycleState"
            )

        projection = self._canonical_projection(artifact)

        return PolicyArtifactDescriptor(
            adapter_id=UVI_ADAPTER_ID,
            policy_type=type(artifact).__name__,
            coordinate=uvi_coordinate(metadata.to_reference()),
            declared_content_digest=metadata.content_digest,
            canonical_projection=projection,
            lifecycle_label=metadata.lifecycle_state.value,
            lifecycle_is_active=(
                metadata.lifecycle_state is PolicyLifecycleState.APPROVED_ACTIVE
            ),
            supersedes_ref=metadata.supersedes_ref,
            effective_from=metadata.effective_from,
            effective_to=metadata.effective_to,
        )

    # ------------------------------------------------------------------
    # Canonical projection
    # ------------------------------------------------------------------
    @staticmethod
    def _canonical_projection(artifact: Any) -> dict:
        """Project the artifact, removing exactly ``metadata.content_digest``.

        Canonicalization itself (NFC enforcement, naive-datetime rejection,
        ``float`` rejection, UTC normalization) happens inside
        :func:`to_canonical_obj`, so a malformed artifact is refused here rather
        than silently digested.
        """

        body = to_canonical_obj(artifact, path="$")
        metadata = body.get("metadata") if isinstance(body, dict) else None
        if not isinstance(metadata, dict) or "content_digest" not in metadata:
            raise UnsupportedPolicyArtifactError(
                "a UVI policy must carry a PolicyArtifactMetadata envelope with a "
                "content_digest declaration"
            )
        body = dict(body)
        # Exactly this one declared path. Nested content_digest fields elsewhere
        # in the artifact (benchmark references, referenced policy references)
        # are untouched and remain bound.
        body["metadata"] = {k: v for k, v in metadata.items() if k != "content_digest"}
        return body


class UviPolicyArtifactCodec:
    """Rehydrates the five UVI policy families from their canonical projection.

    The durable registry stores each artifact as the same canonical structure
    :func:`to_canonical_obj` produces for digesting, and asks this codec to
    rebuild the exact runtime type on read. Decoding is driven by the contracts'
    own type annotations (dataclass fields, enums, tuples, optionals, aware
    datetimes), so a field the contracts add later is decoded without a change
    here, and a value the contracts refuse at construction is refused on read
    exactly as it would be on issuance.

    Refuses anything that is not one of the five families under this adapter's
    id: a record this codec cannot rehydrate is a storage integrity failure, not
    an absent record.
    """

    adapter_id = UVI_ADAPTER_ID

    _TYPES_BY_NAME: dict[str, type] = {
        cls.__name__: cls for cls in SUPPORTED_UVI_POLICY_FAMILIES.values()
    }

    def encode(self, policy: object) -> Any:
        if type(policy) not in _FAMILY_BY_TYPE:
            raise UnsupportedPolicyArtifactError(
                f"{type(policy).__name__!r} is not a UVI policy family artifact"
            )
        return to_canonical_obj(policy, path="$")

    def decode(self, *, adapter_id: str, policy_type: str, canonical: Any) -> object:
        if adapter_id != UVI_ADAPTER_ID:
            raise UnsupportedPolicyArtifactError(
                f"UviPolicyArtifactCodec does not decode artifacts of adapter {adapter_id!r}"
            )
        cls = self._TYPES_BY_NAME.get(policy_type)
        if cls is None:
            raise UnsupportedPolicyArtifactError(
                f"{policy_type!r} is not one of the five supported UVI policy families"
            )
        policy = decode_dataclass(cls, canonical, path="$")
        if type(policy) is not cls:
            raise UnsupportedPolicyArtifactError("decoded artifact is not the declared type")
        return policy

