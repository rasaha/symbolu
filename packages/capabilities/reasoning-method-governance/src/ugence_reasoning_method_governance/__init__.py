"""Ugence Reasoning Method Governance — shared reasoning-method contracts.

Slice 1 (research-only) of
``docs/architecture/REASONING_METHOD_GOVERNANCE_CONTRACT_AND_COMMISSIONING_BALLOT.md``.
This package holds contracts only: it performs no comparison, issues no
envelope, assigns no approval, eligibility or lifecycle state, and never
imports the experimental reasoning runtime. The curated public surface is
``ugence_reasoning_method_governance.api``.
"""

from .version import __version__

__all__ = ["__version__"]
