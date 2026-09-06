"""Governed reference-map population (`ACC-IA-3`): derivation, never entry.

The conformance resolver's ``(tenant_id, role_contract_ref)`` →
``PolicyCoordinate`` mapping was ratified as injected deployment trust, and its
population was a disclosed, carried gap. This module narrows that gap: **an
entry exists only by derivation from an issued record**. The function below
takes no entry, no key, no coordinate and no role list from its caller — it
takes the record, reads the signed artifact the record carries, and derives one
entry per reference in that artifact's own ``governed_role_refs``, each mapped
to the record's exact coordinate under the coordinate's own tenant component.

Why the record and not the policy: a caller who could pass the artifact and the
coordinate separately could pair a body with a coordinate it was never issued
under. The record binds the two — and the derivation still re-checks that bond
through the adapter rather than trusting it, so a hand-built record whose
coordinate does not equal its carried artifact's derived coordinate is refused.

What remains outside this module, deliberately: removing an entry, re-pointing
an entry, and choosing *which* previously derived entries compose into one
deployment's map. Those are operator reconfigurations of injected trust, and a
population call performs none of them — a conflicting entry fails closed. Under
``ACC-RECONFIG`` they stay outside the repository: an operator who needs a
different map derives one from the records it intends, rather than editing a map
this module produced.

The derived map is returned as a :class:`DerivedReferenceMap`, a read-only
mapping this module alone can construct (``ACC-COUPLING``). It is what
``ActivationRoot.constitution_resolver`` requires, so the orchestrated path
cannot be handed a map that was typed rather than derived. The conformance
package's own ``build_constitution_resolver`` still accepts any mapping — the
injected-trust posture there is ratified and untouched — so a deployment that
composes conformance directly still carries the original disclosed gap.
"""

from __future__ import annotations

from collections.abc import Mapping as _MappingABC
from types import MappingProxyType
from typing import Iterator, Mapping, Optional, Tuple

from ugence_agent_constitution_policy import AgentConstitutionPolicy
from ugence_policy_authority.api import (
    AdapterRegistry,
    IssuedPolicyRecord,
    PolicyCoordinate,
)

from .errors import (
    ActivationRequestError,
    ReferenceMapConflictError,
    ReferenceMapDerivationError,
)

__all__ = ["DerivedReferenceMap", "populate_reference_map"]

#: Construction token. A ``DerivedReferenceMap`` proves its own provenance by
#: being unconstructible outside this module: a caller who could build one could
#: type the entries it claims to have derived, which is the whole gap this
#: closes.
_DERIVED = object()


class DerivedReferenceMap(_MappingABC):
    """A reference map derived from issued records, and never entered by hand.

    A read-only ``Mapping`` of ``(tenant_id, role_contract_ref)`` to
    ``PolicyCoordinate``, plus the coordinates of the records it derived from.
    It behaves as a mapping everywhere one is accepted; what it adds is that its
    existence is evidence of how it was built.
    """

    __slots__ = ("_entries", "_derived_from")

    def __init__(self, token: object, entries, derived_from) -> None:
        if token is not _DERIVED:
            raise ActivationRequestError(
                "a DerivedReferenceMap is constructed by populate_reference_map "
                "alone; entries derive from an issued record, never from a "
                "caller-built mapping"
            )
        object.__setattr__(self, "_entries", MappingProxyType(dict(entries)))
        object.__setattr__(self, "_derived_from", tuple(derived_from))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"DerivedReferenceMap is immutable; cannot set {name!r}")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"DerivedReferenceMap is immutable; cannot delete {name!r}")

    def __getitem__(self, key):
        return self._entries[key]

    def __iter__(self) -> Iterator:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"DerivedReferenceMap({dict(self._entries)!r})"

    @property
    def derived_from(self) -> Tuple[PolicyCoordinate, ...]:
        """The coordinates of the issued records every entry came from."""

        return self._derived_from


def populate_reference_map(
    *,
    record: IssuedPolicyRecord,
    adapters: AdapterRegistry,
    existing: Optional[Mapping[Tuple[str, str], PolicyCoordinate]] = None,
) -> DerivedReferenceMap:
    """Derive reference-map entries from one issued record; return the merged map.

    Returns a **new, read-only** :class:`DerivedReferenceMap`: ``existing``
    (validated, unchanged)
    plus one entry per reference in the record's artifact's
    ``governed_role_refs``. An existing entry already binding one of those keys
    to a *different* coordinate raises ``ReferenceMapConflictError`` and nothing
    is returned; an existing entry already binding the *same* coordinate is
    idempotent. The caller's ``existing`` object is never mutated.
    """

    if type(record) is not IssuedPolicyRecord:
        raise ActivationRequestError(
            "record must be exactly an IssuedPolicyRecord; entries derive from an "
            "issued record only, never from loose values"
        )
    if not isinstance(adapters, AdapterRegistry):
        raise ActivationRequestError("adapters must be an AdapterRegistry")

    policy = record.policy
    if type(policy) is not AgentConstitutionPolicy:
        raise ReferenceMapDerivationError(
            "the issued record does not carry exactly an AgentConstitutionPolicy; "
            "no entry derives from another family's record"
        )

    # Re-derive the coordinate from the carried artifact through the adapter and
    # require exact equality with the record's signed coordinate. A record whose
    # halves disagree yields nothing.
    descriptor = adapters.describe(policy)
    if descriptor.coordinate != record.coordinate:
        raise ReferenceMapDerivationError(
            "the record's coordinate does not equal the coordinate derived from "
            "the artifact it carries; nothing derives from a record whose halves "
            "disagree"
        )

    derived = {
        (record.coordinate.tenant_id, role_ref): record.coordinate
        for role_ref in policy.governed_role_refs
    }

    merged = dict(_validated_existing(existing))
    for key, coordinate in derived.items():
        present = merged.get(key)
        if present is not None and present != coordinate:
            raise ReferenceMapConflictError(
                "an existing entry already binds this tenant and role reference "
                "to a different coordinate; conflicting entries fail closed and "
                "are never overwritten"
            )
        merged[key] = coordinate
    prior = getattr(existing, "derived_from", ())
    return DerivedReferenceMap(
        _DERIVED, merged, tuple(prior) + (record.coordinate,)
    )


def _validated_existing(
    existing: Optional[Mapping[Tuple[str, str], PolicyCoordinate]],
) -> Mapping[Tuple[str, str], PolicyCoordinate]:
    """Structurally validate a prior map; provenance stays the operator's.

    The same shape rule the conformance resolver enforces at construction:
    every key exactly a ``(tenant_id, role_contract_ref)`` pair of strings,
    every value exactly a ``PolicyCoordinate``.
    """

    if existing is None:
        return {}
    if not isinstance(existing, Mapping):
        raise ActivationRequestError("existing must be a mapping or None")
    for key, coordinate in existing.items():
        if (
            type(key) is not tuple
            or len(key) != 2
            or type(key[0]) is not str
            or type(key[1]) is not str
        ):
            raise ActivationRequestError(
                "every existing key must be a (tenant_id, role_contract_ref) "
                "pair of strings"
            )
        if type(coordinate) is not PolicyCoordinate:
            raise ActivationRequestError(
                "every existing value must be exactly a PolicyCoordinate"
            )
    return existing
