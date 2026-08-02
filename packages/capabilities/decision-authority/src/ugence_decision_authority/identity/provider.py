"""Principal identity — the resolved actor and the provider port that resolves it.

The kernel depends only on the :class:`IdentityProvider` protocol, never on a
concrete IdP. ``ActorIdentity`` is the resolved principal context an operation
authorizes against.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from .actor import ActorType


@dataclass(frozen=True)
class ActorIdentity:
    """The resolved identity of an actor, as returned by an IdentityProvider."""

    actor_id: str
    actor_type: ActorType
    authenticated: bool


@runtime_checkable
class IdentityProvider(Protocol):
    """Authentication hook.

    Real deployments supply an OIDC/SAML/workload-identity provider; the kernel
    depends only on this protocol, never on a concrete provider.
    """

    def authenticate(self, actor_id: str) -> ActorIdentity: ...


class StaticIdentityProvider:
    """A simple, in-memory identity provider for development and tests."""

    def __init__(self, identities: Optional[dict[str, ActorIdentity]] = None) -> None:
        self._identities: dict[str, ActorIdentity] = dict(identities or {})

    def register(self, identity: ActorIdentity) -> None:
        self._identities[identity.actor_id] = identity

    def register_human(self, actor_id: str, *, authenticated: bool = True) -> ActorIdentity:
        ident = ActorIdentity(actor_id, ActorType.HUMAN, authenticated)
        self._identities[actor_id] = ident
        return ident

    def register_ai(self, actor_id: str, *, authenticated: bool = True) -> ActorIdentity:
        ident = ActorIdentity(actor_id, ActorType.AI, authenticated)
        self._identities[actor_id] = ident
        return ident

    def register_service(self, actor_id: str, *, authenticated: bool = True) -> ActorIdentity:
        ident = ActorIdentity(actor_id, ActorType.SYSTEM, authenticated)
        self._identities[actor_id] = ident
        return ident

    def authenticate(self, actor_id: str) -> ActorIdentity:
        # Unknown principals resolve as unauthenticated, never as a human.
        return self._identities.get(
            actor_id, ActorIdentity(actor_id, ActorType.SYSTEM, False)
        )
