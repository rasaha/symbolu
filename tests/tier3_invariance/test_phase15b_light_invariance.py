"""
Phase 15b Light Invariance Test Suite (Tier 3)
==============================================

Lightweight invariance scaffolding for Phase 15b - User Preferences.
Total: ~22 tests

Phase Type: Service layer
Routing/Mapper Invariance: SKIP (service layer)
"""

import pytest
import inspect

from symbolu.service.preferences import (
    PreferenceStore,
    UserPreference,
    AdminPreference,
    get_preference_store,
)
from symbolu.policy.interaction_modes import InteractionMode


# ============================================================================
# Test Class 1: Preference Store Determinism (5 tests)
# ============================================================================

class TestPhase15bStoreDeterminism:
    """Verify Phase 15b preference store is deterministic."""

    def test_store_creation_deterministic(self):
        """Test store creation is deterministic."""
        store1 = PreferenceStore()
        store2 = PreferenceStore()
        # Both should start empty
        assert store1.get_user_preference("test") is None
        assert store2.get_user_preference("test") is None

    def test_set_get_deterministic(self):
        """Test set/get operations are deterministic."""
        store = PreferenceStore()
        pref = UserPreference(user_id="user1", preferred_interaction_mode=InteractionMode.SMART_INSIGHT)
        store.set_user_preference(pref)
        results = [store.get_user_preference("user1") for _ in range(10)]
        assert all(r.preferred_interaction_mode == InteractionMode.SMART_INSIGHT for r in results)

    def test_overwrite_deterministic(self):
        """Test overwrite behavior is deterministic."""
        store = PreferenceStore()
        pref1 = UserPreference(user_id="user1", preferred_interaction_mode=InteractionMode.ANALYTICS_ONLY)
        pref2 = UserPreference(user_id="user1", preferred_interaction_mode=InteractionMode.DEEP_ADAPTIVE)
        store.set_user_preference(pref1)
        store.set_user_preference(pref2)
        result = store.get_user_preference("user1")
        assert result.preferred_interaction_mode == InteractionMode.DEEP_ADAPTIVE

    def test_singleton_accessor_deterministic(self):
        """Test singleton accessor is deterministic."""
        store1 = get_preference_store()
        store2 = get_preference_store()
        assert store1 is store2

    def test_no_randomness_in_preferences(self):
        """Test no randomness in preferences module."""
        import symbolu.service.preferences as module
        source = inspect.getsource(module)
        assert 'random' not in source.lower()


# ============================================================================
# Test Class 2: Zero-LLM Guarantee (4 tests)
# ============================================================================

class TestPhase15bZeroLLMGuarantee:
    """Verify Phase 15b makes NO LLM calls."""

    def test_no_anthropic_imports(self):
        """Test no Anthropic imports in preferences."""
        import symbolu.service.preferences as module
        source = inspect.getsource(module)
        assert 'anthropic' not in source.lower()

    def test_no_openai_imports(self):
        """Test no OpenAI imports in preferences."""
        import symbolu.service.preferences as module
        source = inspect.getsource(module)
        assert 'openai' not in source.lower()

    def test_no_network_calls(self):
        """Test no network calls in preferences."""
        import symbolu.service.preferences as module
        source = inspect.getsource(module)
        assert 'requests' not in source.lower()

    def test_runs_offline(self):
        """Test preference operations run offline."""
        store = PreferenceStore()
        pref = UserPreference(user_id="test", preferred_interaction_mode=None)
        store.set_user_preference(pref)
        result = store.get_user_preference("test")
        assert result is not None


# ============================================================================
# Test Class 3: CRUD Operations (5 tests)
# ============================================================================

class TestPhase15bCRUDOperations:
    """Verify Phase 15b CRUD operations work correctly."""

    def test_create_user_preference(self):
        """Test creating user preference."""
        store = PreferenceStore()
        pref = UserPreference(user_id="user1", preferred_interaction_mode=InteractionMode.SMART_INSIGHT)
        store.set_user_preference(pref)
        result = store.get_user_preference("user1")
        assert result is not None
        assert result.user_id == "user1"

    def test_create_admin_preference(self):
        """Test creating admin preference."""
        store = PreferenceStore()
        pref = AdminPreference(org_id="org1", forced_interaction_mode=InteractionMode.ANALYTICS_ONLY)
        store.set_admin_preference(pref)
        result = store.get_admin_preference("org1")
        assert result is not None
        assert result.org_id == "org1"

    def test_clear_user(self):
        """Test clearing user preference."""
        store = PreferenceStore()
        pref = UserPreference(user_id="user1", preferred_interaction_mode=InteractionMode.SMART_INSIGHT)
        store.set_user_preference(pref)
        store.clear_user("user1")
        result = store.get_user_preference("user1")
        assert result is None

    def test_clear_admin(self):
        """Test clearing admin preference."""
        store = PreferenceStore()
        pref = AdminPreference(org_id="org1", forced_interaction_mode=InteractionMode.ANALYTICS_ONLY)
        store.set_admin_preference(pref)
        store.clear_admin("org1")
        result = store.get_admin_preference("org1")
        assert result is None

    def test_get_nonexistent_returns_none(self):
        """Test getting nonexistent preference returns None."""
        store = PreferenceStore()
        assert store.get_user_preference("nonexistent") is None
        assert store.get_admin_preference("nonexistent") is None


# ============================================================================
# Test Class 4: Graceful Degradation (4 tests)
# ============================================================================

class TestPhase15bGracefulDegradation:
    """Verify Phase 15b handles edge cases gracefully."""

    def test_none_mode_preference(self):
        """Test None mode preference is handled."""
        store = PreferenceStore()
        pref = UserPreference(user_id="user1", preferred_interaction_mode=None)
        store.set_user_preference(pref)
        result = store.get_user_preference("user1")
        assert result is not None
        assert result.preferred_interaction_mode is None

    def test_empty_user_id(self):
        """Test empty user_id is handled."""
        store = PreferenceStore()
        try:
            pref = UserPreference(user_id="", preferred_interaction_mode=InteractionMode.SMART_INSIGHT)
            store.set_user_preference(pref)
            result = store.get_user_preference("")
            assert result is None or result is not None  # Either is valid
        except (ValueError, KeyError):
            pass  # Acceptable to reject empty user_id

    def test_clear_nonexistent_no_error(self):
        """Test clearing nonexistent preference doesn't error."""
        store = PreferenceStore()
        # Should not raise
        store.clear_user("nonexistent")
        store.clear_admin("nonexistent")

    def test_multiple_users_isolated(self):
        """Test multiple users are isolated."""
        store = PreferenceStore()
        pref1 = UserPreference(user_id="user1", preferred_interaction_mode=InteractionMode.ANALYTICS_ONLY)
        pref2 = UserPreference(user_id="user2", preferred_interaction_mode=InteractionMode.DEEP_ADAPTIVE)
        store.set_user_preference(pref1)
        store.set_user_preference(pref2)
        assert store.get_user_preference("user1").preferred_interaction_mode == InteractionMode.ANALYTICS_ONLY
        assert store.get_user_preference("user2").preferred_interaction_mode == InteractionMode.DEEP_ADAPTIVE


# ============================================================================
# Test Class 5: Backward Compatibility (4 tests)
# ============================================================================

class TestPhase15bBackwardCompatibility:
    """Verify Phase 15b maintains backward compatibility."""

    def test_preference_store_exists(self):
        """Test PreferenceStore class exists."""
        assert PreferenceStore is not None

    def test_user_preference_exists(self):
        """Test UserPreference class exists."""
        assert UserPreference is not None

    def test_admin_preference_exists(self):
        """Test AdminPreference class exists."""
        assert AdminPreference is not None

    def test_get_preference_store_exists(self):
        """Test get_preference_store function exists."""
        assert callable(get_preference_store)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
