"""ActionGate provider — the first real Action Governance provider for DGM.

Implements the neutral ``ActionGovernanceProvider`` contract (authorization only)
by adapting the ActionGate engine. It plugs into DGM through the Provider
Framework's ``ActionGovernanceControlPlaneAdapter`` → ``ActionControlPlanePort``,
leaving the frozen kernel completely unaware of ActionGate.

Dependency direction: application → actiongate_provider → {governance_providers,
decision_governance}.api. The ActionGate *core* (``core.py``) imports neither.
Import the public surface from ``actiongate_provider.api``.
"""
from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
