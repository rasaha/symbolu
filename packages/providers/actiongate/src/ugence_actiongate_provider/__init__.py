"""Ugence ActionGate provider — the canonical action-governance provider package.

ActionGate implements the neutral ``ActionGovernanceProvider`` contract
(**authorization only**) by adapting the ActionGate policy engine. It evaluates
whether a proposed action is authorized under the supplied authority, policy, risk,
evidence, and decision context and returns an authorization outcome with
constraints, obligations, expiry, authority basis, reason codes, and a trace id. It
plugs into the platform through the Provider Framework's
``ActionGovernanceControlPlaneAdapter`` → ``ActionControlPlanePort``, leaving the
frozen kernel unaware of ActionGate.

ActionGate **does not** dispatch, execute, observe, reconcile, or compensate an
action; it has no execution surface and never treats authorization as proof of
execution.

Canonical distribution: ``ugence-actiongate-provider``. Canonical import namespace:
``ugence_actiongate_provider``. The legacy ``actiongate_provider`` namespace is
preserved as a logic-free compatibility facade that re-exports the identical objects
from this package.

Dependency direction: application → ugence_actiongate_provider →
``ugence_governance_provider_framework.api``. The ActionGate *core* (``core.py``)
imports neither the framework nor the kernel. ActionGate is a peer of TAP and is
entirely independent of it: ActionGate never imports or invokes TAP, and TAP never
imports or invokes ActionGate.

Import the public surface from ``ugence_actiongate_provider.api``.
"""
from __future__ import annotations

from .version import __version__, version_info

__all__ = ["__version__", "version_info"]
