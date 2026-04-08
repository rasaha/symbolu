"""
License Validator
=================

Validates license keys and determines license type.

License Key Format:
    {TYPE}-{XXXX}-{XXXX}-{XXXX}
    where TYPE is:
        - ENT: Enterprise license
        - CON: Consumer license
        - DEV: Development license (full access)

For production, this would integrate with a license server.
Current implementation validates format and extracts type.
"""

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime, timedelta


class LicenseType(Enum):
    """Types of licenses."""
    ENTERPRISE = "enterprise"
    CONSUMER = "consumer"
    DEVELOPMENT = "development"
    INVALID = "invalid"


@dataclass
class LicenseResult:
    """Result of license validation."""
    is_valid: bool
    license_type: LicenseType
    expires_at: Optional[datetime] = None
    customer_id: Optional[str] = None
    features: Optional[list] = None
    error: Optional[str] = None

    def __str__(self) -> str:
        if self.is_valid:
            return f"Valid {self.license_type.value} license"
        return f"Invalid license: {self.error}"


class LicenseValidator:
    """
    Validates license keys.

    For production, this would:
    1. Check against a license server
    2. Verify cryptographic signature
    3. Check expiration dates
    4. Validate customer entitlements

    Current implementation validates format and determines type.

    Usage:
        validator = LicenseValidator()
        result = validator.validate("ENT-ABCD-1234-EFGH")
        if result.is_valid:
            print(f"License type: {result.license_type}")
    """

    # License key pattern: TYPE-XXXX-XXXX-XXXX
    LICENSE_PATTERN = re.compile(
        r'^(ENT|CON|DEV)-([A-Z0-9]{4})-([A-Z0-9]{4})-([A-Z0-9]{4})$',
        re.IGNORECASE
    )

    # Type prefix to LicenseType mapping
    TYPE_MAPPING = {
        "ENT": LicenseType.ENTERPRISE,
        "CON": LicenseType.CONSUMER,
        "DEV": LicenseType.DEVELOPMENT,
    }

    def validate(self, license_key: str) -> LicenseResult:
        """
        Validate a license key.

        Args:
            license_key: The license key to validate

        Returns:
            LicenseResult with validation status and details
        """
        if not license_key:
            return LicenseResult(
                is_valid=False,
                license_type=LicenseType.INVALID,
                error="No license key provided",
            )

        # Clean the key
        key = license_key.strip().upper()

        # Check format
        match = self.LICENSE_PATTERN.match(key)
        if not match:
            return LicenseResult(
                is_valid=False,
                license_type=LicenseType.INVALID,
                error="Invalid license key format",
            )

        # Extract type
        type_prefix = match.group(1).upper()
        license_type = self.TYPE_MAPPING.get(type_prefix, LicenseType.INVALID)

        # Validate checksum (simple validation for now)
        if not self._validate_checksum(key):
            return LicenseResult(
                is_valid=False,
                license_type=LicenseType.INVALID,
                error="Invalid license key checksum",
            )

        # For development licenses, always valid
        if license_type == LicenseType.DEVELOPMENT:
            return LicenseResult(
                is_valid=True,
                license_type=license_type,
                expires_at=datetime.now() + timedelta(days=365),
                customer_id="development",
                features=["all"],
            )

        # For production, would check license server here
        # Current implementation accepts valid format
        return LicenseResult(
            is_valid=True,
            license_type=license_type,
            expires_at=datetime.now() + timedelta(days=365),
            customer_id=self._extract_customer_id(key),
            features=self._get_features_for_type(license_type),
        )

    def _validate_checksum(self, key: str) -> bool:
        """
        Validate license key checksum.

        Simple validation: last 4 chars should be derived from first 12.
        For production, use proper cryptographic signature.
        """
        # For now, accept all properly formatted keys
        # In production, verify against license server
        return True

    def _extract_customer_id(self, key: str) -> str:
        """Extract customer ID from license key."""
        # Simple extraction: hash of key
        return hashlib.md5(key.encode()).hexdigest()[:8]

    def _get_features_for_type(self, license_type: LicenseType) -> list:
        """Get available features for license type."""
        if license_type == LicenseType.ENTERPRISE:
            return [
                "symbolic_providers",
                "audit_logging",
                "compliance_apis",
                "custom_deployment",
                "sla_support",
            ]
        elif license_type == LicenseType.CONSUMER:
            return [
                "learned_providers",
                "basic_apis",
            ]
        elif license_type == LicenseType.DEVELOPMENT:
            return ["all"]
        return []

    def is_enterprise(self, license_key: str) -> bool:
        """Check if license allows enterprise features."""
        result = self.validate(license_key)
        return result.is_valid and result.license_type in [
            LicenseType.ENTERPRISE,
            LicenseType.DEVELOPMENT,
        ]

    def is_consumer(self, license_key: str) -> bool:
        """Check if license allows consumer features."""
        result = self.validate(license_key)
        return result.is_valid and result.license_type in [
            LicenseType.CONSUMER,
            LicenseType.DEVELOPMENT,
        ]


def validate_license(license_key: str) -> LicenseResult:
    """
    Convenience function to validate a license key.

    Args:
        license_key: The license key to validate

    Returns:
        LicenseResult with validation status
    """
    validator = LicenseValidator()
    return validator.validate(license_key)
