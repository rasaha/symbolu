"""
License governance integration — Dormant facade.

STATUS: DORMANT (Policy P0-cleanup, 2026-04)

    This facade has ZERO runtime consumers anywhere in the codebase.
    No governance feature is currently license-gated, and the canonical
    licensing implementation in ``symbolu_core.licensing`` is not
    referenced through this facade anywhere.

    This module is retained on disk as a reserved import path for
    future use. It is deliberately excluded from the ``agentic.policy``
    public API (``__init__.py`` / ``__all__``).

    Do NOT add logic here.
    Do NOT import from here in new code.
    Use the canonical licensing source directly:
        ``from symbolu_core.licensing...``

    This facade will either be promoted to active status (when
    license-gated governance features are implemented) or deleted
    entirely in a future cleanup phase.

Re-exports from symbolu_core.licensing — controls whether governance
features are available per license tier.
"""

# Facade status marker — checked by tests and audit tooling.
# Values: "dormant" (zero consumers, kept for reference) |
#         "provisional" (pre-cleanup) | "active" (real consumers)
_FACADE_STATUS = "dormant"

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
