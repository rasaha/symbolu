"""
License Features
================

Controls feature availability based on license type.
"""

from dataclasses import dataclass
from typing import Optional

from symbolu.licensing.validator import (
    LicenseValidator,
    LicenseType,
    validate_license,
)


@dataclass
class LicenseFeatures:
    """
    Available features based on license.

    Enterprise licenses get:
    - Symbolic/phoneme-based providers
    - Full audit logging
    - Compliance APIs
    - Custom deployment options
    - SLA support

    Consumer licenses get:
    - Pre-trained/learned providers
    - Basic APIs
    - Community support

    Development licenses get everything.
    """
    license_type: LicenseType
    is_valid: bool

    # Mode access
    can_use_enterprise: bool = False
    can_use_consumer: bool = False

    # Provider access
    can_use_symbolic_providers: bool = False
    can_use_learned_providers: bool = False

    # Feature flags
    audit_logging_enabled: bool = False
    compliance_apis_enabled: bool = False
    custom_deployment_enabled: bool = False
    sla_support_enabled: bool = False

    def get_allowed_modes(self) -> list:
        """Get list of allowed modes for this license."""
        modes = []
        if self.can_use_enterprise:
            modes.append("enterprise")
        if self.can_use_consumer:
            modes.append("consumer")
        return modes

    def validate_mode(self, mode: str) -> bool:
        """
        Check if a mode is allowed by this license.

        Args:
            mode: The mode to check ("enterprise" or "consumer")

        Returns:
            True if mode is allowed

        Raises:
            ValueError: If mode is not allowed
        """
        if mode == "enterprise" and not self.can_use_enterprise:
            return False
        if mode == "consumer" and not self.can_use_consumer:
            return False
        return True


def get_available_features(license_key: str) -> LicenseFeatures:
    """
    Get available features for a license key.

    Args:
        license_key: The license key to check

    Returns:
        LicenseFeatures object with available features
    """
    result = validate_license(license_key)

    if not result.is_valid:
        return LicenseFeatures(
            license_type=LicenseType.INVALID,
            is_valid=False,
        )

    if result.license_type == LicenseType.ENTERPRISE:
        return LicenseFeatures(
            license_type=LicenseType.ENTERPRISE,
            is_valid=True,
            can_use_enterprise=True,
            can_use_consumer=False,  # Enterprise license = enterprise mode only
            can_use_symbolic_providers=True,
            can_use_learned_providers=False,
            audit_logging_enabled=True,
            compliance_apis_enabled=True,
            custom_deployment_enabled=True,
            sla_support_enabled=True,
        )

    if result.license_type == LicenseType.CONSUMER:
        return LicenseFeatures(
            license_type=LicenseType.CONSUMER,
            is_valid=True,
            can_use_enterprise=False,  # Consumer license = consumer mode only
            can_use_consumer=True,
            can_use_symbolic_providers=False,
            can_use_learned_providers=True,
            audit_logging_enabled=False,
            compliance_apis_enabled=False,
            custom_deployment_enabled=False,
            sla_support_enabled=False,
        )

    if result.license_type == LicenseType.DEVELOPMENT:
        return LicenseFeatures(
            license_type=LicenseType.DEVELOPMENT,
            is_valid=True,
            can_use_enterprise=True,
            can_use_consumer=True,
            can_use_symbolic_providers=True,
            can_use_learned_providers=True,
            audit_logging_enabled=True,
            compliance_apis_enabled=True,
            custom_deployment_enabled=True,
            sla_support_enabled=True,
        )

    # Default: no access
    return LicenseFeatures(
        license_type=LicenseType.INVALID,
        is_valid=False,
    )


class LicenseError(Exception):
    """Raised when license validation fails."""

    def __init__(self, message: str, license_type: Optional[LicenseType] = None):
        super().__init__(message)
        self.license_type = license_type


def require_license(license_key: str, required_mode: str) -> LicenseFeatures:
    """
    Validate license and require specific mode access.

    Args:
        license_key: The license key to validate
        required_mode: The mode that must be allowed ("enterprise" or "consumer")

    Returns:
        LicenseFeatures if valid

    Raises:
        LicenseError: If license is invalid or mode not allowed
    """
    features = get_available_features(license_key)

    if not features.is_valid:
        raise LicenseError(
            f"Invalid license key",
            features.license_type,
        )

    if not features.validate_mode(required_mode):
        raise LicenseError(
            f"License does not allow {required_mode} mode. "
            f"License type: {features.license_type.value}",
            features.license_type,
        )

    return features
