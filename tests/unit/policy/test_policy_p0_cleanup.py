"""
Tests for Policy P0-cleanup — facade truthfulness cleanup.

Validates:
    - The 3 dormant facades are NOT in agentic.policy.__all__
    - The dormant facades still expose _FACADE_STATUS == "dormant"
    - Live policy modules still work unchanged
    - agentic.policy package-level imports continue to work
"""

from __future__ import annotations

import unittest


class TestDormantFacadesExcludedFromPublicAPI(unittest.TestCase):
    """The 3 dormant facades must NOT be part of agentic.policy public API."""

    def test_governance_binding_symbols_not_in_all(self):
        import agentic.policy as policy
        # P53 re-exports must NOT leak into the policy package surface
        for name in (
            "GovernanceBindingEnvelope",
            "GovernanceResponseValidationError",
            "validate_governance_response_structure",
            "bind_governance_response",
        ):
            self.assertNotIn(name, policy.__all__)

    def test_preferences_symbols_not_in_all(self):
        import agentic.policy as policy
        for name in (
            "UserPreference",
            "AdminPreference",
            "PreferenceStore",
            "get_preference_store",
        ):
            self.assertNotIn(name, policy.__all__)

    def test_licensing_symbols_not_in_all(self):
        import agentic.policy as policy
        for name in (
            "LicenseValidator",
            "LicenseType",
            "LicenseResult",
            "validate_license",
            "LicenseFeatures",
            "LicenseError",
            "get_available_features",
            "require_license",
        ):
            self.assertNotIn(name, policy.__all__)

    def test_facade_module_names_not_in_all(self):
        import agentic.policy as policy
        self.assertNotIn("governance_binding", policy.__all__)
        self.assertNotIn("preferences", policy.__all__)
        self.assertNotIn("licensing", policy.__all__)


class TestDormantFacadeStatusMarkers(unittest.TestCase):
    """Dormant facades still expose the expected _FACADE_STATUS marker."""

    def test_governance_binding_status_dormant(self):
        from agentic.policy.governance_binding import _FACADE_STATUS
        self.assertEqual(_FACADE_STATUS, "dormant")

    def test_preferences_status_dormant(self):
        from agentic.policy.preferences import _FACADE_STATUS
        self.assertEqual(_FACADE_STATUS, "dormant")

    def test_licensing_status_dormant(self):
        from agentic.policy.licensing import _FACADE_STATUS
        self.assertEqual(_FACADE_STATUS, "dormant")


class TestDormantFacadesStillImportable(unittest.TestCase):
    """Dormant facades remain on disk and importable (deprecate-in-place)."""

    def test_governance_binding_importable(self):
        from agentic.policy import governance_binding
        self.assertTrue(hasattr(governance_binding, "GovernanceBindingEnvelope"))
        self.assertTrue(hasattr(governance_binding, "bind_governance_response"))

    def test_preferences_importable(self):
        from agentic.policy import preferences
        self.assertTrue(hasattr(preferences, "UserPreference"))
        self.assertTrue(hasattr(preferences, "PreferenceStore"))

    def test_licensing_importable(self):
        from agentic.policy import licensing
        self.assertTrue(hasattr(licensing, "LicenseValidator"))
        self.assertTrue(hasattr(licensing, "validate_license"))


class TestLivePolicyPublicAPIIntact(unittest.TestCase):
    """Live policy modules must remain fully functional."""

    def test_live_public_api_importable_from_package(self):
        from agentic.policy import (
            get_domain_profile,
            compute_policy_flags,
            InteractionMode,
            resolve_interaction_mode,
            DomainProfile,
            ProfileRegistry,
            get_profile_registry,
            PolicyService,
            get_policy_service,
            SessionPolicyFlags,
            TradingGuardrailFlags,
            simulate_policy,
            compare_policy,
            ProfileStatus,
            PolicyLifecycleManager,
            PolicyControlPlane,
        )
        # Basic sanity: each is not None
        self.assertIsNotNone(get_domain_profile)
        self.assertIsNotNone(compute_policy_flags)
        self.assertIsNotNone(InteractionMode)
        self.assertIsNotNone(resolve_interaction_mode)
        self.assertIsNotNone(DomainProfile)
        self.assertIsNotNone(ProfileRegistry)
        self.assertIsNotNone(get_profile_registry)
        self.assertIsNotNone(PolicyService)
        self.assertIsNotNone(get_policy_service)
        self.assertIsNotNone(SessionPolicyFlags)
        self.assertIsNotNone(TradingGuardrailFlags)
        self.assertIsNotNone(simulate_policy)
        self.assertIsNotNone(compare_policy)
        self.assertIsNotNone(ProfileStatus)
        self.assertIsNotNone(PolicyLifecycleManager)
        self.assertIsNotNone(PolicyControlPlane)

    def test_live_module_count_in_all(self):
        """__all__ must still contain all live phases' public symbols."""
        import agentic.policy as policy
        # Phase P0 / P1 / P2 / P3 / P4 core symbols
        required = {
            "get_domain_profile",
            "compute_policy_flags",
            "InteractionMode",
            "DomainProfile",
            "ProfileRegistry",
            "PolicyService",
            "SessionPolicyFlags",
            "TradingGuardrailFlags",
            "simulate_policy",
            "PolicyLifecycleManager",
            "PolicyControlPlane",
        }
        self.assertTrue(required.issubset(set(policy.__all__)))


if __name__ == "__main__":
    unittest.main()
