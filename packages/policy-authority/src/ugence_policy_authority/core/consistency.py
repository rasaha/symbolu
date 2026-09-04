"""Declared registry consistency — a typed descriptor, never a flippable Boolean.

Ratified under decision D-3 of the execution-reservation scoping (adopting
Benchmark Registry ruling D-22 Posture B for this package, closing ADR §15.7).
The vocabulary mirrors the Benchmark Registry Authority's descriptor so a
composition root reads both the same way.

Two scopes exist and each guarantee answer is a **derived read-only property**
hard-coded from the scope, so no assignment path can turn a disclaimer into a
claim:

* ``PROCESS_LOCAL_ONLY`` — the in-memory reference registry: process-local
  atomicity and read-after-write, nothing more.
* ``SINGLE_NODE_DURABLE`` — the SQLite registry: adds durability across
  restarts, coordination between processes on **one host** (the SQLite write
  lock serializes writers), and revocation that is atomic across those
  processes. Distributed strong consistency and eventual-consistency safety stay
  **explicitly disclaimed** — there is no replication, no second node, and no
  claim about either.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import PolicyAuthorityRequestError

__all__ = [
    "PolicyRegistryConsistencyScope",
    "PolicyRegistryConsistencyClaim",
    "PolicyRegistryConsistencyDescriptor",
    "declared_consistency",
]


class PolicyRegistryConsistencyScope(str, Enum):
    """The consistency scope a registry declares. Two ratified members, no third."""

    PROCESS_LOCAL_ONLY = "PROCESS_LOCAL_ONLY"
    SINGLE_NODE_DURABLE = "SINGLE_NODE_DURABLE"


class PolicyRegistryConsistencyClaim(str, Enum):
    """A guarantee is claimed within the declared scope or explicitly disclaimed.

    No "unknown" member exists: an unavailable guarantee must be stated, never
    left for a caller to assume.
    """

    CLAIMED_WITHIN_DECLARED_SCOPE = "CLAIMED_WITHIN_DECLARED_SCOPE"
    EXPLICITLY_DISCLAIMED = "EXPLICITLY_DISCLAIMED"


_CLAIMED = PolicyRegistryConsistencyClaim.CLAIMED_WITHIN_DECLARED_SCOPE
_DISCLAIMED = PolicyRegistryConsistencyClaim.EXPLICITLY_DISCLAIMED


@dataclass(frozen=True)
class PolicyRegistryConsistencyDescriptor:
    """One field, the scope; every guarantee is derived from it and read-only."""

    scope: PolicyRegistryConsistencyScope = PolicyRegistryConsistencyScope.PROCESS_LOCAL_ONLY

    def __post_init__(self) -> None:
        if not isinstance(self.scope, PolicyRegistryConsistencyScope):
            raise PolicyAuthorityRequestError(
                "PolicyRegistryConsistencyDescriptor.scope must be a "
                "PolicyRegistryConsistencyScope member"
            )

    @property
    def _durable(self) -> bool:
        return self.scope is PolicyRegistryConsistencyScope.SINGLE_NODE_DURABLE

    @property
    def process_local_atomicity(self) -> PolicyRegistryConsistencyClaim:
        """Claimed in both scopes."""

        return _CLAIMED

    @property
    def read_after_write(self) -> PolicyRegistryConsistencyClaim:
        """Claimed in both scopes."""

        return _CLAIMED

    @property
    def durability(self) -> PolicyRegistryConsistencyClaim:
        """Survives process restart. Claimed only by the single-node durable scope."""

        return _CLAIMED if self._durable else _DISCLAIMED

    @property
    def multi_process_coordination(self) -> PolicyRegistryConsistencyClaim:
        """Writers on one host are serialized. Claimed only by the durable scope."""

        return _CLAIMED if self._durable else _DISCLAIMED

    @property
    def cross_process_atomic_revocation(self) -> PolicyRegistryConsistencyClaim:
        """A committed revocation is visible to every process on the host at once.

        The most consequential of the five: without it one process can still
        resolve a version another has revoked. Claimed only by the durable scope.
        """

        return _CLAIMED if self._durable else _DISCLAIMED

    @property
    def distributed_strong_consistency(self) -> PolicyRegistryConsistencyClaim:
        """**Explicitly disclaimed** in every scope. There is no second node."""

        return _DISCLAIMED

    @property
    def eventual_consistency_safety(self) -> PolicyRegistryConsistencyClaim:
        """**Explicitly disclaimed** in every scope. No replication exists to be safe about."""

        return _DISCLAIMED

    def claims(self) -> dict[str, str]:
        """Every guarantee by name, for audit export."""

        return {
            name: getattr(self, name).value
            for name in (
                "process_local_atomicity",
                "read_after_write",
                "durability",
                "multi_process_coordination",
                "cross_process_atomic_revocation",
                "distributed_strong_consistency",
                "eventual_consistency_safety",
            )
        }


def declared_consistency(registry: object) -> PolicyRegistryConsistencyDescriptor:
    """The consistency a registry declares.

    A registry that declares nothing is treated as ``PROCESS_LOCAL_ONLY``: an
    undeclared guarantee is never assumed to be stronger.
    """

    descriptor = getattr(registry, "consistency", None)
    if isinstance(descriptor, PolicyRegistryConsistencyDescriptor):
        return descriptor
    return PolicyRegistryConsistencyDescriptor()
