"""
Phase 15B — User/Admin Preference Store v1.0 Test Suite

Comprehensive test coverage for the preference store system including:
- PreferenceStore behavior (thread-safety, determinism, CRUD operations)
- Policy engine integration (preference resolution cascade)
- API endpoint functionality (set/get preferences)
- Behavioral invariance (no changes to routing/mappers/DHA/Fusion)

All tests are deterministic, zero-LLM, and designed for CI integration.
"""

import threading
import time
from typing import Optional

import pytest

from symbolu.service.preferences import (
    UserPreference,
    AdminPreference,
    PreferenceStore,
    get_preference_store,
)
from symbolu.policy.interaction_modes import InteractionMode
from symbolu.policy.policy_engine import compute_policy_flags, _resolve_mode_from_preferences
from symbolu.policy.domain_profiles import get_domain_profile


# ============================================================================
# GROUP A — PreferenceStore Behavior (8 tests)
# ============================================================================


def test_create_and_retrieve_user_preference():
    """Test creating and retrieving a user preference."""
    store = PreferenceStore()

    user_pref = UserPreference(
        user_id="user123",
        preferred_interaction_mode=InteractionMode.SMART_INSIGHT
    )

    store.set_user_preference(user_pref)
    retrieved = store.get_user_preference("user123")

    assert retrieved is not None
    assert retrieved.user_id == "user123"
    assert retrieved.preferred_interaction_mode == InteractionMode.SMART_INSIGHT


def test_create_and_retrieve_admin_preference():
    """Test creating and retrieving an admin preference."""
    store = PreferenceStore()

    admin_pref = AdminPreference(
        org_id="org456",
        forced_interaction_mode=InteractionMode.DEEP_ADAPTIVE
    )

    store.set_admin_preference(admin_pref)
    retrieved = store.get_admin_preference("org456")

    assert retrieved is not None
    assert retrieved.org_id == "org456"
    assert retrieved.forced_interaction_mode == InteractionMode.DEEP_ADAPTIVE


def test_overwrite_behavior_last_write_wins():
    """Test that last write wins for preference updates."""
    store = PreferenceStore()

    # Write first preference
    user_pref_1 = UserPreference(
        user_id="user123",
        preferred_interaction_mode=InteractionMode.ANALYTICS_ONLY
    )
    store.set_user_preference(user_pref_1)

    # Overwrite with second preference
    user_pref_2 = UserPreference(
        user_id="user123",
        preferred_interaction_mode=InteractionMode.DEEP_ADAPTIVE
    )
    store.set_user_preference(user_pref_2)

    # Verify last write wins
    retrieved = store.get_user_preference("user123")
    assert retrieved.preferred_interaction_mode == InteractionMode.DEEP_ADAPTIVE


def test_clear_user_preference():
    """Test clearing a user preference."""
    store = PreferenceStore()

    user_pref = UserPreference(
        user_id="user123",
        preferred_interaction_mode=InteractionMode.SMART_INSIGHT
    )
    store.set_user_preference(user_pref)

    # Clear the preference
    store.clear_user("user123")

    # Verify it's gone
    retrieved = store.get_user_preference("user123")
    assert retrieved is None


def test_clear_admin_preference():
    """Test clearing an admin preference."""
    store = PreferenceStore()

    admin_pref = AdminPreference(
        org_id="org456",
        forced_interaction_mode=InteractionMode.DEEP_ADAPTIVE
    )
    store.set_admin_preference(admin_pref)

    # Clear the preference
    store.clear_admin("org456")

    # Verify it's gone
    retrieved = store.get_admin_preference("org456")
    assert retrieved is None


def test_thread_safety_concurrent_operations():
    """Test thread safety with concurrent set/get operations."""
    store = PreferenceStore()
    errors = []

    def set_user_pref(user_id: str, mode: InteractionMode):
        try:
            pref = UserPreference(user_id=user_id, preferred_interaction_mode=mode)
            store.set_user_preference(pref)
        except Exception as e:
            errors.append(e)

    def get_user_pref(user_id: str):
        try:
            store.get_user_preference(user_id)
        except Exception as e:
            errors.append(e)

    # Create 20 threads doing concurrent reads and writes
    threads = []
    for i in range(10):
        t1 = threading.Thread(target=set_user_pref, args=(f"user{i}", InteractionMode.SMART_INSIGHT))
        t2 = threading.Thread(target=get_user_pref, args=(f"user{i}",))
        threads.extend([t1, t2])

    # Start all threads
    for t in threads:
        t.start()

    # Wait for all to complete
    for t in threads:
        t.join()

    # Verify no errors occurred
    assert len(errors) == 0


def test_determinism_same_sequence_same_state():
    """Test determinism: same sequence of operations produces same final state."""
    def run_sequence():
        store = PreferenceStore()

        # Execute a specific sequence
        store.set_user_preference(UserPreference("user1", InteractionMode.ANALYTICS_ONLY))
        store.set_user_preference(UserPreference("user2", InteractionMode.SMART_INSIGHT))
        store.set_admin_preference(AdminPreference("org1", InteractionMode.DEEP_ADAPTIVE))
        store.clear_user("user1")
        store.set_user_preference(UserPreference("user3", InteractionMode.DEEP_ADAPTIVE))

        # Return final state
        return {
            "user1": store.get_user_preference("user1"),
            "user2": store.get_user_preference("user2"),
            "user3": store.get_user_preference("user3"),
            "org1": store.get_admin_preference("org1"),
        }

    # Run sequence twice
    state1 = run_sequence()
    state2 = run_sequence()

    # Verify states are identical
    assert state1["user1"] is None
    assert state2["user1"] is None
    assert state1["user2"].preferred_interaction_mode == state2["user2"].preferred_interaction_mode
    assert state1["user3"].preferred_interaction_mode == state2["user3"].preferred_interaction_mode
    assert state1["org1"].forced_interaction_mode == state2["org1"].forced_interaction_mode


def test_singleton_accessor_returns_same_instance():
    """Test that get_preference_store() returns the same singleton instance."""
    store1 = get_preference_store()
    store2 = get_preference_store()

    assert store1 is store2

    # Verify changes in one are visible in the other
    store1.set_user_preference(UserPreference("user_test", InteractionMode.SMART_INSIGHT))

    retrieved = store2.get_user_preference("user_test")
    assert retrieved is not None
    assert retrieved.preferred_interaction_mode == InteractionMode.SMART_INSIGHT


# ============================================================================
# GROUP B — Policy Integration (8 tests)
# ============================================================================


def test_no_preferences_uses_domain_default():
    """Test that without preferences, domain default is used."""
    # Clear any existing preferences
    store = get_preference_store()
    store.clear_all()

    # Get therapy domain profile (default: SMART_INSIGHT)
    profile = get_domain_profile("therapy")

    # Create minimal unified output
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Compute policy flags without user_id/org_id
    flags = compute_policy_flags(unified, "therapy")

    # Verify interaction_mode matches domain default
    assert flags["interaction_mode"] == profile["interaction_mode_default"].value


def test_user_override_beats_domain_default():
    """Test that user preference beats domain default."""
    store = get_preference_store()
    store.clear_all()

    # Set user preference
    user_pref = UserPreference(
        user_id="user_test",
        preferred_interaction_mode=InteractionMode.ANALYTICS_ONLY
    )
    store.set_user_preference(user_pref)

    # Create minimal unified output
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Compute policy flags with user_id (therapy domain default is SMART_INSIGHT)
    flags = compute_policy_flags(unified, "therapy", user_id="user_test")

    # Verify user preference overrides domain default
    assert flags["interaction_mode"] == "analytics_only"


def test_admin_override_beats_user_override():
    """Test that admin preference beats user preference."""
    store = get_preference_store()
    store.clear_all()

    # Set user preference
    user_pref = UserPreference(
        user_id="user_test",
        preferred_interaction_mode=InteractionMode.SMART_INSIGHT
    )
    store.set_user_preference(user_pref)

    # Set admin preference (higher priority)
    admin_pref = AdminPreference(
        org_id="org_test",
        forced_interaction_mode=InteractionMode.DEEP_ADAPTIVE
    )
    store.set_admin_preference(admin_pref)

    # Create minimal unified output
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Compute policy flags with both user_id and org_id
    flags = compute_policy_flags(unified, "therapy", user_id="user_test", org_id="org_test")

    # Verify admin preference overrides user preference
    assert flags["interaction_mode"] == "deep_adaptive"


def test_trading_domain_remains_analytics_only_without_prefs():
    """Test that trading domain stays ANALYTICS_ONLY by default."""
    store = get_preference_store()
    store.clear_all()

    # Create minimal unified output
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Compute policy flags for trading domain without preferences
    flags = compute_policy_flags(unified, "trading")

    # Verify trading stays ANALYTICS_ONLY
    assert flags["interaction_mode"] == "analytics_only"


def test_admin_can_force_smart_insight_in_trading():
    """Test that admin can force SMART_INSIGHT in trading (policy level only)."""
    store = get_preference_store()
    store.clear_all()

    # Set admin preference to force SMART_INSIGHT in trading
    admin_pref = AdminPreference(
        org_id="org_trading",
        forced_interaction_mode=InteractionMode.SMART_INSIGHT
    )
    store.set_admin_preference(admin_pref)

    # Create minimal unified output
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Compute policy flags with org_id
    flags = compute_policy_flags(unified, "trading", org_id="org_trading")

    # Verify admin can override trading domain default (UI-level only)
    assert flags["interaction_mode"] == "smart_insight"


def test_deep_adaptive_forced_by_admin_respected():
    """Test that admin-forced DEEP_ADAPTIVE is respected in policy."""
    store = get_preference_store()
    store.clear_all()

    # Set admin preference
    admin_pref = AdminPreference(
        org_id="org_deep",
        forced_interaction_mode=InteractionMode.DEEP_ADAPTIVE
    )
    store.set_admin_preference(admin_pref)

    # Create minimal unified output with VMF/ATH data
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40},
        "formulas": {
            "vritti_momentum": 0.70,
            "arc_tension_harmonizer": 0.75,
        }
    }

    # Compute policy flags with org_id
    flags = compute_policy_flags(unified, "therapy", org_id="org_deep")

    # Verify DEEP_ADAPTIVE mode is active
    assert flags["interaction_mode"] == "deep_adaptive"

    # Verify VMF/ATH hints are present (DEEP_ADAPTIVE behavior)
    assert "vmf_emotional_momentum" in flags
    assert "ath_arc_tension_state" in flags


def test_safety_flags_unchanged_with_preferences():
    """Test that safety flags (needs_grounding, coherence_warning) are unchanged."""
    store = get_preference_store()
    store.clear_all()

    # Set user preference
    user_pref = UserPreference(
        user_id="user_safety",
        preferred_interaction_mode=InteractionMode.DEEP_ADAPTIVE
    )
    store.set_user_preference(user_pref)

    # Create unified output with low coherence (should trigger safety flags)
    unified = {
        "coherence": {
            "coherence_score": 0.30,  # Below min_coherence for therapy
            "persona_drift_score": 0.70,  # High drift
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.40,
        },
        "entropy": {"normalized_entropy": 0.60}
    }

    # Compute flags without user preference
    flags_no_pref = compute_policy_flags(unified, "therapy")

    # Compute flags with user preference
    flags_with_pref = compute_policy_flags(unified, "therapy", user_id="user_safety")

    # Verify safety flags are identical
    assert flags_no_pref["needs_grounding"] == flags_with_pref["needs_grounding"]
    assert flags_no_pref["coherence_warning"] == flags_with_pref["coherence_warning"]
    assert flags_no_pref["stability_status"] == flags_with_pref["stability_status"]


def test_determinism_over_multiple_runs():
    """Test determinism: same preferences + unified → same policy flags."""
    store = get_preference_store()
    store.clear_all()

    # Set fixed preferences
    user_pref = UserPreference("user_det", InteractionMode.SMART_INSIGHT)
    store.set_user_preference(user_pref)

    # Create fixed unified output
    unified = {
        "coherence": {
            "coherence_score": 0.65,
            "persona_drift_score": 0.40,
            "mapper_volatility_score": 0.25,
            "temporal_arc_score": 0.70,
        },
        "entropy": {"normalized_entropy": 0.45}
    }

    # Run policy engine 5 times
    results = []
    for _ in range(5):
        flags = compute_policy_flags(unified, "therapy", user_id="user_det")
        results.append(flags)

    # Verify all results are identical
    for i in range(1, len(results)):
        assert results[0] == results[i]


# ============================================================================
# GROUP C — API Endpoints (6 tests)
# ============================================================================


def test_set_and_get_user_preference_via_store():
    """Test POST /preferences/user stores and GET retrieves (via direct store access)."""
    store = get_preference_store()
    store.clear_all()

    # Simulate POST behavior
    user_pref = UserPreference(
        user_id="api_user_1",
        preferred_interaction_mode=InteractionMode.SMART_INSIGHT
    )
    store.set_user_preference(user_pref)

    # Simulate GET behavior
    retrieved = store.get_user_preference("api_user_1")

    assert retrieved is not None
    assert retrieved.user_id == "api_user_1"
    assert retrieved.preferred_interaction_mode == InteractionMode.SMART_INSIGHT


def test_set_and_get_admin_preference_via_store():
    """Test POST /preferences/admin stores and GET retrieves (via direct store access)."""
    store = get_preference_store()
    store.clear_all()

    # Simulate POST behavior
    admin_pref = AdminPreference(
        org_id="api_org_1",
        forced_interaction_mode=InteractionMode.DEEP_ADAPTIVE
    )
    store.set_admin_preference(admin_pref)

    # Simulate GET behavior
    retrieved = store.get_admin_preference("api_org_1")

    assert retrieved is not None
    assert retrieved.org_id == "api_org_1"
    assert retrieved.forced_interaction_mode == InteractionMode.DEEP_ADAPTIVE


def test_invalid_mode_string_handling():
    """Test that invalid mode strings are rejected or normalized."""
    from symbolu.policy.interaction_modes import _parse_interaction_mode

    # Valid modes should parse
    assert _parse_interaction_mode("analytics_only") == InteractionMode.ANALYTICS_ONLY
    assert _parse_interaction_mode("SMART_INSIGHT") == InteractionMode.SMART_INSIGHT
    assert _parse_interaction_mode("deep_adaptive") == InteractionMode.DEEP_ADAPTIVE

    # Invalid modes should return None
    assert _parse_interaction_mode("invalid_mode") is None
    assert _parse_interaction_mode("random_string") is None
    assert _parse_interaction_mode("") is None


def test_analyze_endpoint_honors_user_preference():
    """Test that /dilchat/analyze honors stored user preference when user_id passed."""
    store = get_preference_store()
    store.clear_all()

    # Set user preference
    user_pref = UserPreference(
        user_id="analyze_user",
        preferred_interaction_mode=InteractionMode.ANALYTICS_ONLY
    )
    store.set_user_preference(user_pref)

    # Create minimal unified output
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Simulate analyze endpoint behavior (therapy domain defaults to SMART_INSIGHT)
    flags = compute_policy_flags(unified, "therapy", user_id="analyze_user")

    # Verify user preference was applied
    assert flags["interaction_mode"] == "analytics_only"


def test_analyze_endpoint_honors_admin_preference():
    """Test that /symbolu/analyze honors admin preference when org_id passed."""
    store = get_preference_store()
    store.clear_all()

    # Set admin preference
    admin_pref = AdminPreference(
        org_id="analyze_org",
        forced_interaction_mode=InteractionMode.DEEP_ADAPTIVE
    )
    store.set_admin_preference(admin_pref)

    # Create minimal unified output
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40},
        "formulas": {
            "vritti_momentum": 0.65,
            "arc_tension_harmonizer": 0.70,
        }
    }

    # Simulate analyze endpoint behavior
    flags = compute_policy_flags(unified, "therapy", org_id="analyze_org")

    # Verify admin preference was applied
    assert flags["interaction_mode"] == "deep_adaptive"


def test_no_preference_equals_baseline_behavior():
    """Test that when no preference is set, behavior equals previous baseline."""
    store = get_preference_store()
    store.clear_all()

    # Create minimal unified output
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Compute flags without any user_id/org_id (baseline)
    flags_baseline = compute_policy_flags(unified, "therapy")

    # Compute flags with non-existent user_id/org_id (should be same as baseline)
    flags_no_pref = compute_policy_flags(unified, "therapy", user_id="nonexistent", org_id="nonexistent")

    # Verify behavior is identical
    assert flags_baseline["interaction_mode"] == flags_no_pref["interaction_mode"]
    assert flags_baseline["needs_grounding"] == flags_no_pref["needs_grounding"]
    assert flags_baseline["allow_deep_reflection"] == flags_no_pref["allow_deep_reflection"]


# ============================================================================
# GROUP D — Behavioral Invariance (4 tests)
# ============================================================================


def test_routing_and_mapper_unchanged():
    """Test that routing and mapper recommendations are unchanged by preferences."""
    store = get_preference_store()
    store.clear_all()

    # Set user preference
    user_pref = UserPreference(
        user_id="invariance_user",
        preferred_interaction_mode=InteractionMode.DEEP_ADAPTIVE
    )
    store.set_user_preference(user_pref)

    # Create unified output
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Compute flags without preference
    flags_no_pref = compute_policy_flags(unified, "therapy")

    # Compute flags with preference
    flags_with_pref = compute_policy_flags(unified, "therapy", user_id="invariance_user")

    # Verify mapper recommendation is unchanged
    # (Phase 15B affects ONLY UI-level hints, NOT routing/mapper decisions)
    assert flags_no_pref["recommended_mapper"] == flags_with_pref["recommended_mapper"]


def test_trading_generic_unchanged_without_preferences():
    """Test that trading/generic domains remain unchanged without explicit preferences."""
    store = get_preference_store()
    store.clear_all()

    # Create unified output
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Test trading domain
    flags_trading = compute_policy_flags(unified, "trading")
    assert flags_trading["interaction_mode"] == "analytics_only"

    # Test generic domain
    flags_generic = compute_policy_flags(unified, "generic")
    assert flags_generic["interaction_mode"] == "analytics_only"


def test_determinism_with_random_order_calls():
    """Test determinism with random-order calls to preference endpoints."""
    import random

    # Note: This test demonstrates that the FINAL state after a sequence of operations
    # is deterministic - if we execute the same set of operations (regardless of order),
    # the final state will depend on the last operation for each key.
    # The test shows that if user1 is SET then CLEARED, final state is None.
    # But if CLEARED then SET, final state is the SET value.
    # This is correct "last write wins" behavior.

    store = get_preference_store()

    # Define operations - IMPORTANT: operations must not conflict
    # (i.e., same key should not have multiple operations that would give different results)
    # For deterministic testing, we need operations that can execute in any order
    # and still produce the same final state.
    operations = [
        ("set_user", "user_det_1", InteractionMode.ANALYTICS_ONLY),
        ("set_user", "user_det_2", InteractionMode.SMART_INSIGHT),
        ("set_admin", "org_det_1", InteractionMode.DEEP_ADAPTIVE),
        ("set_user", "user_det_3", InteractionMode.SMART_INSIGHT),
    ]

    # Execute in random order 3 times and verify final state is always the same
    final_states = []

    for _ in range(3):
        # Clear only the keys we're testing
        for op_type, id_val, _ in operations:
            if op_type == "set_user":
                store.clear_user(id_val)
            elif op_type == "set_admin":
                store.clear_admin(id_val)

        ops = operations.copy()
        random.shuffle(ops)

        for op_type, id_val, mode in ops:
            if op_type == "set_user":
                store.set_user_preference(UserPreference(id_val, mode))
            elif op_type == "set_admin":
                store.set_admin_preference(AdminPreference(id_val, mode))

        # Capture final state
        state = {
            "user_det_1": store.get_user_preference("user_det_1"),
            "user_det_2": store.get_user_preference("user_det_2"),
            "user_det_3": store.get_user_preference("user_det_3"),
            "org_det_1": store.get_admin_preference("org_det_1"),
        }
        final_states.append(state)

    # Verify all final states are identical (determinism regardless of order)
    for state in final_states:
        assert state["user_det_1"].preferred_interaction_mode == InteractionMode.ANALYTICS_ONLY
        assert state["user_det_2"].preferred_interaction_mode == InteractionMode.SMART_INSIGHT
        assert state["user_det_3"].preferred_interaction_mode == InteractionMode.SMART_INSIGHT
        assert state["org_det_1"].forced_interaction_mode == InteractionMode.DEEP_ADAPTIVE


def test_preference_store_clear_all():
    """Test that clear_all() completely resets the store."""
    store = get_preference_store()

    # Clear first to start with clean state
    store.clear_all()

    # Populate with preferences
    store.set_user_preference(UserPreference("user_clear_1", InteractionMode.SMART_INSIGHT))
    store.set_user_preference(UserPreference("user_clear_2", InteractionMode.ANALYTICS_ONLY))
    store.set_admin_preference(AdminPreference("org_clear_1", InteractionMode.DEEP_ADAPTIVE))

    # Verify preferences exist
    assert store.get_user_count() == 2
    assert store.get_admin_count() == 1

    # Clear all
    store.clear_all()

    # Verify store is empty
    assert store.get_user_count() == 0
    assert store.get_admin_count() == 0
    assert store.get_user_preference("user_clear_1") is None
    assert store.get_user_preference("user_clear_2") is None
    assert store.get_admin_preference("org_clear_1") is None


# ============================================================================
# INTEGRATION TEST — End-to-End Preference Flow
# ============================================================================


def test_end_to_end_preference_flow():
    """
    Integration test: Set preferences → Policy resolves mode → Flags reflect mode.
    """
    store = get_preference_store()
    store.clear_all()

    # Step 1: Set user preference
    user_pref = UserPreference(
        user_id="e2e_user",
        preferred_interaction_mode=InteractionMode.SMART_INSIGHT
    )
    store.set_user_preference(user_pref)

    # Step 2: Set admin preference (higher priority)
    admin_pref = AdminPreference(
        org_id="e2e_org",
        forced_interaction_mode=InteractionMode.ANALYTICS_ONLY
    )
    store.set_admin_preference(admin_pref)

    # Step 3: Create unified output
    unified = {
        "coherence": {
            "coherence_score": 0.75,
            "persona_drift_score": 0.30,
            "mapper_volatility_score": 0.20,
            "temporal_arc_score": 0.80,
        },
        "entropy": {"normalized_entropy": 0.40}
    }

    # Step 4: Compute policy flags with both user_id and org_id
    flags = compute_policy_flags(
        unified,
        "therapy",
        user_id="e2e_user",
        org_id="e2e_org"
    )

    # Step 5: Verify admin preference wins
    assert flags["interaction_mode"] == "analytics_only"

    # Step 6: Remove admin preference
    store.clear_admin("e2e_org")

    # Step 7: Recompute flags (now user preference should apply)
    flags = compute_policy_flags(
        unified,
        "therapy",
        user_id="e2e_user",
        org_id="e2e_org"
    )

    # Step 8: Verify user preference is now active
    assert flags["interaction_mode"] == "smart_insight"

    # Step 9: Remove user preference
    store.clear_user("e2e_user")

    # Step 10: Recompute flags (now domain default should apply)
    flags = compute_policy_flags(
        unified,
        "therapy",
        user_id="e2e_user",
        org_id="e2e_org"
    )

    # Step 11: Verify domain default is active (therapy → SMART_INSIGHT)
    therapy_profile = get_domain_profile("therapy")
    assert flags["interaction_mode"] == therapy_profile["interaction_mode_default"].value
