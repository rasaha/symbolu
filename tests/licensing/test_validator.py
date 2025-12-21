"""Tests for license validation."""

import pytest
from symbolu.licensing.validator import (
    LicenseValidator,
    LicenseResult,
    LicenseType,
    validate_license,
)


class TestLicenseValidator:
    """Tests for LicenseValidator."""

    def test_validate_enterprise_license(self):
        """Should validate enterprise license format."""
        validator = LicenseValidator()
        result = validator.validate("ENT-ABCD-1234-EFGH")
        assert result.is_valid is True
        assert result.license_type == LicenseType.ENTERPRISE

    def test_validate_consumer_license(self):
        """Should validate consumer license format."""
        validator = LicenseValidator()
        result = validator.validate("CON-WXYZ-5678-IJKL")
        assert result.is_valid is True
        assert result.license_type == LicenseType.CONSUMER

    def test_validate_development_license(self):
        """Should validate development license format."""
        validator = LicenseValidator()
        result = validator.validate("DEV-TEST-ABCD-1234")
        assert result.is_valid is True
        assert result.license_type == LicenseType.DEVELOPMENT

    def test_invalid_empty_key(self):
        """Should reject empty license key."""
        validator = LicenseValidator()
        result = validator.validate("")
        assert result.is_valid is False
        assert result.license_type == LicenseType.INVALID

    def test_invalid_format(self):
        """Should reject invalid format."""
        validator = LicenseValidator()
        result = validator.validate("INVALID-KEY")
        assert result.is_valid is False
        assert "format" in result.error.lower()

    def test_invalid_prefix(self):
        """Should reject invalid prefix."""
        validator = LicenseValidator()
        result = validator.validate("XXX-ABCD-1234-EFGH")
        assert result.is_valid is False

    def test_case_insensitive(self):
        """Should accept lowercase keys."""
        validator = LicenseValidator()
        result = validator.validate("ent-abcd-1234-efgh")
        assert result.is_valid is True
        assert result.license_type == LicenseType.ENTERPRISE

    def test_strips_whitespace(self):
        """Should strip whitespace from key."""
        validator = LicenseValidator()
        result = validator.validate("  ENT-ABCD-1234-EFGH  ")
        assert result.is_valid is True

    def test_is_enterprise(self):
        """Should correctly identify enterprise licenses."""
        validator = LicenseValidator()
        assert validator.is_enterprise("ENT-ABCD-1234-EFGH") is True
        assert validator.is_enterprise("DEV-ABCD-1234-EFGH") is True  # Dev has all access
        assert validator.is_enterprise("CON-ABCD-1234-EFGH") is False

    def test_is_consumer(self):
        """Should correctly identify consumer licenses."""
        validator = LicenseValidator()
        assert validator.is_consumer("CON-ABCD-1234-EFGH") is True
        assert validator.is_consumer("DEV-ABCD-1234-EFGH") is True  # Dev has all access
        assert validator.is_consumer("ENT-ABCD-1234-EFGH") is False

    def test_enterprise_features(self):
        """Enterprise license should have enterprise features."""
        validator = LicenseValidator()
        result = validator.validate("ENT-ABCD-1234-EFGH")
        assert "symbolic_providers" in result.features
        assert "audit_logging" in result.features
        assert "compliance_apis" in result.features

    def test_consumer_features(self):
        """Consumer license should have consumer features."""
        validator = LicenseValidator()
        result = validator.validate("CON-ABCD-1234-EFGH")
        assert "learned_providers" in result.features
        assert "symbolic_providers" not in result.features


class TestValidateLicenseFunction:
    """Tests for validate_license convenience function."""

    def test_validates_valid_key(self):
        """Should validate valid license key."""
        result = validate_license("ENT-ABCD-1234-EFGH")
        assert result.is_valid is True

    def test_rejects_invalid_key(self):
        """Should reject invalid license key."""
        result = validate_license("INVALID")
        assert result.is_valid is False


class TestLicenseResult:
    """Tests for LicenseResult dataclass."""

    def test_str_valid(self):
        """Should have readable string for valid license."""
        result = LicenseResult(
            is_valid=True,
            license_type=LicenseType.ENTERPRISE,
        )
        assert "Valid" in str(result)
        assert "enterprise" in str(result)

    def test_str_invalid(self):
        """Should have readable string for invalid license."""
        result = LicenseResult(
            is_valid=False,
            license_type=LicenseType.INVALID,
            error="Bad format",
        )
        assert "Invalid" in str(result)
        assert "Bad format" in str(result)
