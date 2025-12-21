"""
Symbol-U Licensing
==================

License validation and feature control for Symbol-U.

License Types:
- Enterprise (ENT-): Full symbolic providers, audit logging, compliance APIs
- Consumer (CON-): Learned providers only, simpler APIs
- Development (DEV-): Full access for development/testing

Usage:
    from symbolu.licensing import validate_license, get_available_features

    # Validate a license key
    result = validate_license("ENT-XXXX-XXXX-XXXX")
    if result.is_valid:
        print(f"License type: {result.license_type}")

    # Get available features
    features = get_available_features("ENT-XXXX-XXXX-XXXX")
    if features.can_use_enterprise:
        # Use enterprise providers
        pass
"""

from symbolu.licensing.validator import (
    LicenseValidator,
    LicenseResult,
    LicenseType,
    validate_license,
)
from symbolu.licensing.features import (
    LicenseFeatures,
    get_available_features,
)

__all__ = [
    "LicenseValidator",
    "LicenseResult",
    "LicenseType",
    "validate_license",
    "LicenseFeatures",
    "get_available_features",
]
