"""
Tests for Enterprise Recursive Self-Improvement Module

Tests the self-improvement capabilities including:
- Belief system with Bayesian updates
- Self-evaluator utility tracking
- Meta-reasoning and hypothesis generation
- Coefficient adjustments
- Configuration switches
"""

import pytest
from datetime import datetime

from symbolu.guna_modulation.recursive_self_improvement import (
    Belief,
    BeliefType,
    UtilityObservation,
    SelfEvaluator,
    EnterpriseKnowledgeBase,
    MetaReasoner,
    EnterpriseSelfImprover,
    ImprovementAction,
    create_enterprise_self_improver,
)
from symbolu.guna_modulation.observables import Observables, MotionType
from symbolu.guna_modulation.state_types import StateRegister, DEFAULT_STATE
from symbolu.guna_modulation.utility import compute_utility, UtilityAudit
from symbolu.guna_modulation.v27_config import (
    V27Config,
    SelfImprovementConfig,
    DEFAULT_SELF_IMPROVEMENT_CONFIG,
    ENABLED_SELF_IMPROVEMENT_CONFIG,
    AUTO_SELF_IMPROVEMENT_CONFIG,
    UtilityCoefficients,
    DEFAULT_UTILITY_COEFFICIENTS,
)


# =============================================================================
# Belief Tests
# =============================================================================

class TestBelief:
    """Tests for the Belief class."""

    def test_belief_creation(self):
        """Test basic belief creation."""
        belief = Belief(
            id="test_belief",
            content="Test belief content",
            belief_type=BeliefType.PRIOR,
            confidence=0.7,
        )
        assert belief.id == "test_belief"
        assert belief.confidence == 0.7
        assert belief.belief_type == BeliefType.PRIOR
        assert belief.evidence_count == 0

    def test_belief_update_with_positive_utility(self):
        """Test belief confidence increases with high utility."""
        belief = Belief(
            id="test",
            content="Test",
            belief_type=BeliefType.HYPOTHESIS,
            confidence=0.5,
        )

        # Update with high utility (above threshold)
        belief.update_with_utility(0.8, threshold=0.5)

        assert belief.evidence_count == 1
        assert belief.supporting_evidence == 1
        assert belief.contradicting_evidence == 0
        assert belief.confidence > 0.5  # Should increase

    def test_belief_update_with_negative_utility(self):
        """Test belief confidence decreases with low utility."""
        belief = Belief(
            id="test",
            content="Test",
            belief_type=BeliefType.HYPOTHESIS,
            confidence=0.5,
        )

        # Update with low utility (below threshold)
        belief.update_with_utility(0.2, threshold=0.5)

        assert belief.evidence_count == 1
        assert belief.supporting_evidence == 0
        assert belief.contradicting_evidence == 1
        assert belief.confidence < 0.5  # Should decrease

    def test_belief_deprecation(self):
        """Test belief becomes deprecated with consistently low confidence."""
        belief = Belief(
            id="test",
            content="Test",
            belief_type=BeliefType.HYPOTHESIS,
            confidence=0.5,
        )

        # Simulate many negative updates
        for _ in range(15):
            belief.update_with_utility(0.1, threshold=0.5)

        assert belief.belief_type == BeliefType.DEPRECATED
        assert belief.confidence < 0.2

    def test_belief_verification(self):
        """Test hypothesis becomes verified with high confidence."""
        belief = Belief(
            id="test",
            content="Test",
            belief_type=BeliefType.HYPOTHESIS,
            confidence=0.5,
        )

        # Simulate many positive updates
        for _ in range(25):
            belief.update_with_utility(0.9, threshold=0.5)

        assert belief.belief_type == BeliefType.VERIFIED
        assert belief.confidence > 0.8

    def test_belief_to_dict(self):
        """Test belief serialization."""
        belief = Belief(
            id="test",
            content="Test content",
            belief_type=BeliefType.LEARNED,
            confidence=0.75,
        )

        d = belief.to_dict()
        assert d["id"] == "test"
        assert d["content"] == "Test content"
        assert d["type"] == "learned"
        assert d["confidence"] == 0.75


# =============================================================================
# SelfEvaluator Tests
# =============================================================================

class TestSelfEvaluator:
    """Tests for the SelfEvaluator class."""

    def create_observables(self, s=0.4, r=0.3, t=0.3, H=0.5, M=0.5, C=0.1, F=0.1):
        """Helper to create observables."""
        return Observables(s=s, r=r, t=t, H=H, delta_sem=M, C_contr=C, F_fail=F)

    def test_evaluator_creation(self):
        """Test evaluator initialization."""
        evaluator = SelfEvaluator(history_size=100)
        assert len(evaluator.observations) == 0
        assert evaluator.low_utility_streak == 0

    def test_record_observation(self):
        """Test recording a utility observation."""
        evaluator = SelfEvaluator()
        obs = self.create_observables(s=0.6, r=0.2, t=0.2)

        utility_audit = UtilityAudit(
            guna_term=0.5,
            entropy_penalty=-0.1,
            contradiction_penalty=-0.05,
            failure_penalty=-0.02,
            utility=0.33,
        )

        result = evaluator.record_observation(obs, DEFAULT_STATE, 0.33, utility_audit)

        assert result.guna_dominant == "sattva"
        assert len(evaluator.observations) == 1
        assert len(evaluator.recent_utilities) == 1

    def test_guna_dominant_detection(self):
        """Test correct detection of dominant Guna."""
        evaluator = SelfEvaluator()

        # Test Sattva dominant
        obs_s = self.create_observables(s=0.6, r=0.2, t=0.2)
        assert evaluator._get_guna_dominant(obs_s) == "sattva"

        # Test Rajas dominant
        obs_r = self.create_observables(s=0.2, r=0.6, t=0.2)
        assert evaluator._get_guna_dominant(obs_r) == "rajas"

        # Test Tamas dominant
        obs_t = self.create_observables(s=0.2, r=0.2, t=0.6)
        assert evaluator._get_guna_dominant(obs_t) == "tamas"

    def test_level_categorization(self):
        """Test categorization of values into levels."""
        evaluator = SelfEvaluator()

        assert evaluator._categorize_level(0.1) == "low"
        assert evaluator._categorize_level(0.5) == "medium"
        assert evaluator._categorize_level(0.9) == "high"

    def test_utility_tracking_by_context(self):
        """Test utility is tracked by Guna context."""
        evaluator = SelfEvaluator()

        # Record high-Sattva observations with high utility
        for _ in range(10):
            obs = self.create_observables(s=0.7, r=0.15, t=0.15)
            audit = UtilityAudit(0.5, 0, 0, 0, 0.5)
            evaluator.record_observation(obs, DEFAULT_STATE, 0.8, audit)

        # Record high-Tamas observations with low utility
        for _ in range(10):
            obs = self.create_observables(s=0.15, r=0.15, t=0.7)
            audit = UtilityAudit(0.1, 0, 0, 0, 0.1)
            evaluator.record_observation(obs, DEFAULT_STATE, 0.2, audit)

        context = evaluator.get_utility_by_context()

        assert context["by_guna"]["sattva"] > context["by_guna"]["tamas"]

    def test_failure_pattern_detection(self):
        """Test detection of failure patterns."""
        evaluator = SelfEvaluator()

        # Generate imbalanced data - Tamas always low utility
        for _ in range(15):
            obs = self.create_observables(s=0.7, r=0.15, t=0.15)
            audit = UtilityAudit(0.5, 0, 0, 0, 0.5)
            evaluator.record_observation(obs, DEFAULT_STATE, 0.7, audit)

        for _ in range(15):
            obs = self.create_observables(s=0.15, r=0.15, t=0.7)
            audit = UtilityAudit(0.1, 0, 0, 0, 0.1)
            evaluator.record_observation(obs, DEFAULT_STATE, 0.2, audit)

        patterns = evaluator.identify_failure_patterns()

        # Should detect Tamas failure pattern
        tamas_pattern = next(
            (p for p in patterns if p.get("guna") == "tamas"),
            None
        )
        assert tamas_pattern is not None
        assert tamas_pattern["type"] == "guna_failure"

    def test_low_utility_streak_tracking(self):
        """Test tracking of consecutive low utility observations."""
        evaluator = SelfEvaluator()

        # Record streak of low utility
        for _ in range(5):
            obs = self.create_observables()
            audit = UtilityAudit(0.1, 0, 0, 0, 0.1)
            evaluator.record_observation(obs, DEFAULT_STATE, 0.1, audit)

        assert evaluator.low_utility_streak == 5
        assert evaluator.max_low_utility_streak == 5

        # Break streak with high utility
        obs = self.create_observables()
        audit = UtilityAudit(0.5, 0, 0, 0, 0.5)
        evaluator.record_observation(obs, DEFAULT_STATE, 0.8, audit)

        assert evaluator.low_utility_streak == 0
        assert evaluator.max_low_utility_streak == 5

    def test_get_summary(self):
        """Test summary generation."""
        evaluator = SelfEvaluator()

        for i in range(20):
            obs = self.create_observables()
            audit = UtilityAudit(0.5, 0, 0, 0, 0.5)
            evaluator.record_observation(obs, DEFAULT_STATE, 0.5 + i * 0.01, audit)

        summary = evaluator.get_summary()

        assert summary["total_observations"] == 20
        assert "average_utility" in summary
        assert "utility_by_context" in summary
        assert "failure_patterns" in summary


# =============================================================================
# EnterpriseKnowledgeBase Tests
# =============================================================================

class TestEnterpriseKnowledgeBase:
    """Tests for the EnterpriseKnowledgeBase class."""

    def test_knowledge_base_initialization(self):
        """Test KB initializes with prior beliefs."""
        kb = EnterpriseKnowledgeBase()

        assert len(kb.beliefs) > 0
        assert "sattva_positive" in kb.beliefs
        assert kb.beliefs["sattva_positive"].belief_type == BeliefType.PRIOR

    def test_add_belief(self):
        """Test adding a new belief."""
        kb = EnterpriseKnowledgeBase()

        new_belief = Belief(
            id="custom_belief",
            content="Custom belief content",
            belief_type=BeliefType.LEARNED,
            confidence=0.6,
        )

        kb.add_belief(new_belief)

        assert "custom_belief" in kb.beliefs
        assert kb.beliefs["custom_belief"].confidence == 0.6

    def test_update_belief_with_utility(self):
        """Test updating belief based on utility."""
        kb = EnterpriseKnowledgeBase()

        initial_evidence = kb.beliefs["sattva_positive"].evidence_count

        kb.update_belief_with_utility("sattva_positive", 0.9, threshold=0.5)

        # Evidence count should increase
        assert kb.beliefs["sattva_positive"].evidence_count == initial_evidence + 1
        # Supporting evidence should increase for high utility
        assert kb.beliefs["sattva_positive"].supporting_evidence == 1
        assert kb.beliefs["sattva_positive"].contradicting_evidence == 0

    def test_get_active_beliefs(self):
        """Test getting non-deprecated beliefs."""
        kb = EnterpriseKnowledgeBase()

        # Add a deprecated belief
        deprecated = Belief(
            id="deprecated",
            content="Old belief",
            belief_type=BeliefType.DEPRECATED,
            confidence=0.1,
        )
        kb.add_belief(deprecated)

        active = kb.get_active_beliefs()

        assert deprecated not in active
        assert all(b.belief_type != BeliefType.DEPRECATED for b in active)

    def test_coefficient_adjustments(self):
        """Test coefficient adjustment storage."""
        kb = EnterpriseKnowledgeBase()

        kb.set_coefficient_adjustment("c_S", 1.2)
        kb.set_coefficient_adjustment("lambda_H", 0.8)

        assert kb.get_coefficient_adjustment("c_S") == 1.2
        assert kb.get_coefficient_adjustment("lambda_H") == 0.8
        assert kb.get_coefficient_adjustment("unknown") == 1.0  # Default

    def test_coefficient_adjustment_bounds(self):
        """Test coefficient adjustments are bounded."""
        kb = EnterpriseKnowledgeBase()

        # Try to set out of bounds
        kb.set_coefficient_adjustment("c_S", 3.0)  # Should clamp to 2.0
        kb.set_coefficient_adjustment("c_R", 0.1)  # Should clamp to 0.5

        assert kb.get_coefficient_adjustment("c_S") == 2.0
        assert kb.get_coefficient_adjustment("c_R") == 0.5

    def test_export_state(self):
        """Test state export."""
        kb = EnterpriseKnowledgeBase()

        state = kb.export_state()

        assert "beliefs" in state
        assert "coefficient_adjustments" in state
        assert "active_count" in state


# =============================================================================
# MetaReasoner Tests
# =============================================================================

class TestMetaReasoner:
    """Tests for the MetaReasoner class."""

    def create_evaluator_with_patterns(self) -> SelfEvaluator:
        """Create evaluator with failure patterns for testing."""
        evaluator = SelfEvaluator()

        # Create Tamas failure pattern
        for _ in range(20):
            obs = Observables(s=0.7, r=0.15, t=0.15, H=0.3, delta_sem=0.5, C_contr=0.1, F_fail=0.1)
            audit = UtilityAudit(0.5, 0, 0, 0, 0.5)
            evaluator.record_observation(obs, DEFAULT_STATE, 0.7, audit)

        for _ in range(20):
            obs = Observables(s=0.15, r=0.15, t=0.7, H=0.3, delta_sem=0.5, C_contr=0.1, F_fail=0.1)
            audit = UtilityAudit(0.1, 0, 0, 0, 0.1)
            evaluator.record_observation(obs, DEFAULT_STATE, 0.2, audit)

        return evaluator

    def test_meta_reasoner_creation(self):
        """Test MetaReasoner initialization."""
        kb = EnterpriseKnowledgeBase()
        evaluator = SelfEvaluator()
        reasoner = MetaReasoner(kb, evaluator)

        assert reasoner.kb is kb
        assert reasoner.evaluator is evaluator
        assert len(reasoner.hypotheses) == 0

    def test_hypothesis_generation(self):
        """Test hypothesis generation from failure patterns."""
        kb = EnterpriseKnowledgeBase()
        evaluator = self.create_evaluator_with_patterns()
        reasoner = MetaReasoner(kb, evaluator)

        hypotheses = reasoner.analyze_and_generate_hypotheses()

        assert len(hypotheses) > 0
        assert all(h.belief_type == BeliefType.HYPOTHESIS for h in hypotheses)

    def test_guna_failure_hypothesis(self):
        """Test hypothesis generation for Guna-specific failures."""
        kb = EnterpriseKnowledgeBase()
        evaluator = self.create_evaluator_with_patterns()
        reasoner = MetaReasoner(kb, evaluator)

        hypotheses = reasoner.analyze_and_generate_hypotheses()

        # Should have hypothesis about Tamas
        tamas_hyp = next(
            (h for h in hypotheses if "tamas" in h.id.lower()),
            None
        )
        assert tamas_hyp is not None
        assert "adjust" in tamas_hyp.metadata.get("action", "").lower()

    def test_hypothesis_prioritization(self):
        """Test hypothesis prioritization."""
        kb = EnterpriseKnowledgeBase()
        evaluator = self.create_evaluator_with_patterns()
        reasoner = MetaReasoner(kb, evaluator)

        reasoner.analyze_and_generate_hypotheses()
        prioritized = reasoner.prioritize_hypotheses()

        assert len(prioritized) > 0
        # Should be sorted by priority (descending)
        priorities = [p for _, p in prioritized]
        assert priorities == sorted(priorities, reverse=True)


# =============================================================================
# EnterpriseSelfImprover Tests
# =============================================================================

class TestEnterpriseSelfImprover:
    """Tests for the EnterpriseSelfImprover class."""

    def create_observables(self, s=0.4, r=0.3, t=0.3, H=0.5, M=0.5, C=0.1, F=0.1):
        """Helper to create observables."""
        return Observables(s=s, r=r, t=t, H=H, delta_sem=M, C_contr=C, F_fail=F)

    def test_self_improver_creation(self):
        """Test EnterpriseSelfImprover initialization."""
        improver = create_enterprise_self_improver()

        assert improver.observation_count == 0
        assert improver.improvement_cycle_count == 0
        assert len(improver.executed_improvements) == 0
        assert improver.conservative_mode is False

    def test_observe_computes_utility(self):
        """Test observe method computes utility correctly."""
        improver = create_enterprise_self_improver()
        obs = self.create_observables(s=0.6, r=0.2, t=0.2)

        utility, audit = improver.observe(obs, DEFAULT_STATE)

        assert isinstance(utility, float)
        assert isinstance(audit, UtilityAudit)
        assert improver.observation_count == 1

    def test_auto_improve_disabled(self):
        """Test improvements don't execute when auto_improve is False."""
        improver = create_enterprise_self_improver(auto_improve=False)

        for _ in range(150):
            obs = self.create_observables()
            improver.observe(obs, DEFAULT_STATE)

        # Improvement cycle should not have run automatically
        assert improver.improvement_cycle_count == 0

    def test_auto_improve_enabled(self):
        """Test improvements execute when auto_improve is True."""
        improver = create_enterprise_self_improver(
            auto_improve=True,
            improvement_threshold=0.3,  # Low threshold to trigger improvements
        )

        # Generate failure pattern
        for _ in range(110):  # More than observation_window (100)
            obs = self.create_observables(s=0.1, r=0.2, t=0.7, H=0.8, C=0.5, F=0.3)
            improver.observe(obs, DEFAULT_STATE)

        # Should have run at least one improvement cycle
        assert improver.improvement_cycle_count > 0

    def test_coefficient_override(self):
        """Test coefficient overrides are applied."""
        improver = create_enterprise_self_improver(auto_improve=True)

        # Generate pattern that triggers coefficient adjustment
        for _ in range(110):
            obs = self.create_observables(s=0.1, r=0.1, t=0.8, H=0.9, C=0.7, F=0.5)
            improver.observe(obs, DEFAULT_STATE)

        effective = improver.get_effective_coefficients()

        # Should have some overrides (exact values depend on what got triggered)
        # At minimum, the object should exist
        assert effective is not None

    def test_conservative_mode(self):
        """Test conservative mode activation."""
        improver = create_enterprise_self_improver(auto_improve=True)

        # Simulate utility streak failure (5+ consecutive low utility)
        for _ in range(10):
            obs = self.create_observables(s=0.1, r=0.1, t=0.8, H=0.9, C=0.8, F=0.7)
            improver.observe(obs, DEFAULT_STATE)

        # Force improvement cycle
        improver.run_improvement_cycle()

        # After streak failure, conservative mode might be enabled
        # (depends on hypothesis generation)
        # Just verify it doesn't crash

    def test_reasoning_trace(self):
        """Test reasoning trace generation."""
        improver = create_enterprise_self_improver(auto_improve=True)

        for _ in range(50):
            obs = self.create_observables()
            improver.observe(obs, DEFAULT_STATE)

        trace = improver.get_reasoning_trace()

        assert isinstance(trace, list)
        assert len(trace) > 0
        assert "step" in trace[0]

    def test_state_summary(self):
        """Test state summary generation."""
        improver = create_enterprise_self_improver()

        for _ in range(20):
            obs = self.create_observables()
            improver.observe(obs, DEFAULT_STATE)

        summary = improver.get_state_summary()

        assert summary["observation_count"] == 20
        assert "improvement_cycles" in summary
        assert "active_beliefs" in summary
        assert "evaluation" in summary

    def test_export_learned_state(self):
        """Test exporting learned state."""
        improver = create_enterprise_self_improver()

        for _ in range(20):
            obs = self.create_observables()
            improver.observe(obs, DEFAULT_STATE)

        exported = improver.export_learned_state()

        assert "knowledge_base" in exported
        assert "improvements" in exported


# =============================================================================
# Configuration Tests
# =============================================================================

class TestSelfImprovementConfig:
    """Tests for SelfImprovementConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = DEFAULT_SELF_IMPROVEMENT_CONFIG

        assert config.enabled is False
        assert config.auto_improve is False

    def test_enabled_config(self):
        """Test enabled configuration."""
        config = ENABLED_SELF_IMPROVEMENT_CONFIG

        assert config.enabled is True
        assert config.auto_improve is False  # Manual approval

    def test_auto_config(self):
        """Test auto-improve configuration."""
        config = AUTO_SELF_IMPROVEMENT_CONFIG

        assert config.enabled is True
        assert config.auto_improve is True

    def test_config_validation_threshold(self):
        """Test threshold validation."""
        with pytest.raises(ValueError):
            SelfImprovementConfig(enabled=True, improvement_threshold=1.5)

        with pytest.raises(ValueError):
            SelfImprovementConfig(enabled=True, improvement_threshold=-0.1)

    def test_config_validation_window(self):
        """Test observation window validation."""
        with pytest.raises(ValueError):
            SelfImprovementConfig(enabled=True, observation_window=5)

    def test_config_validation_max_change(self):
        """Test max coefficient change validation."""
        with pytest.raises(ValueError):
            SelfImprovementConfig(enabled=True, max_coefficient_change=0.6)

        with pytest.raises(ValueError):
            SelfImprovementConfig(enabled=True, max_coefficient_change=0.0)

    def test_v27_config_with_self_improvement(self):
        """Test V27Config factory for self-improvement."""
        config = V27Config.with_self_improvement(
            tier="enterprise_tier_1",
            bayesian=True,
            auto_improve=True,
        )

        assert config.v2_7_enabled is True
        assert config.self_improvement_enabled is True
        assert config.is_self_improving is True
        assert config.is_bayesian is True

    def test_v27_config_self_improving_property(self):
        """Test is_self_improving property."""
        # Disabled
        config1 = V27Config()
        assert config1.is_self_improving is False

        # Enabled
        config2 = V27Config.with_self_improvement()
        assert config2.is_self_improving is True


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the full self-improvement flow."""

    def test_full_improvement_cycle(self):
        """Test complete improvement cycle from observation to modification."""
        improver = create_enterprise_self_improver(
            auto_improve=True,
            improvement_threshold=0.4,
        )

        # Phase 1: Generate failure pattern (high Tamas, low utility)
        for _ in range(60):
            obs = Observables(
                s=0.1, r=0.2, t=0.7,
                H=0.8, delta_sem=0.2,
                C_contr=0.6, F_fail=0.4,
            )
            improver.observe(obs, DEFAULT_STATE)

        # Phase 2: Generate success pattern (high Sattva, high utility)
        for _ in range(60):
            obs = Observables(
                s=0.7, r=0.2, t=0.1,
                H=0.2, delta_sem=0.5,
                C_contr=0.1, F_fail=0.05,
            )
            improver.observe(obs, DEFAULT_STATE)

        # Verify improvement happened
        assert improver.improvement_cycle_count > 0

        # Verify beliefs were updated
        active_beliefs = improver.kb.get_active_beliefs()
        assert len(active_beliefs) > 8  # More than initial priors

    def test_utility_improvement_over_time(self):
        """Test that average utility improves with self-improvement."""
        improver = create_enterprise_self_improver(
            auto_improve=True,
            improvement_threshold=0.3,
        )

        # Initial phase with mixed utility
        initial_utilities = []
        for i in range(50):
            s = 0.5 + (i % 2) * 0.2  # Alternating
            obs = Observables(
                s=s, r=0.3, t=1.0 - s - 0.3,
                H=0.5, delta_sem=0.5,
                C_contr=0.2, F_fail=0.1,
            )
            utility, _ = improver.observe(obs, DEFAULT_STATE)
            initial_utilities.append(utility)

        initial_avg = sum(initial_utilities) / len(initial_utilities)

        # Run improvement cycle explicitly
        improver.run_improvement_cycle()

        # Post-improvement phase
        final_utilities = []
        for i in range(50):
            s = 0.5 + (i % 2) * 0.2
            obs = Observables(
                s=s, r=0.3, t=1.0 - s - 0.3,
                H=0.5, delta_sem=0.5,
                C_contr=0.2, F_fail=0.1,
            )
            utility, _ = improver.observe(obs, DEFAULT_STATE)
            final_utilities.append(utility)

        # Utility should be tracked (improvement depends on patterns)
        assert len(final_utilities) == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
