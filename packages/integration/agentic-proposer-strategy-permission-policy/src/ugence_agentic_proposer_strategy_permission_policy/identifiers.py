"""Stable identifiers for the strategy-permission policy family.

Every constant here is bound into a digest, a coordinate, or both. Moving one
moves an artifact digest, which is the point: these are identity, not
configuration.

Two naming notes, both deliberate:

* the scope and lifecycle collections are named ``ADMITTED_`` rather than
  ``SUPPORTED_``. ``SUPPORTED`` is a member of the Agentic Proposer's reserved
  authority vocabulary, and this distribution keeps every reserved term out of
  its surface and its message text entirely rather than relying on a reader to
  notice that a constant name is not an exception name.
* ``STRATEGY_VOCABULARY_VERSION`` is a **fixed value, ruled** — see its own
  comment. It enters the canonical projection and therefore every issued
  policy's body digest, so it is identity, never configuration.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "STRATEGY_PERMISSION_ADAPTER_ID",
    "STRATEGY_PERMISSION_POLICY_FAMILY",
    "STRATEGY_PERMISSION_POLICY_TYPE",
    "STRATEGY_VOCABULARY_VERSION",
    "POLICY_SCOPE_GLOBAL",
    "POLICY_SCOPE_TENANT",
    "ADMITTED_POLICY_SCOPES",
    "LIFECYCLE_DRAFT",
    "LIFECYCLE_APPROVED_ACTIVE",
    "LIFECYCLE_SUPERSEDED",
    "LIFECYCLE_WITHDRAWN",
    "ADMITTED_LIFECYCLE_STATES",
    "ACTIVE_LIFECYCLE_STATE",
]

#: Stable adapter identity, framed into every body digest this adapter produces.
STRATEGY_PERMISSION_ADAPTER_ID: Final[str] = "ugence.agentic-proposer.strategy-permission/v1"

#: The ``policy_family`` component of every coordinate this family issues. The
#: shared authority identifies a version by coordinate, so two families must never
#: collide in that space: this value collides with no UVI family value and not with
#: ``cloud_scaling.capacity_bounds``.
STRATEGY_PERMISSION_POLICY_FAMILY: Final[str] = "agentic_proposer.strategy_permission"

#: The ``policy_type`` framed into the body digest alongside the adapter id. Stated
#: as a constant so a class rename is a deliberate, digest-moving act rather than a
#: silent consequence of refactoring.
STRATEGY_PERMISSION_POLICY_TYPE: Final[str] = "StrategyPermissionPolicy"

#: The one vocabulary this family's permitted sets are drawn from.
#:
#: Fixed **by owner ruling** (`S2B-PF-BASE`, §1.1 of the ratification): the design
#: stated the string illustratively and the ruling hardened it into the required
#: value. It participates in the canonical projection and therefore in every issued
#: policy's body digest, so changing it later moves every digest and is a new policy
#: version rather than an edit.
STRATEGY_VOCABULARY_VERSION: Final[str] = "ugence.agentic-proposer.reasoning-strategy/v1"

POLICY_SCOPE_GLOBAL: Final[str] = "GLOBAL"
POLICY_SCOPE_TENANT: Final[str] = "TENANT"

#: The two scopes this family admits. ``GLOBAL`` carries the authority's canonical
#: empty tenant component; ``TENANT`` requires a non-empty one.
ADMITTED_POLICY_SCOPES: Final[frozenset] = frozenset(
    {POLICY_SCOPE_GLOBAL, POLICY_SCOPE_TENANT}
)

LIFECYCLE_DRAFT: Final[str] = "DRAFT"
LIFECYCLE_APPROVED_ACTIVE: Final[str] = "APPROVED_ACTIVE"
LIFECYCLE_SUPERSEDED: Final[str] = "SUPERSEDED"
LIFECYCLE_WITHDRAWN: Final[str] = "WITHDRAWN"

ADMITTED_LIFECYCLE_STATES: Final[frozenset] = frozenset(
    {
        LIFECYCLE_DRAFT,
        LIFECYCLE_APPROVED_ACTIVE,
        LIFECYCLE_SUPERSEDED,
        LIFECYCLE_WITHDRAWN,
    }
)

#: The single lifecycle state the authority may resolve. Every other state fails
#: closed with the authority's own lifecycle reason.
ACTIVE_LIFECYCLE_STATE: Final[str] = LIFECYCLE_APPROVED_ACTIVE
