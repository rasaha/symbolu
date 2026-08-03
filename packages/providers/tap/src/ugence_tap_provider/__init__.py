"""TAP provider — the second real governance provider for DGM (assertion governance).

Implements the neutral ``AssertionGovernanceProvider`` contract (assertion support
only) by adapting the TAP engine. TAP evaluates whether a material assertion is
adequately supported by supplied evidence and returns a structured, component-level
result that integrates into DGM's **assessment / recommendation** workflow via the
Provider Framework's ``AssertionAssessmentIntegration`` — never into authorization
or execution.

Dependency direction: application → tap_provider → {governance_providers,
decision_governance}.api. The TAP *core* (``core/``) imports neither. TAP is a peer
of ActionGate and is entirely independent of it: TAP never imports or invokes
ActionGate, and ActionGate never imports or invokes TAP.

Import the public surface from ``tap_provider.api``.
"""
from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
