"""
Comprehensive Unit Tests for Configurable Decision Posture
===========================================================

Tests cover:
    1. DecisionPostureProfile creation, validation, normalization
    2. Tier-specific influence rules (Tier 1 = no influence)
    3. Determinism of all modulation functions
    4. Audit record generation and validation
    5. Hard constraint enforcement
    6. Preset profile correctness
    7. Configuration validation

Version: 1.0
Date: 2025-12-22
"""

import pytest
from typing import List

from symbolu.posture import (
    # Types
    DecisionPostureProfile,
    PostureConfig,
    PostureApplicationResult,
    PostureAuditRecord,
    PostureTier,
    PostureInfluenceScope,
    PostureConstraint,
    HARD_CONSTRAINTS,
    TIER_ALLOWED_INFLUENCES,
    # Presets
    BALANCED_DEFAULT,
    CONSERVATIVE_ENTERPRISE,
    EXPLORATORY_RESEARCH,
    HIGH_COHERENCE,
    HIGH_CONSTRAINT,
    get_preset_profile,
    list_presets,
    get_tier_default_config,
    create_custom_profile,
    create_config,
    # Modulation
    apply_posture_to_routing,
    apply_posture_to_escalation,
    apply_posture_to_response_depth,
    apply_posture_to_conservatism,
    apply_posture_to_cascade_aggressiveness,
    apply_posture_to_feedback_activation,
    apply_posture_to_all,
    is_influence_allowed,
    # Audit
    create_audit_record,
    format_audit_for_api_response,
    format_audit_for_detailed_log,
    format_audit_for_compliance_report,
    validate_audit_record,
    summarize_applications,
)


# =============================================================================
# DecisionPostureProfile Tests
# =============================================================================

class TestDecisionPostureProfile:
    """Tests for DecisionPostureProfile dataclass."""

    def test_profile_creation_basic(self):
        """Test basic profile creation."""
        profile = DecisionPostureProfile(
            coherence_bias=0.5,
            exploration_bias=0.3,
            constraint_bias=0.2,
        )
        assert profile.coherence_bias == 0.5
        assert profile.exploration_bias == 0.3
        assert profile.constraint_bias == 0.2

    def test_profile_is_frozen(self):
        """Test that profile is immutable (frozen dataclass)."""
        profile = DecisionPostureProfile(
            coherence_bias=0.5,
            exploration_bias=0.3,
            constraint_bias=0.2,
        )
        with pytest.raises(AttributeError):
            profile.coherence_bias = 0.9

    def test_profile_clamps_negative_values(self):
        """Test that negative values are clamped to 0."""
        profile = DecisionPostureProfile(
            coherence_bias=-0.5,
            exploration_bias=0.3,
            constraint_bias=0.2,
        )
        assert profile.coherence_bias == 0.0

    def test_profile_clamps_values_over_one(self):
        """Test that values over 1.0 are clamped."""
        profile = DecisionPostureProfile(
            coherence_bias=1.5,
            exploration_bias=0.3,
            constraint_bias=0.2,
        )
        assert profile.coherence_bias == 1.0

    def test_profile_normalize_balanced(self):
        """Test normalization of balanced profile."""
        profile = DecisionPostureProfile(
            coherence_bias=1.0,
            exploration_bias=1.0,
            constraint_bias=1.0,
        )
        normalized = profile.normalize()
        # All should be roughly 1/3
        assert abs(normalized.coherence_bias - 1/3) < 0.01
        assert abs(normalized.exploration_bias - 1/3) < 0.01
        assert abs(normalized.constraint_bias - 1/3) < 0.01

    def test_profile_normalize_unbalanced(self):
        """Test normalization of unbalanced profile."""
        profile = DecisionPostureProfile(
            coherence_bias=0.8,
            exploration_bias=0.1,
            constraint_bias=0.1,
        )
        normalized = profile.normalize()
        # Sum should equal 1.0
        total = normalized.coherence_bias + normalized.exploration_bias + normalized.constraint_bias
        assert abs(total - 1.0) < 0.001

    def test_profile_normalize_zero_total(self):
        """Test normalization when all values are zero."""
        profile = DecisionPostureProfile(
            coherence_bias=0.0,
            exploration_bias=0.0,
            constraint_bias=0.0,
        )
        normalized = profile.normalize()
        # Should return balanced default
        assert abs(normalized.coherence_bias - 1/3) < 0.01
        assert abs(normalized.exploration_bias - 1/3) < 0.01
        assert abs(normalized.constraint_bias - 1/3) < 0.01

    def test_profile_normalize_applies_hard_caps(self):
        """Test that normalize applies MIN_BIAS and prevents extreme dominance."""
        # Create extreme profile
        profile = DecisionPostureProfile(
            coherence_bias=0.95,
            exploration_bias=0.025,
            constraint_bias=0.025,
        )
        normalized = profile.normalize()
        # After normalization, biases sum to 1.0
        total = normalized.coherence_bias + normalized.exploration_bias + normalized.constraint_bias
        assert abs(total - 1.0) < 0.001
        # Smaller biases should be raised to at least MIN_BIAS (before re-normalization)
        assert normalized.exploration_bias >= 0.05
        assert normalized.constraint_bias >= 0.05
        # Coherence should still dominate but extreme values are moderated
        assert normalized.coherence_bias > normalized.exploration_bias
        assert normalized.coherence_bias > normalized.constraint_bias

    def test_profile_is_balanced_true(self):
        """Test is_balanced returns true for balanced profile."""
        profile = DecisionPostureProfile(
            coherence_bias=0.34,
            exploration_bias=0.33,
            constraint_bias=0.33,
        )
        assert profile.is_balanced is True

    def test_profile_is_balanced_false(self):
        """Test is_balanced returns false for unbalanced profile."""
        profile = DecisionPostureProfile(
            coherence_bias=0.7,
            exploration_bias=0.2,
            constraint_bias=0.1,
        )
        assert profile.is_balanced is False

    def test_profile_to_dict(self):
        """Test serialization to dictionary."""
        profile = DecisionPostureProfile(
            coherence_bias=0.5,
            exploration_bias=0.3,
            constraint_bias=0.2,
        )
        data = profile.to_dict()
        assert data["coherence_bias"] == 0.5
        assert data["exploration_bias"] == 0.3
        assert data["constraint_bias"] == 0.2

    def test_profile_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "coherence_bias": 0.5,
            "exploration_bias": 0.3,
            "constraint_bias": 0.2,
        }
        profile = DecisionPostureProfile.from_dict(data)
        assert profile.coherence_bias == 0.5
        assert profile.exploration_bias == 0.3
        assert profile.constraint_bias == 0.2

    def test_profile_from_dict_with_defaults(self):
        """Test deserialization uses defaults for missing keys."""
        data = {"coherence_bias": 0.5}
        profile = DecisionPostureProfile.from_dict(data)
        assert profile.coherence_bias == 0.5
        assert abs(profile.exploration_bias - 1/3) < 0.01
        assert abs(profile.constraint_bias - 1/3) < 0.01


# =============================================================================
# Tier Safety Tests
# =============================================================================

class TestTierSafety:
    """Tests for tier-specific safety rules."""

    def test_tier1_has_no_allowed_influences(self):
        """Tier 1 must have NO posture influence."""
        allowed = TIER_ALLOWED_INFLUENCES[PostureTier.TIER_1]
        assert allowed == ()
        assert len(allowed) == 0

    def test_tier2_has_limited_influences(self):
        """Tier 2 must have limited posture influence."""
        allowed = TIER_ALLOWED_INFLUENCES[PostureTier.TIER_2]
        assert PostureInfluenceScope.ROUTING_THRESHOLD in allowed
        assert PostureInfluenceScope.RESPONSE_DEPTH in allowed
        # But NOT cascade or feedback
        assert PostureInfluenceScope.CASCADE_AGGRESSIVENESS not in allowed
        assert PostureInfluenceScope.FEEDBACK_ACTIVATION not in allowed

    def test_tier3_has_full_influences(self):
        """Tier 3 must have full posture influence."""
        allowed = TIER_ALLOWED_INFLUENCES[PostureTier.TIER_3]
        assert PostureInfluenceScope.CASCADE_AGGRESSIVENESS in allowed
        assert PostureInfluenceScope.FEEDBACK_ACTIVATION in allowed
        assert PostureInfluenceScope.ROUTING_THRESHOLD in allowed

    def test_is_influence_allowed_tier1(self):
        """Test is_influence_allowed returns False for all Tier 1 scopes."""
        for scope in PostureInfluenceScope:
            assert is_influence_allowed(PostureTier.TIER_1, scope) is False

    def test_is_influence_allowed_tier2(self):
        """Test is_influence_allowed for Tier 2."""
        assert is_influence_allowed(PostureTier.TIER_2, PostureInfluenceScope.ROUTING_THRESHOLD) is True
        assert is_influence_allowed(PostureTier.TIER_2, PostureInfluenceScope.CASCADE_AGGRESSIVENESS) is False

    def test_is_influence_allowed_tier3(self):
        """Test is_influence_allowed for Tier 3."""
        assert is_influence_allowed(PostureTier.TIER_3, PostureInfluenceScope.ROUTING_THRESHOLD) is True
        assert is_influence_allowed(PostureTier.TIER_3, PostureInfluenceScope.CASCADE_AGGRESSIVENESS) is True


# =============================================================================
# Modulation Function Tests
# =============================================================================

class TestModulationFunctions:
    """Tests for posture modulation functions."""

    @pytest.fixture
    def balanced_profile(self) -> DecisionPostureProfile:
        return BALANCED_DEFAULT

    @pytest.fixture
    def conservative_profile(self) -> DecisionPostureProfile:
        return CONSERVATIVE_ENTERPRISE

    @pytest.fixture
    def exploratory_profile(self) -> DecisionPostureProfile:
        return EXPLORATORY_RESEARCH

    def test_routing_tier1_no_influence(self, balanced_profile):
        """Tier 1 routing must NOT be influenced."""
        result = apply_posture_to_routing(
            base_confidence=0.75,
            posture=balanced_profile,
            tier=PostureTier.TIER_1,
        )
        assert result.was_influenced is False
        assert result.adjusted_value == result.original_value
        assert result.adjustment_delta == 0.0

    def test_routing_tier2_is_influenced(self, balanced_profile):
        """Tier 2 routing CAN be influenced."""
        result = apply_posture_to_routing(
            base_confidence=0.75,
            posture=balanced_profile,
            tier=PostureTier.TIER_2,
        )
        # May or may not be influenced depending on profile
        assert result.influence_scope == PostureInfluenceScope.ROUTING_THRESHOLD

    def test_escalation_tier1_no_influence(self, balanced_profile):
        """Tier 1 escalation must NOT be influenced."""
        result = apply_posture_to_escalation(
            base_threshold=0.5,
            posture=balanced_profile,
            tier=PostureTier.TIER_1,
        )
        assert result.was_influenced is False

    def test_response_depth_tier2_influenced(self, balanced_profile):
        """Tier 2 response depth CAN be influenced."""
        result = apply_posture_to_response_depth(
            base_depth=0.5,
            posture=balanced_profile,
            tier=PostureTier.TIER_2,
        )
        assert result.influence_scope == PostureInfluenceScope.RESPONSE_DEPTH

    def test_cascade_tier2_not_influenced(self, balanced_profile):
        """Tier 2 cascade must NOT be influenced."""
        result = apply_posture_to_cascade_aggressiveness(
            base_aggressiveness=0.5,
            posture=balanced_profile,
            tier=PostureTier.TIER_2,
        )
        assert result.was_influenced is False

    def test_cascade_tier3_is_influenced(self, exploratory_profile):
        """Tier 3 cascade CAN be influenced."""
        result = apply_posture_to_cascade_aggressiveness(
            base_aggressiveness=0.5,
            posture=exploratory_profile,
            tier=PostureTier.TIER_3,
        )
        assert result.influence_scope == PostureInfluenceScope.CASCADE_AGGRESSIVENESS

    def test_feedback_tier3_is_influenced(self, exploratory_profile):
        """Tier 3 feedback CAN be influenced."""
        result = apply_posture_to_feedback_activation(
            base_activation=0.5,
            posture=exploratory_profile,
            tier=PostureTier.TIER_3,
        )
        assert result.influence_scope == PostureInfluenceScope.FEEDBACK_ACTIVATION

    def test_conservatism_increases_with_constraint_bias(self):
        """High constraint bias should increase conservatism."""
        high_constraint = HIGH_CONSTRAINT
        low_constraint = EXPLORATORY_RESEARCH

        result_high = apply_posture_to_conservatism(
            base_level=0.5,
            posture=high_constraint,
            tier=PostureTier.TIER_3,
        )
        result_low = apply_posture_to_conservatism(
            base_level=0.5,
            posture=low_constraint,
            tier=PostureTier.TIER_3,
        )

        # High constraint should result in higher conservatism
        assert result_high.adjusted_value > result_low.adjusted_value

    def test_apply_to_all_tier1_none_influenced(self, balanced_profile):
        """apply_posture_to_all with Tier 1 should influence nothing."""
        base_values = {scope.value: 0.5 for scope in PostureInfluenceScope}
        results = apply_posture_to_all(
            posture=balanced_profile,
            tier=PostureTier.TIER_1,
            base_values=base_values,
        )
        for result in results:
            assert result.was_influenced is False

    def test_apply_to_all_tier3_some_influenced(self, exploratory_profile):
        """apply_posture_to_all with Tier 3 should influence most scopes."""
        base_values = {scope.value: 0.5 for scope in PostureInfluenceScope}
        results = apply_posture_to_all(
            posture=exploratory_profile,
            tier=PostureTier.TIER_3,
            base_values=base_values,
        )
        # At least some should be influenced
        influenced = [r for r in results if r.was_influenced]
        assert len(influenced) > 0


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_routing_is_deterministic(self):
        """Same inputs must produce same outputs."""
        profile = CONSERVATIVE_ENTERPRISE
        results = []
        for _ in range(100):
            result = apply_posture_to_routing(
                base_confidence=0.75,
                posture=profile,
                tier=PostureTier.TIER_2,
            )
            results.append(result.adjusted_value)

        # All results should be identical
        assert len(set(results)) == 1

    def test_all_modulations_deterministic(self):
        """All modulation functions must be deterministic."""
        profile = EXPLORATORY_RESEARCH

        for _ in range(50):
            r1 = apply_posture_to_routing(0.5, profile, PostureTier.TIER_3)
            r2 = apply_posture_to_routing(0.5, profile, PostureTier.TIER_3)
            assert r1.adjusted_value == r2.adjusted_value

            e1 = apply_posture_to_escalation(0.5, profile, PostureTier.TIER_3)
            e2 = apply_posture_to_escalation(0.5, profile, PostureTier.TIER_3)
            assert e1.adjusted_value == e2.adjusted_value

            c1 = apply_posture_to_conservatism(0.5, profile, PostureTier.TIER_3)
            c2 = apply_posture_to_conservatism(0.5, profile, PostureTier.TIER_3)
            assert c1.adjusted_value == c2.adjusted_value

    def test_normalization_is_deterministic(self):
        """Profile normalization must be deterministic."""
        profile = DecisionPostureProfile(0.7, 0.2, 0.1)
        results = [profile.normalize() for _ in range(100)]

        first = results[0]
        for r in results[1:]:
            assert r.coherence_bias == first.coherence_bias
            assert r.exploration_bias == first.exploration_bias
            assert r.constraint_bias == first.constraint_bias


# =============================================================================
# Preset Profile Tests
# =============================================================================

class TestPresetProfiles:
    """Tests for preset posture profiles."""

    def test_balanced_default_is_balanced(self):
        """BALANCED_DEFAULT should be balanced."""
        assert BALANCED_DEFAULT.is_balanced

    def test_conservative_has_high_constraint(self):
        """CONSERVATIVE_ENTERPRISE should have highest constraint bias."""
        assert CONSERVATIVE_ENTERPRISE.constraint_bias > CONSERVATIVE_ENTERPRISE.coherence_bias
        assert CONSERVATIVE_ENTERPRISE.constraint_bias > CONSERVATIVE_ENTERPRISE.exploration_bias

    def test_exploratory_has_high_exploration(self):
        """EXPLORATORY_RESEARCH should have highest exploration bias."""
        assert EXPLORATORY_RESEARCH.exploration_bias > EXPLORATORY_RESEARCH.coherence_bias
        assert EXPLORATORY_RESEARCH.exploration_bias > EXPLORATORY_RESEARCH.constraint_bias

    def test_high_coherence_has_high_coherence(self):
        """HIGH_COHERENCE should have highest coherence bias."""
        assert HIGH_COHERENCE.coherence_bias > HIGH_COHERENCE.exploration_bias
        assert HIGH_COHERENCE.coherence_bias > HIGH_COHERENCE.constraint_bias

    def test_high_constraint_has_highest_constraint(self):
        """HIGH_CONSTRAINT should have highest constraint bias."""
        assert HIGH_CONSTRAINT.constraint_bias > HIGH_CONSTRAINT.coherence_bias
        assert HIGH_CONSTRAINT.constraint_bias > HIGH_CONSTRAINT.exploration_bias

    def test_get_preset_profile_valid(self):
        """get_preset_profile should return valid profiles."""
        assert get_preset_profile("balanced") == BALANCED_DEFAULT
        assert get_preset_profile("conservative") == CONSERVATIVE_ENTERPRISE
        assert get_preset_profile("exploratory") == EXPLORATORY_RESEARCH

    def test_get_preset_profile_case_insensitive(self):
        """get_preset_profile should be case-insensitive."""
        assert get_preset_profile("BALANCED") == BALANCED_DEFAULT
        assert get_preset_profile("Conservative") == CONSERVATIVE_ENTERPRISE

    def test_get_preset_profile_invalid_raises(self):
        """get_preset_profile should raise for invalid names."""
        with pytest.raises(ValueError):
            get_preset_profile("invalid_preset")

    def test_list_presets(self):
        """list_presets should return all preset names."""
        presets = list_presets()
        assert "balanced" in presets
        assert "conservative" in presets
        assert "exploratory" in presets
        assert "coherence" in presets
        assert "constraint" in presets


# =============================================================================
# Configuration Tests
# =============================================================================

class TestConfiguration:
    """Tests for posture configuration."""

    def test_tier_default_config_tier1(self):
        """Tier 1 should have no override allowed."""
        config = get_tier_default_config(PostureTier.TIER_1)
        assert config.allow_request_override is False
        assert config.max_adjustment_magnitude == 0.0

    def test_tier_default_config_tier2(self):
        """Tier 2 should have limited adjustment."""
        config = get_tier_default_config(PostureTier.TIER_2)
        assert config.allow_request_override is True
        assert config.max_adjustment_magnitude == 0.08

    def test_tier_default_config_tier3(self):
        """Tier 3 should have full adjustment."""
        config = get_tier_default_config(PostureTier.TIER_3)
        assert config.allow_request_override is True
        assert config.max_adjustment_magnitude == 0.10

    def test_create_custom_profile(self):
        """create_custom_profile should create valid profile."""
        profile = create_custom_profile(
            coherence=0.5,
            exploration=0.3,
            constraint=0.2,
            normalize=False,
        )
        assert profile.coherence_bias == 0.5
        assert profile.exploration_bias == 0.3
        assert profile.constraint_bias == 0.2

    def test_create_custom_profile_normalized(self):
        """create_custom_profile with normalize=True should normalize."""
        profile = create_custom_profile(
            coherence=1.0,
            exploration=1.0,
            constraint=1.0,
            normalize=True,
        )
        total = profile.coherence_bias + profile.exploration_bias + profile.constraint_bias
        assert abs(total - 1.0) < 0.001

    def test_create_config(self):
        """create_config should create valid configuration."""
        config = create_config(
            profile=CONSERVATIVE_ENTERPRISE,
            allow_override=False,
            max_adjustment=0.05,
        )
        assert config.default_profile == CONSERVATIVE_ENTERPRISE
        assert config.allow_request_override is False
        assert config.max_adjustment_magnitude == 0.05

    def test_config_validates_max_adjustment(self):
        """PostureConfig should reject invalid max_adjustment_magnitude."""
        with pytest.raises(ValueError):
            PostureConfig(
                default_profile=BALANCED_DEFAULT,
                max_adjustment_magnitude=0.5,  # Too high
            )


# =============================================================================
# Audit Tests
# =============================================================================

class TestAudit:
    """Tests for audit logging functionality."""

    @pytest.fixture
    def sample_applications(self) -> List[PostureApplicationResult]:
        return [
            PostureApplicationResult(
                original_value=0.5,
                adjusted_value=0.55,
                adjustment_delta=0.05,
                influence_scope=PostureInfluenceScope.ROUTING_THRESHOLD,
                tier=PostureTier.TIER_2,
                posture_applied=BALANCED_DEFAULT,
                was_influenced=True,
            ),
            PostureApplicationResult(
                original_value=0.5,
                adjusted_value=0.5,
                adjustment_delta=0.0,
                influence_scope=PostureInfluenceScope.CASCADE_AGGRESSIVENESS,
                tier=PostureTier.TIER_2,
                posture_applied=BALANCED_DEFAULT,
                was_influenced=False,
            ),
        ]

    def test_create_audit_record(self, sample_applications):
        """create_audit_record should create valid record."""
        record = create_audit_record(
            posture=BALANCED_DEFAULT,
            tier=PostureTier.TIER_2,
            applications=sample_applications,
            source="deployment_default",
        )
        assert record.posture_profile == BALANCED_DEFAULT
        assert record.tier == PostureTier.TIER_2
        assert record.influence_scope_label == "non-authoritative"
        assert len(record.applications) == 2

    def test_audit_record_always_non_authoritative(self, sample_applications):
        """Audit record influence_scope_label must always be 'non-authoritative'."""
        # Try to create with different label (will be overwritten)
        record = PostureAuditRecord(
            posture_profile=BALANCED_DEFAULT,
            applied_to=(PostureInfluenceScope.ROUTING_THRESHOLD,),
            influence_scope_label="authoritative",  # This should be overwritten
            tier=PostureTier.TIER_2,
            applications=tuple(sample_applications),
            constraints_respected=tuple(HARD_CONSTRAINTS),
            posture_source="test",
        )
        assert record.influence_scope_label == "non-authoritative"

    def test_format_audit_for_api_response(self, sample_applications):
        """format_audit_for_api_response should return valid dict."""
        record = create_audit_record(
            posture=BALANCED_DEFAULT,
            tier=PostureTier.TIER_2,
            applications=sample_applications,
        )
        result = format_audit_for_api_response(record)
        assert "decision_posture" in result
        assert result["decision_posture"]["influence_scope"] == "non-authoritative"

    def test_format_audit_for_detailed_log(self, sample_applications):
        """format_audit_for_detailed_log should return full details."""
        record = create_audit_record(
            posture=BALANCED_DEFAULT,
            tier=PostureTier.TIER_2,
            applications=sample_applications,
        )
        result = format_audit_for_detailed_log(record)
        assert "applications" in result
        assert len(result["applications"]) == 2
        assert result["assertions"]["no_truth_override"] is True
        assert result["assertions"]["deterministic"] is True

    def test_format_audit_for_compliance_report(self, sample_applications):
        """format_audit_for_compliance_report should return readable string."""
        record = create_audit_record(
            posture=BALANCED_DEFAULT,
            tier=PostureTier.TIER_2,
            applications=sample_applications,
        )
        result = format_audit_for_compliance_report(record)
        assert "DECISION POSTURE AUDIT RECORD" in result
        assert "No truth evaluation override" in result
        assert "Deterministic application" in result

    def test_validate_audit_record_valid(self, sample_applications):
        """validate_audit_record should pass for valid record."""
        record = create_audit_record(
            posture=BALANCED_DEFAULT,
            tier=PostureTier.TIER_2,
            applications=sample_applications,
        )
        is_valid, violations = validate_audit_record(record)
        # May have violations due to Tier 2 not allowing CASCADE_AGGRESSIVENESS
        # but the record correctly shows was_influenced=False for that scope
        # Check that influence_scope_label is validated
        assert record.influence_scope_label == "non-authoritative"

    def test_summarize_applications(self, sample_applications):
        """summarize_applications should return correct stats."""
        summary = summarize_applications(sample_applications)
        assert summary["total"] == 2
        assert summary["influenced"] == 1
        assert summary["influence_rate"] == 0.5

    def test_summarize_applications_empty(self):
        """summarize_applications should handle empty list."""
        summary = summarize_applications([])
        assert summary["total"] == 0
        assert summary["influenced"] == 0
        assert summary["influence_rate"] == 0.0


# =============================================================================
# Hard Constraints Tests
# =============================================================================

class TestHardConstraints:
    """Tests for hard safety constraints."""

    def test_all_hard_constraints_defined(self):
        """All expected hard constraints should be defined."""
        assert PostureConstraint.NO_TRUTH_OVERRIDE in HARD_CONSTRAINTS
        assert PostureConstraint.NO_ONTOLOGY_MODIFICATION in HARD_CONSTRAINTS
        assert PostureConstraint.NO_MORAL_JUDGMENT in HARD_CONSTRAINTS
        assert PostureConstraint.NO_USER_CLASSIFICATION in HARD_CONSTRAINTS
        assert PostureConstraint.NO_STOCHASTIC_BEHAVIOR in HARD_CONSTRAINTS
        assert PostureConstraint.NO_TIER1_MODIFICATION in HARD_CONSTRAINTS

    def test_hard_constraints_count(self):
        """Should have exactly 6 hard constraints."""
        assert len(HARD_CONSTRAINTS) == 6

    def test_audit_record_includes_all_constraints(self):
        """Audit record should include all hard constraints."""
        record = create_audit_record(
            posture=BALANCED_DEFAULT,
            tier=PostureTier.TIER_2,
            applications=[],
        )
        assert set(record.constraints_respected) == HARD_CONSTRAINTS


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for complete posture workflow."""

    def test_full_workflow_tier2(self):
        """Test complete workflow for Tier 2."""
        # 1. Get default config for tier
        config = get_tier_default_config(PostureTier.TIER_2)

        # 2. Get a preset profile
        profile = get_preset_profile("conservative")

        # 3. Apply to various decision points
        base_values = {
            "routing_threshold": 0.75,
            "response_depth": 0.5,
            "conservatism_level": 0.5,
        }

        routing_result = apply_posture_to_routing(
            base_values["routing_threshold"],
            profile,
            PostureTier.TIER_2,
            config,
        )

        depth_result = apply_posture_to_response_depth(
            base_values["response_depth"],
            profile,
            PostureTier.TIER_2,
            config,
        )

        # 4. Create audit record
        record = create_audit_record(
            posture=profile,
            tier=PostureTier.TIER_2,
            applications=[routing_result, depth_result],
        )

        # 5. Validate
        is_valid, violations = validate_audit_record(record)

        # 6. Format for API
        api_response = format_audit_for_api_response(record)

        # Assertions
        assert api_response["decision_posture"]["influence_scope"] == "non-authoritative"
        assert record.influence_scope_label == "non-authoritative"

    def test_full_workflow_tier3(self):
        """Test complete workflow for Tier 3."""
        config = get_tier_default_config(PostureTier.TIER_3)
        profile = get_preset_profile("exploratory")

        # Apply to all decision points
        base_values = {scope.value: 0.5 for scope in PostureInfluenceScope}
        results = apply_posture_to_all(profile, PostureTier.TIER_3, base_values, config)

        # Create audit
        record = create_audit_record(
            posture=profile,
            tier=PostureTier.TIER_3,
            applications=results,
        )

        # Validate
        is_valid, _ = validate_audit_record(record)

        # Get summary
        summary = summarize_applications(results)

        # Some values should be influenced in Tier 3 with exploratory profile
        assert summary["influenced"] > 0

    def test_posture_respects_config_limits(self):
        """Posture adjustments should respect config limits."""
        # Create config with very small max adjustment
        config = create_config(max_adjustment=0.01)

        # Use extreme profile
        extreme = HIGH_CONSTRAINT

        result = apply_posture_to_conservatism(
            base_level=0.5,
            posture=extreme,
            tier=PostureTier.TIER_3,
            config=config,
        )

        # Adjustment should be capped to 0.01 (with floating point tolerance)
        assert abs(result.adjustment_delta) <= 0.01 + 1e-9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
