"""Provider Heterogeneity, Resolution, and Failover Validation (Phase 6B).

Validates that the existing provider framework supports more than one provider per
governance family: deterministic selection by compatibility, capability, health, and
explicit policy; bounded, safe failover under infrastructure failure; and strict
prohibition of governance shopping — all without modifying any frozen component.

Selection and evaluation are provider-neutral; only composition/runner modules import
concrete providers. Import the public surface from the subpackages; run via
``python -m provider_heterogeneity_validation.run``.
"""
from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
