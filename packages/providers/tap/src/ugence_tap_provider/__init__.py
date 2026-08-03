"""Ugence TAP provider — the canonical assertion-governance provider package.

TAP implements the neutral ``AssertionGovernanceProvider`` contract (assertion
support only) by adapting the TAP engine. TAP evaluates whether a material
assertion is adequately supported by supplied evidence and returns a structured,
component-level result that integrates into the assessment / recommendation
workflow via the Provider Framework's ``AssertionAssessmentIntegration`` — never
into authorization or execution.

Canonical distribution: ``ugence-tap-provider``. Canonical import namespace:
``ugence_tap_provider``. The legacy ``tap_provider`` namespace is preserved as a
logic-free compatibility facade that re-exports the identical objects from this
package.

Dependency direction: application → ugence_tap_provider →
``ugence_governance_provider_framework.api``. The TAP *core* (``core/``) imports
neither the framework nor the kernel. TAP is a peer of ActionGate and is entirely
independent of it: TAP never imports or invokes ActionGate, and ActionGate never
imports or invokes TAP.

Import the public surface from ``ugence_tap_provider.api``.
"""
from __future__ import annotations

from .version import __version__, version_info

__all__ = ["__version__", "version_info"]
