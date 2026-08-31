"""Stable identifiers for the Agent Constitution policy family.

Every constant here is bound into a digest, a coordinate, or both. Moving one
moves an artifact digest, which is the point: these are identity, not
configuration. The four family values were ratified as one table, whole
(`ACC-S1-Q1`), so none may change independently of a new ruling.

Two naming notes, both deliberate and both inherited from the ratified
strategy-permission discipline:

* the scope and lifecycle collections are named ``ADMITTED_`` rather than
  ``SUPPORTED_``. ``SUPPORTED`` is a member of the Agentic Proposer's reserved
  authority vocabulary, and this distribution keeps every reserved term out of
  its surface and its message text entirely rather than relying on a reader to
  notice that a constant name is not an exception name.
* ``CONSTITUTION_VOCABULARY_VERSION`` is a **fixed value, ruled** — see its own
  comment. It enters the canonical projection and therefore every issued
  constitution's body digest, so it is identity, never configuration.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "AGENT_CONSTITUTION_ADAPTER_ID",
    "AGENT_CONSTITUTION_POLICY_FAMILY",
    "AGENT_CONSTITUTION_POLICY_TYPE",
    "CONSTITUTION_VOCABULARY_VERSION",
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
#: Ratified by `ACC-S1-Q1`.
AGENT_CONSTITUTION_ADAPTER_ID: Final[str] = "ugence.agent-constitution/v1"

#: The ``policy_family`` component of every coordinate this family issues. The
#: shared authority identifies a version by coordinate, so two families must never
#: collide in that space: this value collides with no UVI family value, not with
#: ``cloud_scaling.capacity_bounds`` and not with
#: ``agentic_proposer.strategy_permission``. Ratified by `ACC-S1-Q1`; the
#: registration-time guard (`ACC-S1-Q3`) re-asserts the non-collision over every
#: assembled registry.
AGENT_CONSTITUTION_POLICY_FAMILY: Final[str] = "agent_governance.agent_constitution"

#: The ``policy_type`` framed into the body digest alongside the adapter id, and
#: the canonical technical artifact name the `OD-C5=A` "narrower name" ruling
#: settled: the artifact class and the policy type are the same word deliberately.
#: Stated as a constant so a class rename is a deliberate, digest-moving act
#: rather than a silent consequence of refactoring.
AGENT_CONSTITUTION_POLICY_TYPE: Final[str] = "AgentConstitutionPolicy"

#: The one clause vocabulary this family's bounds are drawn from.
#:
#: Fixed **by owner ruling** (`ACC-S1-Q1`). It participates in the canonical
#: projection and therefore in every issued constitution's body digest, so
#: changing it later moves every digest and is a new policy version rather than
#: an edit. No process for versioning the clause vocabulary is settled by that
#: ruling, and none is implied here.
CONSTITUTION_VOCABULARY_VERSION: Final[str] = "ugence.agent-constitution/clauses/v1"

POLICY_SCOPE_GLOBAL: Final[str] = "GLOBAL"
POLICY_SCOPE_TENANT: Final[str] = "TENANT"

#: The two scopes this family admits — reused verbatim from the ratified
#: strategy-permission envelope, no new member (`ACC-S1-Q1`). ``GLOBAL`` carries
#: the authority's canonical empty tenant component; ``TENANT`` requires a
#: non-empty one.
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
