"""Product version + maturity metadata for Ugence Procurement.

This is the **Procurement product** capability-maturity marker — distinct from the
independent **distribution** (wheel packaging) version in
:mod:`ugence_procurement.version`.

Procurement is deliberately at a *much lower evidence maturity* than the AI Hiring
product. Its complete reference workflow is verified offline and deterministically,
but it has had **no** enterprise pilot and carries **no** production certification.
The maturity classification is intentionally conservative.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Pre-1.0 Procurement product version. The reference workflow (request → validation
#: → assessment → recommendation → human decision → action → authorization →
#: dispatch → outcome → reconciliation → compensation) is complete and offline-verified.
PRODUCT_VERSION = "0.1.0"

#: The frozen Decision Governance Platform (Decision Authority kernel) release this
#: product composes.
PLATFORM_BASELINE = "v1.0"

#: Human-readable stability tier. NOT a production certification.
STABILITY = "pre-1.0 / reference-workflow"

#: Product evidence maturity. The most conservative classification supported by the
#: live results: the full reference workflow is verified offline, nothing more.
EVIDENCE_MATURITY = "REFERENCE_WORKFLOW_OFFLINE_VERIFIED"

#: Forward-looking readiness note. Explicitly NOT a validation claim.
READINESS = "READY_FOR_BOUNDED_SHADOW_PILOT_DESIGN"

#: Hard, non-negotiable maturity flags (see MATURITY.md).
PILOT_VALIDATED = False
PRODUCTION_CERTIFIED = False


@dataclass(frozen=True)
class ProductMaturity:
    product_version: str
    platform_baseline: str
    stability: str
    evidence_maturity: str
    readiness: str
    pilot_validated: bool
    production_certified: bool

    def to_dict(self) -> dict:
        return {
            "product_version": self.product_version,
            "platform_baseline": self.platform_baseline,
            "stability": self.stability,
            "evidence_maturity": self.evidence_maturity,
            "readiness": self.readiness,
            "pilot_validated": self.pilot_validated,
            "production_certified": self.production_certified,
        }


def product_maturity() -> ProductMaturity:
    """Return the conservative product maturity record.

    ``pilot_validated`` and ``production_certified`` are hard-coded ``False``: the
    package ships only deterministic, offline reference adapters and makes no
    production, scale, or enterprise-integration claim.
    """
    return ProductMaturity(
        product_version=PRODUCT_VERSION,
        platform_baseline=PLATFORM_BASELINE,
        stability=STABILITY,
        evidence_maturity=EVIDENCE_MATURITY,
        readiness=READINESS,
        pilot_validated=PILOT_VALIDATED,
        production_certified=PRODUCTION_CERTIFIED,
    )


__all__ = [
    "PRODUCT_VERSION",
    "PLATFORM_BASELINE",
    "STABILITY",
    "EVIDENCE_MATURITY",
    "READINESS",
    "PILOT_VALIDATED",
    "PRODUCTION_CERTIFIED",
    "ProductMaturity",
    "product_maturity",
]
