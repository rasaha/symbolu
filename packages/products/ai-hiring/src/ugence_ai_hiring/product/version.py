"""Product version metadata (H6 §6, §21).

This is the **AI Hiring product** version — distinct from the repository's
``symbolu`` distribution version. It is deliberately **pre-1.0**: the public API
surface (:mod:`ugence_ai_hiring.product`) is stable enough to demonstrate and pilot, but
the semantic-versioning contract explicitly reserves the right to change before a
1.0 release, and no production external-effect adapters ship in this package.

Semantics of the pre-1.0 line (per semver §4):
- ``0.MINOR.PATCH`` — anything MAY change; a MINOR bump signals a
  potentially-breaking public-API change, a PATCH bump signals a
  backwards-compatible fix or additive change.
- The ``0.`` prefix is a standing notice: **not** certified for production
  hiring decisions, integrations, or fairness/compliance claims.

The number encodes completed build phases H0–H6 as ``0.6.x``; it is a maturity
marker for the *packaging*, not a production-readiness certification.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Pre-1.0 AI Hiring product version (H0–H6 complete; controlled-pilot maturity).
PRODUCT_VERSION = "0.6.0"

#: The frozen Decision Governance Platform release this product is built on.
PLATFORM_BASELINE = "v1.0"

#: Human-readable stability tier. NOT a production certification.
STABILITY = "pre-1.0 / controlled-pilot"


@dataclass(frozen=True)
class VersionInfo:
    product_version: str
    platform_baseline: str
    stability: str
    production_certified: bool

    def to_dict(self) -> dict:
        return {
            "product_version": self.product_version,
            "platform_baseline": self.platform_baseline,
            "stability": self.stability,
            "production_certified": self.production_certified,
        }


def version_info() -> VersionInfo:
    """Return structured version metadata.

    ``production_certified`` is hard-coded ``False``: this package ships only
    deterministic simulation adapters and makes no production, scale, or
    fairness-compliance claim.
    """
    return VersionInfo(
        product_version=PRODUCT_VERSION,
        platform_baseline=PLATFORM_BASELINE,
        stability=STABILITY,
        production_certified=False,
    )
