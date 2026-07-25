"""Platform freeze tooling — version.

This is repository/release tooling, NOT a runtime platform dependency. It is
versioned independently of the frozen platform it verifies.
"""
from __future__ import annotations

__version__ = "0.1.0"
VERSION = __version__

#: The platform version this tooling freezes/verifies.
PLATFORM_VERSION = "1.0.0"
#: The commit the platform was frozen at (Phase 6B completion).
FREEZE_COMMIT = "5ae4f70"
BASELINE_TESTS = 1006

#: The four core runtime trees frozen as Platform v1.0.
CORE_TREES = ("decision_governance", "governance_providers",
              "actiongate_provider", "tap_provider")
#: Architectural behaviour frozen (validation harnesses, not core product).
BEHAVIOUR_TREES = ("enterprise_validation_pilot", "comparative_governance_benchmark",
                   "provider_heterogeneity_validation")
#: The four public API surfaces snapshotted for compatibility.
PUBLIC_API_MODULES = ("decision_governance.api", "governance_providers.api",
                      "actiongate_provider.api", "tap_provider.api")

COMPONENT_VERSIONS = {
    "decision-governance": "1.0.0",
    "dgm-provider-framework": "0.1.0",
    "dgm-actiongate-provider": "0.1.0",
    "dgm-tap-provider": "0.1.0",
}
