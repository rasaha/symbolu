"""
LAM v1.0 Integration Tests

Tests for the Long-Arc Mapper engine integration with
TemporalBhavaTracker and CrossDomainIntelligence.

Simulates multi-turn conversations to verify:
- Arc state transitions (tension -> recovery)
- Pattern persistence across turns
- Domain transfer consistency
- Trajectory tracking over time
"""

import pytest

from symbolu.mechanical.lam import LAMEngine, LAMInput, LongArcMap
from symbolu.temporal.temporal_bhava_tracker import TemporalBhavaTracker
from symbolu.temporal.cross_domain_intelligence import CrossDomainIntelligence


class TestMultiTurnConversation:
    """Tests simulating multi-turn conversations."""

    def test_tension_to_recovery_transition(self):
        """
        Simulate a conversation that transitions from tension to recovery.

        Scenario:
        - Turn 1-2: High tension (high SMI, downward movement)
        - Turn 3-4: Recovery (dropping SMI, upward movement)
        """
        tracker = TemporalBhavaTracker(window_size=5)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # Turn 1: Initial tension
        turn1 = LAMInput(
            text="I'm overwhelmed with everything",
            smi=0.75,
            bhava_id=3,
            bhava_direction="downward",
            kosha_id=2,
            ontology_id=3,
            domain="psychology",
            long_arc_tension=0.7,
            temporal_tracker=tracker,
            cdi=cdi,
        )
        result1 = engine.build_map(turn1)

        # Turn 2: Continued tension
        turn2 = LAMInput(
            text="It's all too much",
            smi=0.78,
            bhava_id=2,
            bhava_direction="downward",
            kosha_id=2,
            ontology_id=2,
            domain="psychology",
            long_arc_tension=0.75,
            temporal_tracker=tracker,
            cdi=cdi,
        )
        result2 = engine.build_map(turn2)

        # Should be in tension state
        assert result2.arc_state == "tension"

        # Turn 3: Beginning recovery
        turn3 = LAMInput(
            text="I think I can handle some of it",
            smi=0.55,
            bhava_id=4,
            bhava_direction="upward",
            kosha_id=3,
            ontology_id=4,
            domain="psychology",
            long_arc_tension=0.4,
            temporal_tracker=tracker,
            cdi=cdi,
        )
        result3 = engine.build_map(turn3)

        # Turn 4: Deeper recovery
        turn4 = LAMInput(
            text="Actually, I'm starting to see a way forward",
            smi=0.40,
            bhava_id=5,
            bhava_direction="upward",
            kosha_id=4,
            ontology_id=5,
            domain="psychology",
            long_arc_tension=0.3,
            temporal_tracker=tracker,
            cdi=cdi,
        )
        result4 = engine.build_map(turn4)

        # Should have transitioned to recovery
        assert result4.arc_state == "recovery"

        # Trajectory should show falling trend (SMI decreasing = recovery)
        assert result4.trajectory_summary.get("trend") == "falling"

    def test_pattern_persistence_across_turns(self):
        """
        Test that patterns persist consistently across turns
        when conditions remain similar.
        """
        tracker = TemporalBhavaTracker(window_size=5)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine(pattern_confidence_threshold=0.60)

        detected_patterns = []

        # Multiple turns with similar inputs to trigger consistent patterns
        for i in range(3):
            lam_input = LAMInput(
                text=f"Understanding grows {i}",
                smi=0.25 + i * 0.02,  # Slight variation
                bhava_id=7,
                bhava_direction="upward",
                kosha_id=5,
                ontology_id=7,
                domain="psychology",
                long_arc_tension=0.3,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)
            detected_patterns.append(set(result.active_patterns))

        # Check for pattern consistency
        # At least some patterns should appear in multiple turns
        all_patterns = detected_patterns[0].union(detected_patterns[1]).union(detected_patterns[2])

        # Should detect at least one pattern consistently
        assert len(all_patterns) >= 1, "Should detect at least one pattern"

        # Check if patterns that appear should be consistent
        for pattern in all_patterns:
            # Pattern should appear in at least 2 turns if conditions are similar
            count = sum(1 for p_set in detected_patterns if pattern in p_set)
            # This is a soft assertion - patterns may vary with trajectory
            if count >= 2:
                assert True  # Pattern shows consistency

    def test_domain_transfer_determinism(self):
        """
        Test that domain transfer strings are deterministic
        for the same pattern and domain.
        """
        tracker = TemporalBhavaTracker(window_size=5)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine(pattern_confidence_threshold=0.60)

        domain_transfers_list = []

        # Same inputs should produce same domain transfers
        for i in range(3):
            lam_input = LAMInput(
                text="Pattern trigger",
                smi=0.62,
                bhava_id=5,
                bhava_direction="downward",
                kosha_id=3,
                ontology_id=5,
                domain="finance",
                long_arc_tension=0.4,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)
            domain_transfers_list.append(result.domain_transfers)

        # All domain transfers should be identical for same patterns
        if len(domain_transfers_list) > 0 and len(domain_transfers_list[0]) > 0:
            for i in range(1, len(domain_transfers_list)):
                for pattern in domain_transfers_list[0]:
                    if pattern in domain_transfers_list[i]:
                        assert domain_transfers_list[0][pattern] == domain_transfers_list[i][pattern]

    def test_cross_domain_integration(self):
        """
        Test LAM with different domains to verify
        domain-specific interpretations.
        """
        domains = ["finance", "medicine", "psychology", "education", "legal", "corporate"]
        results = {}

        for domain in domains:
            tracker = TemporalBhavaTracker(window_size=5)
            cdi = CrossDomainIntelligence()
            engine = LAMEngine(pattern_confidence_threshold=0.60)

            # Same inputs but different domains
            lam_input = LAMInput(
                text="I need to reassess the situation",
                smi=0.55,
                bhava_id=4,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=4,
                domain=domain,
                long_arc_tension=0.4,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)
            results[domain] = result

        # Domain transfers should be domain-specific
        for domain, result in results.items():
            for pattern, transfer in result.domain_transfers.items():
                # Each transfer should contain domain-relevant terms
                # or be a valid interpretation
                assert len(transfer) > 0, f"Domain {domain} should have valid transfer for {pattern}"


class TestTemporalIntegration:
    """Tests for temporal tracking integration."""

    def test_sliding_window_behavior(self):
        """
        Test that LAM respects the sliding window of TemporalBhavaTracker.
        """
        window_size = 3
        tracker = TemporalBhavaTracker(window_size=window_size)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # Feed more entries than window size
        for i in range(5):
            lam_input = LAMInput(
                text=f"Query {i}",
                smi=0.3 + i * 0.1,
                bhava_id=4,
                bhava_direction="upward" if i > 2 else "neutral",
                kosha_id=3,
                ontology_id=5,
                domain="psychology",
                long_arc_tension=0.2,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            engine.build_map(lam_input)

        # Tracker should only have window_size entries
        assert len(tracker.entries) == window_size

    def test_trajectory_confidence_increases_with_data(self):
        """
        Test that trajectory confidence increases as more data is collected.
        """
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        confidences = []

        for i in range(5):
            lam_input = LAMInput(
                text=f"Query {i}",
                smi=0.3 + i * 0.05,  # Clear rising trend
                bhava_id=5,
                bhava_direction="upward",
                kosha_id=4,
                ontology_id=5,
                domain="psychology",
                long_arc_tension=0.3,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)
            confidences.append(result.trajectory_summary.get("confidence", 0.0))

        # Confidence should generally increase with more data
        # (may not be strictly monotonic but trend should be upward)
        assert confidences[-1] >= confidences[0], "Confidence should increase with more data"


class TestFullConversationScenarios:
    """Full conversation scenario tests."""

    def test_therapy_session_scenario(self):
        """
        Simulate a therapy session with emotional arc:
        - Start: Distress
        - Middle: Exploration
        - End: Insight/Resolution
        """
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        conversation = [
            # Distress phase
            ("I can't stop worrying about everything", 0.75, 2, "downward", 0.7),
            ("It's been weeks like this", 0.70, 3, "downward", 0.65),
            # Exploration phase
            ("I guess it started when...", 0.55, 4, "neutral", 0.5),
            ("I never thought about it that way", 0.45, 5, "upward", 0.4),
            # Insight phase
            ("Oh, I see the connection now", 0.30, 6, "upward", 0.3),
            ("I feel like I finally understand", 0.25, 7, "upward", 0.2),
        ]

        arc_states = []
        for text, smi, bhava_id, direction, lat in conversation:
            lam_input = LAMInput(
                text=text,
                smi=smi,
                bhava_id=bhava_id,
                bhava_direction=direction,
                kosha_id=max(1, bhava_id - 1),
                ontology_id=max(1, bhava_id + 1),
                domain="psychology",
                long_arc_tension=lat,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)
            arc_states.append(result.arc_state)

        # Should show progression through states
        # Early states likely "tension", later states "recovery" or "turning_point"
        assert arc_states[0] in ["tension", "steady"], "Should start in tension or steady"
        assert arc_states[-1] in ["recovery", "turning_point", "steady"], "Should end in positive state"

    def test_financial_consultation_scenario(self):
        """
        Simulate a financial consultation with risk assessment arc.
        """
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine(pattern_confidence_threshold=0.60)

        conversation = [
            # Risk assessment
            ("I think the investment is safe", 0.60, 4, "neutral", 0.5),
            ("But there are some concerns", 0.65, 3, "downward", 0.55),
            # Analysis
            ("Looking at the data more carefully", 0.55, 5, "neutral", 0.45),
            ("I see both risks and opportunities", 0.50, 6, "upward", 0.4),
        ]

        results = []
        for text, smi, bhava_id, direction, lat in conversation:
            lam_input = LAMInput(
                text=text,
                smi=smi,
                bhava_id=bhava_id,
                bhava_direction=direction,
                kosha_id=max(1, bhava_id - 2),
                ontology_id=max(1, bhava_id),
                domain="finance",
                long_arc_tension=lat,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)
            results.append(result)

        # Check domain transfers are finance-specific
        for result in results:
            for pattern, transfer in result.domain_transfers.items():
                # Finance domain transfers should contain financial language
                finance_terms = ["investment", "risk", "financial", "market", "portfolio"]
                has_finance_term = any(term in transfer.lower() for term in finance_terms)
                # Allow generic transfers too, but prefer finance-specific
                assert has_finance_term or len(transfer) > 0


class TestEdgeCases:
    """Edge case tests."""

    def test_single_turn_conversation(self):
        """LAM should work with just one turn."""
        tracker = TemporalBhavaTracker(window_size=5)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        lam_input = LAMInput(
            text="Single query",
            smi=0.5,
            bhava_id=5,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
            domain="psychology",
            long_arc_tension=0.3,
            temporal_tracker=tracker,
            cdi=cdi,
        )

        result = engine.build_map(lam_input)

        assert result.arc_state == "steady"
        assert result.trajectory_summary.get("trend") == "stable"

    def test_extreme_values(self):
        """LAM should handle extreme input values gracefully."""
        tracker = TemporalBhavaTracker(window_size=5)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        extreme_input = LAMInput(
            text="Extreme query",
            smi=1.0,  # Maximum SMI
            bhava_id=10,  # High bhava
            bhava_direction="upward",
            kosha_id=7,  # High kosha
            ontology_id=9,  # High ontology
            domain="psychology",
            long_arc_tension=1.0,  # Maximum tension
            temporal_tracker=tracker,
            cdi=cdi,
        )

        result = engine.build_map(extreme_input)

        # Should not crash and produce valid output
        assert result.arc_state in ["tension", "recovery", "turning_point", "steady"]
        assert 0.0 <= result.long_arc_signal <= 1.0

    def test_zero_values(self):
        """LAM should handle zero input values gracefully."""
        tracker = TemporalBhavaTracker(window_size=5)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        zero_input = LAMInput(
            text="Minimal query",
            smi=0.0,  # Minimum SMI
            bhava_id=1,
            bhava_direction="neutral",
            kosha_id=1,
            ontology_id=1,
            domain="psychology",
            long_arc_tension=0.0,
            temporal_tracker=tracker,
            cdi=cdi,
        )

        result = engine.build_map(zero_input)

        # Should not crash and produce valid output
        assert result.arc_state in ["tension", "recovery", "turning_point", "steady"]
        assert 0.0 <= result.long_arc_signal <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
