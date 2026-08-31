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
population call performs none of them — a conflicting entry fails closed.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Optional, Tuple

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

__all__ = ["populate_reference_map"]


def populate_reference_map(
    *,
    record: IssuedPolicyRecord,
    adapters: AdapterRegistry,
    existing: Optional[Mapping[Tuple[str, str], PolicyCoordinate]] = None,
) -> Mapping[Tuple[str, str], PolicyCoordinate]:
    """Derive reference-map entries from one issued record; return the merged map.

    Returns a **new, read-only** mapping: ``existing`` (validated, unchanged)
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
    return MappingProxyType(merged)


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
