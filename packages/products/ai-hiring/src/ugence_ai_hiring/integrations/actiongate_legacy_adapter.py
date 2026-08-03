"""Legacy ActionGate compatibility adapter (optional, isolated).

Bridges the current ``actiongate_provider`` distribution (``ActionGateProvider``,
an :class:`ActionGovernanceProvider`) onto the AI Hiring core's neutral
authorization boundary (:class:`ActionAuthorizationIntegration`).

Boundary discipline:

* This module imports ``actiongate_provider`` **lazily** — only when a loader is
  called — so importing it (or the AI Hiring core) never requires the legacy
  distribution to be installed.
* It implements **no** ActionGate authorization logic. Adjudication stays inside
  the injected ``ActionGateProvider``; the core only wires it through the neutral
  ``ActionGovernanceProvider`` protocol. Authorization is prepared here — it is
  **never** executed.

Install with ``pip install "ugence-ai-hiring[actiongate]"``. Classification:
``LEGACY_COMPATIBILITY_DEPENDENCY`` (temporary; migrates to
``ugence-actiongate-provider`` in a later dependency-only PR).
"""

from __future__ import annotations

from typing import Any

from ..actions.actiongate_integration import ActionAuthorizationIntegration
from . import LegacyProviderUnavailable

__all__ = [
    "load_actiongate_provider_cls",
    "build_actiongate_provider",
    "build_action_authorization_integration",
]

_DIST_HINT = 'pip install "ugence-ai-hiring[actiongate]"  (legacy: dgm-actiongate-provider)'


def load_actiongate_provider_cls():
    """Return the legacy ``ActionGateProvider`` class (lazy import).

    Raises :class:`LegacyProviderUnavailable` if ``actiongate_provider`` is not
    installed.
    """
    try:
        from actiongate_provider.provider import ActionGateProvider
    except ImportError as exc:  # pragma: no cover - exercised in the no-legacy env
        raise LegacyProviderUnavailable(
            "the ActionGate legacy provider ('actiongate_provider') is not "
            f"installed; {_DIST_HINT}"
        ) from exc
    return ActionGateProvider


def build_actiongate_provider(client: Any, **kwargs: Any):
    """Construct a legacy ``ActionGateProvider`` from a caller-supplied client.

    The ``client`` (an ``ActionGateClient``) and any keyword options are passed
    straight through to the legacy provider; this adapter adds no policy of its
    own. Returns an object satisfying the neutral ``ActionGovernanceProvider``
    protocol.
    """
    provider_cls = load_actiongate_provider_cls()
    return provider_cls(client, **kwargs)


def build_action_authorization_integration(
    client: Any, *, provider_id: str = "", **kwargs: Any
) -> ActionAuthorizationIntegration:
    """Wire a legacy ActionGate provider into the core's neutral authorization
    integration. The returned integration prepares authorization records; it does
    not execute the authorized action.
    """
    provider = build_actiongate_provider(client, **kwargs)
    return ActionAuthorizationIntegration(provider, provider_id=provider_id)
