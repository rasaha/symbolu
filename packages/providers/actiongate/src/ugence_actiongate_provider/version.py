"""ActionGate provider version, compatibility declarations, and version metadata.

Five version concepts are kept explicit and separate:

* :data:`__version__` — the **ActionGate provider implementation** version (unchanged
  by the package relocation: the code did not change, only its location did).
* :data:`DISTRIBUTION_VERSION` — the **canonical distribution**
  (``ugence-actiongate-provider``) packaging-lifecycle version.
* :data:`CONTRACT_VERSION` — the ``ActionGovernanceProvider`` contract version.
* the **mapping version** (``actiongate-map-1``) — reported by :func:`version_info`.
* :data:`TARGET_FRAMEWORK_VERSION` — the provider-framework version targeted.

The implementation and initial canonical distribution both start at ``0.1.0``. A
path migration does NOT bump the implementation version.
"""
from __future__ import annotations

import importlib.metadata as _md
from dataclasses import dataclass, field

#: ActionGate provider **implementation** version. Not changed by relocation.
__version__ = "0.1.0"
VERSION = __version__

#: Canonical **distribution** version (``ugence-actiongate-provider`` on the index).
DISTRIBUTION_VERSION = "0.1.0"
#: Canonical distribution name.
DISTRIBUTION_NAME = "ugence-actiongate-provider"

#: The DGM kernel version this provider is built against.
TARGET_KERNEL_VERSION = "1.0.0"
#: The provider-framework version this provider targets.
TARGET_FRAMEWORK_VERSION = "0.1.0"
#: The ActionGovernanceProvider contract version implemented.
CONTRACT_VERSION = "1.0.0"

# Runtime dependencies whose installed versions we surface for provenance.
_TRACKED_DEPENDENCIES = (
    "ugence-governance-provider-framework",
    "ugence-governance-contracts",
    "ugence-decision-authority",
)


def _dist_version(name: str) -> str | None:
    try:
        return _md.version(name)
    except Exception:  # pragma: no cover - best effort in a source checkout
        return None


@dataclass(frozen=True)
class VersionInfo:
    """Structured version + provenance metadata for the ActionGate distribution."""

    distribution: str
    distribution_version: str
    implementation_version: str
    mapping_version: str
    contract_version: str
    target_framework_version: str
    compatible_kernel_majors: tuple[str, ...]
    production_certified: bool
    dependency_versions: dict = field(default_factory=dict)
    build_commit: str | None = None

    def to_dict(self) -> dict:
        return {
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
            "implementation_version": self.implementation_version,
            "mapping_version": self.mapping_version,
            "contract_version": self.contract_version,
            "target_framework_version": self.target_framework_version,
            "compatible_kernel_majors": list(self.compatible_kernel_majors),
            "production_certified": self.production_certified,
            "dependency_versions": dict(self.dependency_versions),
            "build_commit": self.build_commit,
        }


def version_info() -> VersionInfo:
    """Return structured distribution + implementation version metadata.

    ``production_certified`` is hard-coded ``False``: packaging verification is not a
    production certification, and no frozen ActionGate contract asserts otherwise.
    ``dependency_versions`` is best-effort resolved from installed distribution
    metadata (``None`` for each in a bare source checkout).
    """
    # Imported lazily to avoid an import cycle (mapping imports the framework API).
    from .mapping import MAPPING_VERSION

    deps = {name: _dist_version(name) for name in _TRACKED_DEPENDENCIES}
    return VersionInfo(
        distribution=DISTRIBUTION_NAME,
        distribution_version=DISTRIBUTION_VERSION,
        implementation_version=__version__,
        mapping_version=MAPPING_VERSION,
        contract_version=CONTRACT_VERSION,
        target_framework_version=TARGET_FRAMEWORK_VERSION,
        compatible_kernel_majors=(TARGET_KERNEL_VERSION.split(".")[0],),
        production_certified=False,
        dependency_versions=deps,
        build_commit=None,
    )
