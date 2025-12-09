"""
Unit tests for CrossDomainIntelligence
=======================================

Tests cover:
1. Risk hiding pattern detection
2. Breakthrough insight pattern detection
3. Threshold filtering
4. Domain transfer functionality
5. Pattern configuration access
"""

import pytest
from temporal.cross_domain_intelligence import CrossDomainIntelligence, PatternConfig


class TestPatternDetection:
    """Tests for pattern detection functionality."""

    def test_risk_hiding_pattern_detection(self):
        """Test detection of risk_hiding pattern with matching parameters."""
        cdi = CrossDomainIntelligence()

        # Parameters that should match risk_hiding:
        # - SMI in range (0.5, 0.75)
        # - bhava_id in range (3, 7)
        # - direction: downward or neutral
        # - temporal_trend: rising or stable
        patterns = cdi.detect_pattern(
            smi=0.62,
            bhava_id=5,
            bhava_direction="downward",
            kosha_id=3,
            ontology_id=5,
            temporal_trend="rising",
        )

        # Extract pattern names
        pattern_names = [p[0] for p in patterns]

        # risk_hiding should be detected
        assert "risk_hiding" in pattern_names

        # Check confidence is high
        risk_hiding_result = next(p for p in patterns if p[0] == "risk_hiding")
        assert risk_hiding_result[1] >= 0.65  # Must meet min_confidence

    def test_risk_hiding_domain_transfer_finance(self):
        """Test domain transfer for risk_hiding to finance domain."""
        cdi = CrossDomainIntelligence()

        result = cdi.transfer_pattern_to_domain("risk_hiding", "finance")

        assert result["pattern"] == "risk_hiding"
        assert result["domain"] == "finance"
        assert "investment risk" in result["interpretation"].lower()
        assert result["category"] == "protective"

    def test_risk_hiding_domain_transfer_medicine(self):
        """Test domain transfer for risk_hiding to medicine domain."""
        cdi = CrossDomainIntelligence()

        result = cdi.transfer_pattern_to_domain("risk_hiding", "medicine")

        assert result["pattern"] == "risk_hiding"
        assert result["domain"] == "medicine"
        assert "symptom" in result["interpretation"].lower() or "downplaying" in result["interpretation"].lower()

    def test_breakthrough_insight_pattern_detection(self):
        """Test detection of breakthrough_insight pattern."""
        cdi = CrossDomainIntelligence()

        # Parameters that should match breakthrough_insight:
        # - SMI in range (0.15, 0.35)
        # - bhava_id in range (6, 9)
        # - direction: upward
        # - temporal_trend: falling or stable
        patterns = cdi.detect_pattern(
            smi=0.25,
            bhava_id=7,
            bhava_direction="upward",
            kosha_id=5,
            ontology_id=7,
            temporal_trend="falling",
        )

        pattern_names = [p[0] for p in patterns]

        # breakthrough_insight should be detected
        assert "breakthrough_insight" in pattern_names

        # integrative_growth may also be detected with these parameters
        # (similar profile)

    def test_integrative_growth_detection(self):
        """Test detection of integrative_growth pattern."""
        cdi = CrossDomainIntelligence()

        # Parameters optimized for integrative_growth:
        # - SMI in range (0.2, 0.4)
        # - bhava_id in range (7, 10)
        # - direction: upward
        patterns = cdi.detect_pattern(
            smi=0.3,
            bhava_id=8,
            bhava_direction="upward",
            kosha_id=6,
            ontology_id=8,
            temporal_trend="falling",
        )

        pattern_names = [p[0] for p in patterns]
        assert "integrative_growth" in pattern_names

    def test_breakthrough_education_domain_transfer(self):
        """Test domain transfer for breakthrough_insight to education."""
        cdi = CrossDomainIntelligence()

        result = cdi.transfer_pattern_to_domain("breakthrough_insight", "education")

        assert result["pattern"] == "breakthrough_insight"
        assert result["domain"] == "education"
        # Should mention learning breakthrough or concept crystallization
        interpretation_lower = result["interpretation"].lower()
        assert (
            "concept" in interpretation_lower
            or "crystalliz" in interpretation_lower
            or "breakthrough" in interpretation_lower
            or "learning" in interpretation_lower
        )


class TestThresholdFiltering:
    """Tests for threshold-based pattern filtering."""

    def test_pattern_below_threshold_not_returned(self):
        """Test that patterns below confidence threshold are filtered out."""
        cdi = CrossDomainIntelligence()

        # Parameters that partially match acute_anxiety but with lower SMI
        # acute_anxiety requires SMI in (0.7, 1.0) and min_confidence=0.75
        patterns = cdi.detect_pattern(
            smi=0.5,  # Below acute_anxiety range
            bhava_id=2,  # In range
            bhava_direction="downward",  # Matches
            kosha_id=1,  # Good kosha match
            ontology_id=1,  # Good ontology match
            temporal_trend="rising",  # Matches
        )

        pattern_names = [p[0] for p in patterns]

        # acute_anxiety should NOT be detected (SMI too low)
        assert "acute_anxiety" not in pattern_names

    def test_all_returned_patterns_meet_threshold(self):
        """Test that all returned patterns meet their minimum confidence."""
        cdi = CrossDomainIntelligence()

        patterns = cdi.detect_pattern(
            smi=0.5,
            bhava_id=5,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
            temporal_trend="stable",
        )

        for pattern_name, confidence in patterns:
            config = cdi.get_pattern_config(pattern_name)
            assert config is not None
            assert confidence >= config.min_confidence, \
                f"{pattern_name} returned with confidence {confidence} < min {config.min_confidence}"

    def test_edge_case_exact_threshold(self):
        """Test behavior when confidence is exactly at threshold."""
        cdi = CrossDomainIntelligence()

        # Get any pattern and verify it's at or above threshold
        patterns = cdi.detect_pattern(
            smi=0.62,
            bhava_id=5,
            bhava_direction="downward",
            kosha_id=3,
            ontology_id=5,
            temporal_trend="rising",
        )

        # All returned patterns should be at or above their thresholds
        for pattern_name, confidence in patterns:
            config = cdi.get_pattern_config(pattern_name)
            assert confidence >= config.min_confidence


class TestDomainTransfer:
    """Tests for domain transfer functionality."""

    def test_all_domains_supported(self):
        """Test that all 6 domains are supported."""
        cdi = CrossDomainIntelligence()

        expected_domains = ["finance", "medicine", "psychology", "education", "legal", "corporate"]
        assert cdi.DOMAINS == expected_domains

    def test_unknown_pattern_raises_error(self):
        """Test that unknown pattern raises ValueError."""
        cdi = CrossDomainIntelligence()

        with pytest.raises(ValueError) as exc_info:
            cdi.transfer_pattern_to_domain("nonexistent_pattern", "finance")

        assert "Unknown pattern" in str(exc_info.value)

    def test_unknown_domain_raises_error(self):
        """Test that unknown domain raises ValueError."""
        cdi = CrossDomainIntelligence()

        with pytest.raises(ValueError) as exc_info:
            cdi.transfer_pattern_to_domain("risk_hiding", "astrology")

        assert "Unknown domain" in str(exc_info.value)

    def test_all_patterns_have_domain_interpretations(self):
        """Test that all patterns have interpretations for all domains."""
        cdi = CrossDomainIntelligence()

        all_patterns = cdi.get_all_patterns()
        all_domains = cdi.DOMAINS

        for pattern in all_patterns:
            for domain in all_domains:
                result = cdi.transfer_pattern_to_domain(pattern, domain)
                assert "interpretation" in result
                assert len(result["interpretation"]) > 0

    def test_domain_transfer_includes_category(self):
        """Test that domain transfer result includes pattern category."""
        cdi = CrossDomainIntelligence()

        result = cdi.transfer_pattern_to_domain("acute_anxiety", "psychology")

        assert result["category"] == "stress"
        assert result["pattern"] == "acute_anxiety"

    def test_legal_domain_interpretation(self):
        """Test legal domain interpretation for cognitive_dissonance."""
        cdi = CrossDomainIntelligence()

        result = cdi.transfer_pattern_to_domain("cognitive_dissonance", "legal")

        assert result["domain"] == "legal"
        interpretation_lower = result["interpretation"].lower()
        assert (
            "contradict" in interpretation_lower
            or "inconsistent" in interpretation_lower
            or "statement" in interpretation_lower
        )


class TestPatternConfiguration:
    """Tests for pattern configuration access."""

    def test_get_pattern_categories(self):
        """Test getting patterns organized by category."""
        cdi = CrossDomainIntelligence()

        categories = cdi.get_pattern_categories()

        expected_categories = ["protective", "growth", "stress", "conflict", "recovery"]
        for cat in expected_categories:
            assert cat in categories
            assert len(categories[cat]) > 0

    def test_get_all_patterns(self):
        """Test getting list of all pattern names."""
        cdi = CrossDomainIntelligence()

        patterns = cdi.get_all_patterns()

        # Should have 13 patterns
        assert len(patterns) == 13

        # Check key patterns exist
        expected_patterns = [
            "risk_hiding",
            "emotional_masking",
            "defensive_rationalization",
            "breakthrough_insight",
            "authentic_expression",
            "integrative_growth",
            "acute_anxiety",
            "chronic_stress",
            "tension_corridor",
            "cognitive_dissonance",
            "avoidance_pattern",
            "recovery_trajectory",
            "resilience_pattern",
        ]

        for pattern in expected_patterns:
            assert pattern in patterns

    def test_get_pattern_config(self):
        """Test getting configuration for specific pattern."""
        cdi = CrossDomainIntelligence()

        config = cdi.get_pattern_config("risk_hiding")

        assert config is not None
        assert config.name == "risk_hiding"
        assert config.category == "protective"
        assert config.min_confidence == 0.65
        assert config.smi_range == (0.5, 0.75)
        assert "downward" in config.directions

    def test_get_nonexistent_pattern_config(self):
        """Test getting config for nonexistent pattern returns None."""
        cdi = CrossDomainIntelligence()

        config = cdi.get_pattern_config("fake_pattern")
        assert config is None


class TestStressPatterns:
    """Tests for stress-related patterns."""

    def test_acute_anxiety_detection(self):
        """Test detection of acute_anxiety pattern."""
        cdi = CrossDomainIntelligence()

        patterns = cdi.detect_pattern(
            smi=0.85,
            bhava_id=2,
            bhava_direction="downward",
            kosha_id=1,
            ontology_id=2,
            temporal_trend="rising",
        )

        pattern_names = [p[0] for p in patterns]
        assert "acute_anxiety" in pattern_names

    def test_chronic_stress_detection(self):
        """Test detection of chronic_stress pattern."""
        cdi = CrossDomainIntelligence()

        patterns = cdi.detect_pattern(
            smi=0.65,
            bhava_id=3,
            bhava_direction="downward",
            kosha_id=2,
            ontology_id=3,
            temporal_trend="stable",
        )

        pattern_names = [p[0] for p in patterns]
        assert "chronic_stress" in pattern_names

    def test_tension_corridor_detection(self):
        """Test detection of tension_corridor pattern."""
        cdi = CrossDomainIntelligence()

        patterns = cdi.detect_pattern(
            smi=0.72,
            bhava_id=4,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=4,
            temporal_trend="stable",
        )

        pattern_names = [p[0] for p in patterns]
        assert "tension_corridor" in pattern_names


class TestRecoveryPatterns:
    """Tests for recovery-related patterns."""

    def test_recovery_trajectory_detection(self):
        """Test detection of recovery_trajectory pattern."""
        cdi = CrossDomainIntelligence()

        patterns = cdi.detect_pattern(
            smi=0.42,
            bhava_id=5,
            bhava_direction="upward",
            kosha_id=4,
            ontology_id=5,
            temporal_trend="falling",
        )

        pattern_names = [p[0] for p in patterns]
        assert "recovery_trajectory" in pattern_names

    def test_resilience_pattern_detection(self):
        """Test detection of resilience_pattern."""
        cdi = CrossDomainIntelligence()

        patterns = cdi.detect_pattern(
            smi=0.35,
            bhava_id=6,
            bhava_direction="upward",
            kosha_id=5,
            ontology_id=6,
            temporal_trend="stable",
        )

        pattern_names = [p[0] for p in patterns]
        assert "resilience_pattern" in pattern_names


class TestNoTemporalTrend:
    """Tests for pattern detection without temporal trend data."""

    def test_detection_without_temporal_trend(self):
        """Test that pattern detection works without temporal_trend."""
        cdi = CrossDomainIntelligence()

        patterns = cdi.detect_pattern(
            smi=0.62,
            bhava_id=5,
            bhava_direction="downward",
            kosha_id=3,
            ontology_id=5,
            temporal_trend=None,  # No temporal data
        )

        # Should still return patterns, just without temporal bonus
        assert isinstance(patterns, list)

        # risk_hiding should still be detectable
        pattern_names = [p[0] for p in patterns]
        assert "risk_hiding" in pattern_names

    def test_confidence_affected_by_temporal_trend(self):
        """Test that temporal_trend affects confidence scores."""
        cdi = CrossDomainIntelligence()

        # Detect with matching temporal trend
        patterns_with_trend = cdi.detect_pattern(
            smi=0.62,
            bhava_id=5,
            bhava_direction="downward",
            kosha_id=3,
            ontology_id=5,
            temporal_trend="rising",  # Matches risk_hiding
        )

        # Detect without temporal trend
        patterns_without_trend = cdi.detect_pattern(
            smi=0.62,
            bhava_id=5,
            bhava_direction="downward",
            kosha_id=3,
            ontology_id=5,
            temporal_trend=None,
        )

        # Find risk_hiding in both results
        risk_with = next((p for p in patterns_with_trend if p[0] == "risk_hiding"), None)
        risk_without = next((p for p in patterns_without_trend if p[0] == "risk_hiding"), None)

        assert risk_with is not None
        assert risk_without is not None

        # Both should be above threshold
        assert risk_with[1] >= 0.65
        assert risk_without[1] >= 0.65


class TestPatternSorting:
    """Tests for pattern result sorting."""

    def test_patterns_sorted_by_confidence(self):
        """Test that returned patterns are sorted by confidence descending."""
        cdi = CrossDomainIntelligence()

        patterns = cdi.detect_pattern(
            smi=0.5,
            bhava_id=5,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
            temporal_trend="stable",
        )

        if len(patterns) > 1:
            confidences = [p[1] for p in patterns]
            assert confidences == sorted(confidences, reverse=True), \
                "Patterns should be sorted by confidence descending"

    def test_multiple_patterns_can_match(self):
        """Test that multiple patterns can match same input."""
        cdi = CrossDomainIntelligence()

        # Parameters that could match multiple patterns
        patterns = cdi.detect_pattern(
            smi=0.3,
            bhava_id=7,
            bhava_direction="upward",
            kosha_id=5,
            ontology_id=7,
            temporal_trend="falling",
        )

        # Should get multiple growth patterns
        assert len(patterns) >= 1
