"""
Tests for Persona Drift Monitor.

Validates:
- Drift detection for domain changes
- Drift detection for bhava jumps
- Drift detection for bhava direction oscillations
- Drift detection for arc_mode changes
- Edge cases and stability scenarios
"""

import pytest
from symbolu.core.coherence.persona_drift_monitor import (
    compute_persona_drift,
    _compute_domain_instability,
    _compute_bhava_instability,
    _compute_arc_mode_instability,
)


class TestDomainInstability:
    """Test domain instability computation."""

    def test_constant_domain_zero_instability(self):
        """Test that constant domain results in zero instability."""
        domain_history = ["task"] * 5

        instability = _compute_domain_instability(domain_history)

        assert instability == 0.0

    def test_all_changes_max_instability(self):
        """Test that all changes result in max (1.0) instability."""
        domain_history = ["task", "finance", "therapy", "identity", "spiritual"]

        instability = _compute_domain_instability(domain_history)

        assert instability == 1.0

    def test_partial_changes(self):
        """Test partial domain changes."""
        domain_history = ["task", "task", "finance", "finance", "therapy"]

        instability = _compute_domain_instability(domain_history)

        # 2 changes out of 4 transitions = 0.5
        assert instability == 0.5

    def test_empty_history(self):
        """Test empty domain history returns 0."""
        domain_history = []

        instability = _compute_domain_instability(domain_history)

        assert instability == 0.0

    def test_single_entry(self):
        """Test single domain entry returns 0."""
        domain_history = ["task"]

        instability = _compute_domain_instability(domain_history)

        assert instability == 0.0


class TestBhavaInstability:
    """Test bhava instability computation."""

    def test_stable_bhava_zero_instability(self):
        """Test that stable bhava results in low instability."""
        bhava_id_history = [5, 5, 5, 5, 5]
        bhava_direction_history = ["stable"] * 5

        instability = _compute_bhava_instability(bhava_id_history, bhava_direction_history)

        assert instability == 0.0

    def test_big_jumps_high_instability(self):
        """Test that big bhava jumps (>=3) result in high instability."""
        bhava_id_history = [0, 5, 10, 2, 8]  # All jumps >= 3
        bhava_direction_history = ["stable"] * 5

        instability = _compute_bhava_instability(bhava_id_history, bhava_direction_history)

        # All 4 transitions are big jumps
        assert instability >= 0.6  # High instability

    def test_small_jumps_low_instability(self):
        """Test that small bhava jumps (<3) result in low instability."""
        bhava_id_history = [5, 6, 7, 8, 9]  # All jumps = 1
        bhava_direction_history = ["upward"] * 5

        instability = _compute_bhava_instability(bhava_id_history, bhava_direction_history)

        # No big jumps, no oscillations
        assert instability < 0.3

    def test_direction_oscillations(self):
        """Test that direction oscillations increase instability."""
        bhava_id_history = [5, 5, 5, 5, 5]  # No ID jumps
        bhava_direction_history = ["upward", "downward", "upward", "downward", "upward"]

        instability = _compute_bhava_instability(bhava_id_history, bhava_direction_history)

        # Should detect oscillations
        assert instability > 0.0

    def test_empty_history(self):
        """Test empty bhava history returns 0."""
        bhava_id_history = []
        bhava_direction_history = []

        instability = _compute_bhava_instability(bhava_id_history, bhava_direction_history)

        assert instability == 0.0


class TestArcModeInstability:
    """Test arc_mode instability computation."""

    def test_constant_arc_mode_zero_instability(self):
        """Test that constant arc_mode results in zero instability."""
        mapper_profile_history = [{"arc_mode": "none"}] * 5

        instability = _compute_arc_mode_instability(mapper_profile_history)

        assert instability == 0.0

    def test_all_changes_max_instability(self):
        """Test that all arc_mode changes result in max instability."""
        mapper_profile_history = [
            {"arc_mode": "none"},
            {"arc_mode": "identity"},
            {"arc_mode": "temporal"},
            {"arc_mode": "deep_context"},
            {"arc_mode": "none"},
        ]

        instability = _compute_arc_mode_instability(mapper_profile_history)

        assert instability == 1.0

    def test_partial_changes(self):
        """Test partial arc_mode changes."""
        mapper_profile_history = [
            {"arc_mode": "none"},
            {"arc_mode": "none"},
            {"arc_mode": "identity"},
            {"arc_mode": "identity"},
            {"arc_mode": "temporal"},
        ]

        instability = _compute_arc_mode_instability(mapper_profile_history)

        # 2 changes out of 4 transitions = 0.5
        assert instability == 0.5

    def test_empty_history(self):
        """Test empty mapper history returns 0."""
        mapper_profile_history = []

        instability = _compute_arc_mode_instability(mapper_profile_history)

        assert instability == 0.0


class TestPersonaDrift:
    """Test overall persona drift computation."""

    def test_stable_identity_zero_drift(self):
        """Test that stable identity domain with stable bhava results in near-zero drift."""
        domain_history = ["identity"] * 5
        mapper_profile_history = [{"arc_mode": "identity"}] * 5
        bhava_id_history = [5, 5, 5, 5, 5]
        bhava_direction_history = ["stable"] * 5

        drift = compute_persona_drift(
            domain_history,
            mapper_profile_history,
            bhava_id_history,
            bhava_direction_history,
        )

        assert drift == 0.0

    def test_rapid_domain_flipping_high_drift(self):
        """Test that rapid domain flipping results in high drift."""
        domain_history = ["identity", "task", "therapy", "finance", "identity", "spiritual"]
        mapper_profile_history = [{"arc_mode": "identity"}] * 6
        bhava_id_history = [5] * 6
        bhava_direction_history = ["stable"] * 6

        drift = compute_persona_drift(
            domain_history,
            mapper_profile_history,
            bhava_id_history,
            bhava_direction_history,
        )

        # High domain instability should contribute significantly
        # Domain instability = 1.0, weight = 0.4 → drift = 0.4
        assert drift >= 0.4

    def test_arc_mode_flips_increase_drift(self):
        """Test that arc_mode flips increase drift."""
        domain_history = ["identity"] * 6
        mapper_profile_history = [
            {"arc_mode": "identity"},
            {"arc_mode": "none"},
            {"arc_mode": "identity"},
            {"arc_mode": "none"},
            {"arc_mode": "identity"},
            {"arc_mode": "none"},
        ]
        bhava_id_history = [5] * 6
        bhava_direction_history = ["stable"] * 6

        drift = compute_persona_drift(
            domain_history,
            mapper_profile_history,
            bhava_id_history,
            bhava_direction_history,
        )

        # Arc mode instability should contribute
        assert drift > 0.2

    def test_combined_instabilities(self):
        """Test that combined instabilities result in high drift."""
        domain_history = ["task", "therapy", "finance", "identity", "task"]
        mapper_profile_history = [
            {"arc_mode": "none"},
            {"arc_mode": "identity"},
            {"arc_mode": "temporal"},
            {"arc_mode": "none"},
            {"arc_mode": "identity"},
        ]
        bhava_id_history = [0, 5, 10, 3, 9]
        bhava_direction_history = ["upward", "downward", "upward", "downward", "upward"]

        drift = compute_persona_drift(
            domain_history,
            mapper_profile_history,
            bhava_id_history,
            bhava_direction_history,
        )

        # All instabilities combined
        assert drift > 0.6

    def test_drift_in_bounds(self):
        """Test that drift score is always in [0, 1] bounds."""
        # Test various scenarios
        test_cases = [
            # (domains, mapper_profiles, bhava_ids, bhava_directions)
            (
                ["task"] * 5,
                [{"arc_mode": "none"}] * 5,
                [5] * 5,
                ["stable"] * 5,
            ),
            (
                ["task", "finance", "therapy", "identity", "spiritual"],
                [{"arc_mode": "none"}] * 5,
                [0, 5, 10, 2, 8],
                ["upward", "downward", "upward", "downward", "stable"],
            ),
        ]

        for domains, profiles, bhava_ids, directions in test_cases:
            drift = compute_persona_drift(domains, profiles, bhava_ids, directions)
            assert 0.0 <= drift <= 1.0

    def test_empty_history_returns_zero(self):
        """Test that empty history returns zero drift."""
        drift = compute_persona_drift([], [], [], [])

        assert drift == 0.0

    def test_single_turn_returns_zero(self):
        """Test that single turn returns zero drift."""
        drift = compute_persona_drift(
            ["task"],
            [{"arc_mode": "none"}],
            [5],
            ["stable"],
        )

        assert drift == 0.0

    def test_gradual_identity_evolution_low_drift(self):
        """Test that gradual, coherent evolution has low drift."""
        # Simulating a coherent therapeutic journey
        domain_history = ["therapy", "therapy", "therapy", "identity", "identity"]
        mapper_profile_history = [
            {"arc_mode": "deep_context"},
            {"arc_mode": "deep_context"},
            {"arc_mode": "identity"},
            {"arc_mode": "identity"},
            {"arc_mode": "identity"},
        ]
        bhava_id_history = [3, 4, 5, 5, 6]
        bhava_direction_history = ["upward", "upward", "upward", "stable", "upward"]

        drift = compute_persona_drift(
            domain_history,
            mapper_profile_history,
            bhava_id_history,
            bhava_direction_history,
        )

        # Gradual, coherent evolution should have relatively low drift
        assert drift < 0.4
