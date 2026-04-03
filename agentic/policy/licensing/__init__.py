"""
License governance integration for the agentic layer.

Copied from symbolu_core.licensing — these modules control whether
governance features (audit logging, compliance APIs) are available
per license tier. The agentic layer needs direct access to:

  - LicenseFeatures.audit_logging_enabled
  - LicenseFeatures.compliance_apis_enabled
  - require_license() enforcement gate

The canonical implementation lives in symbolu_core.licensing.
This copy exists so the governance layer can check license constraints
without a cross-boundary import at runtime.
"""

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
]
