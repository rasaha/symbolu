"""Stable identifiers for the Cloud Scaling capacity-bounds policy family.

Every constant here is bound into a digest, a coordinate, or both. Moving one
moves an artifact digest, which is the point: these are identity, not
configuration.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "CAPACITY_BOUNDS_ADAPTER_ID",
    "CAPACITY_BOUNDS_POLICY_FAMILY",
    "CAPACITY_BOUNDS_POLICY_TYPE",
    "POLICY_SCOPE_GLOBAL",
    "POLICY_SCOPE_TENANT",
    "SUPPORTED_POLICY_SCOPES",
    "LIFECYCLE_APPROVED_ACTIVE",
    "LIFECYCLE_DRAFT",
    "LIFECYCLE_SUPERSEDED",
    "LIFECYCLE_WITHDRAWN",
    "SUPPORTED_LIFECYCLE_STATES",
    "ACTIVE_LIFECYCLE_STATE",
]

#: Stable adapter identity, framed into every body digest this adapter produces.
CAPACITY_BOUNDS_ADAPTER_ID: Final[str] = "ugence.cloud-scaling.capacity-bounds/v1"

#: The ``policy_family`` component of every coordinate this family issues. Distinct
#: from any UVI family: the shared authority identifies a version by coordinate, and
#: two families must never collide in that space.
CAPACITY_BOUNDS_POLICY_FAMILY: Final[str] = "cloud_scaling.capacity_bounds"

#: The ``policy_type`` framed into the body digest alongside the adapter id. It is
#: the runtime type name of the one artifact class this adapter recognizes, stated
#: as a constant so a rename is a deliberate, digest-moving act rather than a
#: silent consequence of refactoring.
CAPACITY_BOUNDS_POLICY_TYPE: Final[str] = "CapacityBoundsPolicy"

POLICY_SCOPE_GLOBAL: Final[str] = "GLOBAL"
POLICY_SCOPE_TENANT: Final[str] = "TENANT"

#: The two scopes this family admits. ``GLOBAL`` carries the authority's canonical
#: empty tenant component; ``TENANT`` requires a non-empty one.
SUPPORTED_POLICY_SCOPES: Final[frozenset] = frozenset(
    {POLICY_SCOPE_GLOBAL, POLICY_SCOPE_TENANT}
)

LIFECYCLE_DRAFT: Final[str] = "DRAFT"
LIFECYCLE_APPROVED_ACTIVE: Final[str] = "APPROVED_ACTIVE"
LIFECYCLE_SUPERSEDED: Final[str] = "SUPERSEDED"
LIFECYCLE_WITHDRAWN: Final[str] = "WITHDRAWN"

SUPPORTED_LIFECYCLE_STATES: Final[frozenset] = frozenset(
    {
        LIFECYCLE_DRAFT,
        LIFECYCLE_APPROVED_ACTIVE,
        LIFECYCLE_SUPERSEDED,
        LIFECYCLE_WITHDRAWN,
    }
)

#: The single lifecycle state the authority may resolve. Every other state fails
#: closed as ``LIFECYCLE_NOT_ACTIVE``.
ACTIVE_LIFECYCLE_STATE: Final[str] = LIFECYCLE_APPROVED_ACTIVE
