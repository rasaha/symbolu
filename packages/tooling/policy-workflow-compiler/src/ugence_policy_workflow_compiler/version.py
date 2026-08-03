"""Distribution + product version and maturity metadata.

Two version concepts are kept separate:

* :data:`DISTRIBUTION_VERSION` — the independent wheel-packaging lifecycle of the
  ``ugence-policy-workflow-compiler`` distribution.
* :data:`PRODUCT_VERSION` — the Policy Workflow Compiler product/capability marker.

:func:`version_info` reports honest maturity booleans. The three
verification booleans (``structured_policy_pack_implemented``,
``deterministic_compilation_verified``,
``procurement_reference_equivalence_verified``) are only ``True`` because their
gates pass in this build's test suite. Document extraction, runtime deployment,
pilot validation, and production certification are all ``False``.
"""

from __future__ import annotations

import importlib
import importlib.metadata as _md
from dataclasses import dataclass, field
from typing import Dict, Optional

DISTRIBUTION_VERSION = "0.1.0"
DISTRIBUTION_NAME = "ugence-policy-workflow-compiler"
PRODUCT_NAME = "Ugence Policy Workflow Compiler"
PRODUCT_VERSION = "0.1.0"
CANONICAL_NAMESPACE = "ugence_policy_workflow_compiler"

#: Optional integrations this distribution can probe for at runtime. The core
#: compiler never imports these; the capability registry resolves capability
#: targets from metadata alone. version_info() reports availability only.
_OPTIONAL_INTEGRATIONS = {
    "procurement-reference": "ugence_procurement",
}

_TRACKED_DEPENDENCIES = ("pydantic",)


def _dist_version(name: str) -> Optional[str]:
    try:
        return _md.version(name)
    except Exception:  # pragma: no cover - best effort
        return None


def _module_available(module: Optional[str]) -> bool:
    if module is None:
        return False
    try:
        importlib.import_module(module)
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class VersionInfo:
    """Structured version + maturity metadata."""

    distribution: str
    distribution_version: str
    product: str
    product_version: str
    canonical_namespace: str
    structured_policy_pack_implemented: bool
    deterministic_compilation_verified: bool
    procurement_reference_equivalence_verified: bool
    document_extraction_implemented: bool
    runtime_deployment_implemented: bool
    pilot_validated: bool
    production_certified: bool
    dependency_versions: Dict[str, Optional[str]] = field(default_factory=dict)
    optional_integrations: Dict[str, bool] = field(default_factory=dict)
    build_commit: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
            "product": self.product,
            "product_version": self.product_version,
            "canonical_namespace": self.canonical_namespace,
            "structured_policy_pack_implemented": self.structured_policy_pack_implemented,
            "deterministic_compilation_verified": self.deterministic_compilation_verified,
            "procurement_reference_equivalence_verified": (
                self.procurement_reference_equivalence_verified
            ),
            "document_extraction_implemented": self.document_extraction_implemented,
            "runtime_deployment_implemented": self.runtime_deployment_implemented,
            "pilot_validated": self.pilot_validated,
            "production_certified": self.production_certified,
            "dependency_versions": dict(self.dependency_versions),
            "optional_integrations": dict(self.optional_integrations),
            "build_commit": self.build_commit,
        }


def version_info() -> VersionInfo:
    """Return structured distribution + product version and maturity metadata.

    The three verification booleans are ``True`` in this build because the
    corresponding gates pass in the shipped test suite. ``document_extraction``,
    ``runtime_deployment``, ``pilot_validated`` and ``production_certified`` are
    hard-coded ``False`` — this package makes no such claim.
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
        structured_policy_pack_implemented=True,
        deterministic_compilation_verified=True,
        procurement_reference_equivalence_verified=True,
        document_extraction_implemented=False,
        runtime_deployment_implemented=False,
        pilot_validated=False,
        production_certified=False,
        dependency_versions=deps,
        optional_integrations=integrations,
        build_commit=None,
    )


__all__ = [
    "DISTRIBUTION_VERSION",
    "DISTRIBUTION_NAME",
    "PRODUCT_NAME",
    "PRODUCT_VERSION",
    "CANONICAL_NAMESPACE",
    "VersionInfo",
    "version_info",
]
