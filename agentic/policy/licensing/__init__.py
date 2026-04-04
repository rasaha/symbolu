"""
License governance integration for the agentic layer.

STATUS: PROVISIONAL (Policy Phase P0)

    This module has ZERO runtime consumers as of Policy Phase P0.
    No governance feature is currently license-gated. The canonical
    licensing implementation lives in symbolu_core.licensing and is
    not referenced through this facade anywhere in the codebase.

    This facade will be promoted when license-gated governance
    features (audit logging tiers, compliance API access) are
    implemented, or deprecated if license checks are kept in
    symbolu_core exclusively.

    Do not add new logic here. Do not assume this module is active.

Re-exports from symbolu_core.licensing — controls whether governance
features are available per license tier.
"""

# Facade status marker — checked by tests and audit tooling
_FACADE_STATUS = "provisional"

from symbolu_core.licensing.validator import (
    LicenseValidator,
    LicenseType,
    LicenseResult,
    validate_license,
)
from symbolu_core.licensing.features import (
    LicenseFeatures,
    LicenseError,
    get_available_features,
    require_license,
)

__all__ = [
    "LicenseValidator",
    "LicenseType",
    "LicenseResult",
    "validate_license",
    "LicenseFeatures",
    "LicenseError",
    "get_available_features",
    "require_license",
    "_FACADE_STATUS",
]
