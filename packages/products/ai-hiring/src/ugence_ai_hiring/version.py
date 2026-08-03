"""Distribution + product version metadata for Ugence AI Hiring.

Two version concepts are kept deliberately separate:

* :data:`DISTRIBUTION_VERSION` — the independent **wheel packaging** lifecycle of
  the ``ugence-ai-hiring`` distribution. It starts at ``0.1.0`` for the first
  independent extraction and moves with packaging changes, not product maturity.
* :data:`PRODUCT_VERSION` — the **AI Hiring product** capability-maturity marker
  (H0–H6 complete → ``0.6.x``), sourced from :mod:`ugence_ai_hiring.product.version`.
  It is unchanged by extraction.

Neither is a production-readiness certification. :func:`version_info` always
reports ``production_certified=False``: the package ships only deterministic,
offline simulation adapters and makes no production, scale, fairness, or legal
claim.
"""

from __future__ import annotations

import importlib
import importlib.metadata as _md
from dataclasses import dataclass, field

from .product.version import (
    PLATFORM_BASELINE,
    PRODUCT_VERSION,
    STABILITY,
)

#: Independent distribution (wheel packaging) version. Distinct from the product
#: capability-maturity version below. Bumped 0.1.0 -> 0.1.1 for the canonical TAP /
#: ActionGate optional-dependency normalization: a packaging/dependency-metadata
#: change only — no product capability, API, or behavior change.
DISTRIBUTION_VERSION = "0.1.1"

#: Distribution name on the index.
DISTRIBUTION_NAME = "ugence-ai-hiring"

#: Release classification for the independent package. Retained from the product
#: controlled-pilot line; the independent wheel only keeps it if its own build
#: and clean-install gates pass (see docs/release material). NOT a production
#: certification.
RELEASE_CLASSIFICATION = "PACKAGE_READY_FOR_CONTROLLED_PILOT"

# Optional integration extras this distribution declares, mapped to the module
# that must be importable for the integration to be usable. version_info() probes
# availability at runtime. The core identity provider, in-memory persistence,
# and neutral authorization ports are always present (they live in the core wheel
# / its governance-kernel dependency), so they are NOT listed here.
#
# Compatibility note: the ``tap_legacy`` / ``actiongate_legacy`` KEY NAMES are
# retained unchanged so the version-info schema does not break for existing
# consumers, but the probed MODULES are now the CANONICAL provider namespaces
# (``ugence_tap_provider`` / ``ugence_actiongate_provider``). A later minor release
# may normalize the public key names; this patch release keeps them additive-safe.
_OPTIONAL_INTEGRATIONS = {
    "api": "fastapi",
    # Optional canonical control-plane adapters (dependency-injected peers).
    "tap_legacy": "ugence_tap_provider",
    "actiongate_legacy": "ugence_actiongate_provider",
}

# Runtime dependencies whose versions we surface for provenance/debugging.
_TRACKED_DEPENDENCIES = (
    "pydantic",
    "ugence-decision-authority",
    "ugence-governance-provider-framework",
    "ugence-governance-contracts",
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
    product_version: str
    platform_baseline: str
    stability: str
    release_classification: str
    production_certified: bool
    contract_versions: dict = field(default_factory=dict)
    dependency_versions: dict = field(default_factory=dict)
    optional_integrations: dict = field(default_factory=dict)
    build_commit: str | None = None

    def to_dict(self) -> dict:
        return {
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
            "product_version": self.product_version,
            "platform_baseline": self.platform_baseline,
            "stability": self.stability,
            "release_classification": self.release_classification,
            "production_certified": self.production_certified,
            "contract_versions": dict(self.contract_versions),
            "dependency_versions": dict(self.dependency_versions),
            "optional_integrations": dict(self.optional_integrations),
            "build_commit": self.build_commit,
        }


def version_info() -> VersionInfo:
    """Return structured distribution + product version metadata.

    ``production_certified`` is hard-coded ``False``. ``contract_versions`` and
    ``dependency_versions`` are best-effort resolved from installed distribution
    metadata; ``optional_integrations`` reports whether each optional integration
    is importable in the current environment.
    """
    deps = {name: _dist_version(name) for name in _TRACKED_DEPENDENCIES}
    contracts = {
        "decision_authority": deps.get("ugence-decision-authority"),
        "governance_provider_framework": deps.get("ugence-governance-provider-framework"),
        "governance_contracts": deps.get("ugence-governance-contracts"),
    }
    integrations = {
        name: _module_available(module)
        for name, module in _OPTIONAL_INTEGRATIONS.items()
    }
    return VersionInfo(
        distribution=DISTRIBUTION_NAME,
        distribution_version=DISTRIBUTION_VERSION,
        product_version=PRODUCT_VERSION,
        platform_baseline=PLATFORM_BASELINE,
        stability=STABILITY,
        release_classification=RELEASE_CLASSIFICATION,
        production_certified=False,
        contract_versions=contracts,
        dependency_versions=deps,
        optional_integrations=integrations,
        build_commit=None,  # not embedded in the wheel; set by release tooling when available
    )


__all__ = [
    "DISTRIBUTION_VERSION",
    "DISTRIBUTION_NAME",
    "PRODUCT_VERSION",
    "PLATFORM_BASELINE",
    "STABILITY",
    "RELEASE_CLASSIFICATION",
    "VersionInfo",
    "version_info",
]
