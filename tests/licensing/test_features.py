"""Tests for license features."""

import pytest
from symbolu.licensing.features import (
    LicenseFeatures,
    get_available_features,
    require_license,
    LicenseError,
)
from symbolu.licensing.validator import LicenseType


class TestGetAvailableFeatures:
    """Tests for get_available_features function."""

    def test_enterprise_features(self):
        """Enterprise license should have enterprise features."""
        features = get_available_features("ENT-ABCD-1234-EFGH")
        assert features.is_valid is True
        assert features.license_type == LicenseType.ENTERPRISE
        assert features.can_use_enterprise is True
        assert features.can_use_consumer is False
        assert features.can_use_symbolic_providers is True
        assert features.audit_logging_enabled is True

    def test_consumer_features(self):
        """Consumer license should have consumer features."""
        features = get_available_features("CON-ABCD-1234-EFGH")
        assert features.is_valid is True
        assert features.license_type == LicenseType.CONSUMER
        assert features.can_use_enterprise is False
        assert features.can_use_consumer is True
        assert features.can_use_learned_providers is True
        assert features.audit_logging_enabled is False

    def test_development_features(self):
        """Development license should have all features."""
        features = get_available_features("DEV-TEST-ABCD-1234")
        assert features.is_valid is True
        assert features.license_type == LicenseType.DEVELOPMENT
        assert features.can_use_enterprise is True
        assert features.can_use_consumer is True
        assert features.can_use_symbolic_providers is True
        assert features.can_use_learned_providers is True

    def test_invalid_license(self):
        """Invalid license should have no features."""
        features = get_available_features("INVALID")
        assert features.is_valid is False
        assert features.can_use_enterprise is False
        assert features.can_use_consumer is False


class TestLicenseFeatures:
    """Tests for LicenseFeatures class."""

    def test_get_allowed_modes_enterprise(self):
        """Enterprise features should allow only enterprise mode."""
        features = get_available_features("ENT-ABCD-1234-EFGH")
        modes = features.get_allowed_modes()
        assert "enterprise" in modes
        assert "consumer" not in modes

    def test_get_allowed_modes_consumer(self):
        """Consumer features should allow only consumer mode."""
        features = get_available_features("CON-ABCD-1234-EFGH")
        modes = features.get_allowed_modes()
        assert "consumer" in modes
        assert "enterprise" not in modes

    def test_get_allowed_modes_development(self):
        """Development features should allow both modes."""
        features = get_available_features("DEV-TEST-ABCD-1234")
        modes = features.get_allowed_modes()
        assert "enterprise" in modes
        assert "consumer" in modes

    def test_validate_mode_enterprise(self):
        """Should validate enterprise mode access."""
        features = get_available_features("ENT-ABCD-1234-EFGH")
        assert features.validate_mode("enterprise") is True
        assert features.validate_mode("consumer") is False

    def test_validate_mode_consumer(self):
        """Should validate consumer mode access."""
        features = get_available_features("CON-ABCD-1234-EFGH")
        assert features.validate_mode("consumer") is True
        assert features.validate_mode("enterprise") is False


class TestRequireLicense:
    """Tests for require_license function."""

    def test_valid_enterprise_license(self):
        """Should pass for valid enterprise license and mode."""
        features = require_license("ENT-ABCD-1234-EFGH", "enterprise")
        assert features.is_valid is True
        assert features.can_use_enterprise is True

    def test_valid_consumer_license(self):
        """Should pass for valid consumer license and mode."""
        features = require_license("CON-ABCD-1234-EFGH", "consumer")
        assert features.is_valid is True
        assert features.can_use_consumer is True

    def test_invalid_license_raises(self):
        """Should raise for invalid license."""
        with pytest.raises(LicenseError):
            require_license("INVALID", "enterprise")

    def test_wrong_mode_raises(self):
        """Should raise when license doesn't allow mode."""
        with pytest.raises(LicenseError) as exc_info:
            require_license("ENT-ABCD-1234-EFGH", "consumer")
        assert "consumer" in str(exc_info.value).lower()

    def test_development_allows_all(self):
        """Development license should allow any mode."""
        features = require_license("DEV-TEST-ABCD-1234", "enterprise")
        assert features.is_valid is True

        features = require_license("DEV-TEST-ABCD-1234", "consumer")
        assert features.is_valid is True
