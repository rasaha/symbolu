"""Pilot-level ecosystem/compatibility manifest (Task 114).

A pilot-owned manifest asserting the frozen versions the pilot targets. Validated
against the actually-installed distributions before a run. This does **not** modify
the provider framework or registry.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..version import (
    DATASET_VERSION, TARGET_ACTIONGATE_VERSION, TARGET_FRAMEWORK_VERSION,
    TARGET_KERNEL_VERSION, TARGET_TAP_VERSION, __version__)

ECOSYSTEM_MANIFEST: dict = {
    "ecosystem": {
        "kernel": {"distribution": "decision-governance", "version": TARGET_KERNEL_VERSION},
        "framework": {"distribution": "dgm-provider-framework",
                      "version": TARGET_FRAMEWORK_VERSION},
        "providers": {
            "assertion": {"distribution": "dgm-tap-provider", "version": TARGET_TAP_VERSION,
                          "contract": "assertion-governance/1.0"},
            "action": {"distribution": "dgm-actiongate-provider",
                       "version": TARGET_ACTIONGATE_VERSION,
                       "contract": "action-governance/1.0"},
        },
        "pilot": {"distribution": "dgm-enterprise-validation-pilot", "version": __version__,
                  "dataset": DATASET_VERSION},
    }
}


@dataclass(frozen=True)
class ManifestCheck:
    component: str
    expected: str
    actual: str

    @property
    def ok(self) -> bool:
        return self.expected == self.actual


@dataclass(frozen=True)
class ManifestValidation:
    checks: tuple[ManifestCheck, ...]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failures(self) -> tuple[ManifestCheck, ...]:
        return tuple(c for c in self.checks if not c.ok)


def validate_manifest() -> ManifestValidation:
    """Compare manifest versions against installed distributions (public APIs only)."""
    import actiongate_provider
    import decision_governance
    import governance_providers
    import tap_provider

    eco = ECOSYSTEM_MANIFEST["ecosystem"]
    checks = (
        ManifestCheck("decision-governance", eco["kernel"]["version"],
                      decision_governance.__version__),
        ManifestCheck("dgm-provider-framework", eco["framework"]["version"],
                      governance_providers.__version__),
        ManifestCheck("dgm-tap-provider", eco["providers"]["assertion"]["version"],
                      tap_provider.__version__),
        ManifestCheck("dgm-actiongate-provider", eco["providers"]["action"]["version"],
                      actiongate_provider.__version__),
        ManifestCheck("dgm-enterprise-validation-pilot", eco["pilot"]["version"], __version__),
    )
    return ManifestValidation(checks=checks)
