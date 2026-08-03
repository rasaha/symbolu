"""Canonical ActionGate compatibility adapter (optional, isolated).

Bridges the canonical ``ugence_actiongate_provider`` distribution
(``ActionGateProvider``, an :class:`ActionGovernanceProvider`) onto the AI Hiring
core's neutral authorization boundary (:class:`ActionAuthorizationIntegration`).

Boundary discipline:

* This module imports ``ugence_actiongate_provider`` **lazily** — only when a
  loader is called — so importing it (or the AI Hiring core) never requires the
  provider distribution to be installed.
* It implements **no** ActionGate authorization logic. Adjudication stays inside
  the injected ``ActionGateProvider``; the core only wires it through the neutral
  ``ActionGovernanceProvider`` protocol. Authorization is prepared here — it is
  **never** executed.

Install with ``pip install "ugence-ai-hiring[actiongate]"`` (resolves
``ugence-actiongate-provider``). Classification: ``OPTIONAL_CANONICAL_ADAPTER`` —
the concrete provider is a dependency-injected peer, never a core dependency.
"""

from __future__ import annotations

from typing import Any

from ..actions.actiongate_integration import ActionAuthorizationIntegration
from . import ProviderUnavailable

__all__ = [
    "load_actiongate_provider_cls",
    "build_actiongate_provider",
    "build_action_authorization_integration",
]

_DIST_HINT = (
    'pip install "ugence-ai-hiring[actiongate]"  (installs ugence-actiongate-provider)'
)


def load_actiongate_provider_cls():
    """Return the canonical ``ActionGateProvider`` class (lazy import).

    Raises :class:`ProviderUnavailable` if ``ugence-actiongate-provider`` is not
    installed.
    """
    try:
        from ugence_actiongate_provider.provider import ActionGateProvider
    except ImportError as exc:  # pragma: no cover - exercised in the no-provider env
        raise ProviderUnavailable(
            "the canonical ActionGate provider ('ugence_actiongate_provider') is "
            f"not installed; {_DIST_HINT}"
        ) from exc
    return ActionGateProvider


def build_actiongate_provider(client: Any, **kwargs: Any):
    """Construct a canonical ``ActionGateProvider`` from a caller-supplied client.

    The ``client`` (an ``ActionGateClient``) and any keyword options are passed
    straight through to the provider; this adapter adds no policy of its own.
    Returns an object satisfying the neutral ``ActionGovernanceProvider`` protocol.
    """
    provider_cls = load_actiongate_provider_cls()
    return provider_cls(client, **kwargs)


def build_action_authorization_integration(
    client: Any, *, provider_id: str = "", **kwargs: Any
) -> ActionAuthorizationIntegration:
    """Wire a canonical ActionGate provider into the core's neutral authorization
    integration. The returned integration prepares authorization records; it does
    not execute the authorized action.
    """
    provider = build_actiongate_provider(client, **kwargs)
    return ActionAuthorizationIntegration(provider, provider_id=provider_id)
