"""Baseline action provider — a capability-limited alternative ActionGovernanceProvider.

A legitimate, deterministic validation implementation (NOT a production competitor)
used to prove the framework supports heterogeneous action providers. Authorization
only — it never executes. Independent of ActionGate and of all assertion providers;
its core imports neither DGM nor the framework. Import from ``baseline_action_provider.api``.
"""
from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
