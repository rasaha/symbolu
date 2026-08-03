"""Distribution + product version metadata for Ugence Procurement.

Two version concepts are kept deliberately separate:

* :data:`DISTRIBUTION_VERSION` — the independent **wheel packaging** lifecycle of
  the ``ugence-procurement`` distribution. It starts at ``0.1.0`` for the first
  independent extraction and moves with packaging changes, not product maturity.
* :data:`PRODUCT_VERSION` — the **Procurement product** capability/evidence marker
  (sourced from :mod:`ugence_procurement.product.version`). It is unchanged by
  extraction.

Neither is a production-readiness certification. :func:`version_info` always
reports ``production_certified=False`` and ``pilot_validated=False``: the package
ships only deterministic, offline reference adapters and makes no production,
scale, enterprise-integration, or ERP claim.
"""

from __future__ import annotations

import importlib
import importlib.metadata as _md
from dataclasses import dataclass, field

from .product.version import (
    EVIDENCE_MATURITY,
    PILOT_VALIDATED,
    PLATFORM_BASELINE,
    PRODUCT_VERSION,
    PRODUCTION_CERTIFIED,
    READINESS,
    STABILITY,
)

#: Independent distribution (wheel packaging) version. Distinct from the product
#: capability/evidence version below. First independent extraction of the
#: procurement reference domain into a standalone Ugence product package.
DISTRIBUTION_VERSION = "0.1.0"

#: Distribution name on the index.
DISTRIBUTION_NAME = "ugence-procurement"

#: Product name (customer-facing).
PRODUCT_NAME = "Ugence Procurement"

#: Canonical import namespace.
CANONICAL_NAMESPACE = "ugence_procurement"

#: Release classification for the independent package. Promoted to
#: ``INDEPENDENT_PACKAGE_VERIFIED`` only when every packaging + equivalence + isolation
#: gate passes (see docs/MATURITY.md). This constant is the *aspirational target*;
#: the honest product-evidence classification remains ``EVIDENCE_MATURITY`` above.
RELEASE_CLASSIFICATION = "INDEPENDENT_PACKAGE_VERIFIED"

# Optional integration extras this distribution declares, mapped to the module that
# must be importable for the integration to be usable. version_info() probes
# availability at runtime. The core (contracts, deterministic policy, in-memory
# persistence, neutral authorization ports, offline supplier adapter) is always
# present via the core wheel and its ugence-decision-authority dependency, so it is
# NOT listed here.
_OPTIONAL_INTEGRATIONS = {
    "api": "fastapi",
}

# Runtime dependencies whose versions we surface for provenance/debugging.
_TRACKED_DEPENDENCIES = (
    "pydantic",
    "ugence-decision-authority",
)


def _dist_version(name: str) -> str | None:
    try:
        return _md.version(name)
    except Exception:  # pragma: no cover - best effort
        return None


def _module_available(module: str | None) -> bool:
    if module is None:
        return False
    try:
        importlib.import_module(module)
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class VersionInfo:
    """Structured version + provenance metadata for the independent package."""

    distribution: str
    distribution_version: str
    product: str
    product_version: str
    canonical_namespace: str
    platform_baseline: str
    stability: str
    release_classification: str
    reference_workflow_verified: bool
    pilot_validated: bool
    production_certified: bool
    evidence_maturity: str
    readiness: str
    dependency_versions: dict = field(default_factory=dict)
    optional_integrations: dict = field(default_factory=dict)
    build_commit: str | None = None

    def to_dict(self) -> dict:
        return {
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
            "product": self.product,
            "product_version": self.product_version,
            "canonical_namespace": self.canonical_namespace,
            "platform_baseline": self.platform_baseline,
            "stability": self.stability,
            "release_classification": self.release_classification,
            "reference_workflow_verified": self.reference_workflow_verified,
            "pilot_validated": self.pilot_validated,
            "production_certified": self.production_certified,
            "evidence_maturity": self.evidence_maturity,
            "readiness": self.readiness,
            "dependency_versions": dict(self.dependency_versions),
            "optional_integrations": dict(self.optional_integrations),
            "build_commit": self.build_commit,
        }


def version_info() -> VersionInfo:
    """Return structured distribution + product version metadata.

    ``pilot_validated`` and ``production_certified`` are hard-coded ``False``.
    ``dependency_versions`` is best-effort resolved from installed distribution
    metadata; ``optional_integrations`` reports whether each optional integration is
    importable in the current environment.
    """
    deps = {name: _dist_version(name) for name in _TRACKED_DEPENDENCIES}
    integrations = {
        name: _module_available(module)
        for name, module in _OPTIONAL_INTEGRATIONS.items()
    }
    return VersionInfo(
        distribution=DISTRIBUTION_NAME,
        distribution_version=DISTRIBUTION_VERSION,
        product=PRODUCT_NAME,
        product_version=PRODUCT_VERSION,
        canonical_namespace=CANONICAL_NAMESPACE,
        platform_baseline=PLATFORM_BASELINE,
        stability=STABILITY,
        release_classification=RELEASE_CLASSIFICATION,
        reference_workflow_verified=True,
        pilot_validated=PILOT_VALIDATED,
        production_certified=PRODUCTION_CERTIFIED,
        evidence_maturity=EVIDENCE_MATURITY,
        readiness=READINESS,
        dependency_versions=deps,
        optional_integrations=integrations,
        build_commit=None,  # set by release tooling when available
    )


__all__ = [
    "DISTRIBUTION_VERSION",
    "DISTRIBUTION_NAME",
    "PRODUCT_NAME",
    "PRODUCT_VERSION",
    "CANONICAL_NAMESPACE",
    "PLATFORM_BASELINE",
    "STABILITY",
    "RELEASE_CLASSIFICATION",
    "VersionInfo",
    "version_info",
]
