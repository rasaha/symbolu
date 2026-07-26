"""Baseline assertion provider — a capability-limited alternative AssertionGovernanceProvider.

A legitimate, deterministic validation implementation (NOT a production competitor)
used to prove the provider framework supports heterogeneous providers per family.
Implements the neutral AssertionGovernanceProvider contract with an honestly limited
capability set. Independent of TAP and of all action providers; its core imports
neither DGM nor the framework. Import the public surface from
``baseline_assertion_provider.api``.
"""
from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
