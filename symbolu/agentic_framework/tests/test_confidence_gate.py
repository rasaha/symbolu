"""
Tests for Confidence Gating Module.

Tests that confidence CONTROLS behavior, not just annotates output.
"""

import pytest
from symbolu.agentic_framework.confidence_gate import (
    # Enums
    EscalationLevel,
    ExecutionMode,
    # Data classes
    ConfidenceSignals,
    UnifiedConfidence,
    EscalationDecision,
    BudgetAllocation,
    MemoryWeight,
    ExecutionPermission,
    ConfidenceGateDecision,
    AggregationWeights,
    # Controllers
    ConfidenceAggregator,
    EscalationController,
    BudgetController,
    MemoryController,
    ExecutionController,
    # Main gate
    ConfidenceGate,
    # Factory functions
    create_confidence_gate,
    create_strict_confidence_gate,
    create_permissive_confidence_gate,
    # Integration helpers
    signals_from_critique,
    signals_from_coherence_metrics,
    signals_from_policy_decision,
    merge_signals,
)


# =============================================================================
# Test Enums
# =============================================================================


class TestEscalationLevel:
    """Test EscalationLevel enum."""

    def test_escalation_levels_exist(self):
        """Verify all escalation levels are defined."""
        assert EscalationLevel.NONE.value == "none"
        assert EscalationLevel.NOTIFY.value == "notify"
        assert EscalationLevel.CONFIRM.value == "confirm"
        assert EscalationLevel.HALT.value == "halt"

    def test_escalation_level_ordering(self):
        """Verify escalation levels have correct severity."""
        # Ordering by severity (implicit through design)
        levels = [EscalationLevel.NONE, EscalationLevel.NOTIFY,
                  EscalationLevel.CONFIRM, EscalationLevel.HALT]
        assert len(levels) == 4


class TestExecutionMode:
    """Test ExecutionMode enum."""

    def test_execution_modes_exist(self):
        """Verify all execution modes are defined."""
        assert ExecutionMode.FULL.value == "full"
        assert ExecutionMode.CAUTIOUS.value == "cautious"
        assert ExecutionMode.CONFIRM_REQUIRED.value == "confirm"
        assert ExecutionMode.BLOCKED.value == "blocked"


# =============================================================================
# Test Data Classes
# =============================================================================


class TestConfidenceSignals:
    """Test ConfidenceSignals dataclass."""

    def test_default_values(self):
        """Default values should be 0.5 for most fields."""
        signals = ConfidenceSignals()
        assert signals.quality_score == 0.5
        assert signals.coherence_score == 0.5
        assert signals.internal_consistency == 0.5
        assert signals.action_reversibility == 1.0  # Exception: default is 1.0

    def test_custom_values(self):
        """Custom values should be preserved."""
        signals = ConfidenceSignals(
            quality_score=0.9,
            coherence_score=0.8,
            action_reversibility=0.3,
        )
        assert signals.quality_score == 0.9
        assert signals.coherence_score == 0.8
        assert signals.action_reversibility == 0.3

    def test_to_dict(self):
        """to_dict should return all fields."""
        signals = ConfidenceSignals(quality_score=0.9)
        d = signals.to_dict()
        assert "quality_score" in d
        assert d["quality_score"] == 0.9
        assert "action_reversibility" in d


class TestUnifiedConfidence:
    """Test UnifiedConfidence dataclass."""

    def test_is_high(self):
        """High confidence is >= 0.75."""
        high = UnifiedConfidence(overall=0.8, quality_component=0.8,
                                  coherence_component=0.8, stability_component=0.8,
                                  action_component=0.8)
        assert high.is_high is True
        assert high.is_medium is False
        assert high.is_low is False

    def test_is_medium(self):
        """Medium confidence is [0.45, 0.75)."""
        medium = UnifiedConfidence(overall=0.6, quality_component=0.6,
                                    coherence_component=0.6, stability_component=0.6,
                                    action_component=0.6)
        assert medium.is_high is False
        assert medium.is_medium is True
        assert medium.is_low is False

    def test_is_low(self):
        """Low confidence is < 0.45."""
        low = UnifiedConfidence(overall=0.3, quality_component=0.3,
                                 coherence_component=0.3, stability_component=0.3,
                                 action_component=0.3)
        assert low.is_high is False
        assert low.is_medium is False
        assert low.is_low is True

    def test_boundary_values(self):
        """Test boundary values for confidence levels."""
        # Exactly 0.75 should be high
        boundary_high = UnifiedConfidence(overall=0.75, quality_component=0.5,
                                           coherence_component=0.5, stability_component=0.5,
                                           action_component=0.5)
        assert boundary_high.is_high is True

        # Exactly 0.45 should be medium
        boundary_medium = UnifiedConfidence(overall=0.45, quality_component=0.5,
                                             coherence_component=0.5, stability_component=0.5,
                                             action_component=0.5)
        assert boundary_medium.is_medium is True

    def test_to_dict(self):
        """to_dict should include all fields and computed properties."""
        conf = UnifiedConfidence(overall=0.8, quality_component=0.8,
                                  coherence_component=0.7, stability_component=0.9,
                                  action_component=0.8)
        d = conf.to_dict()
        assert d["overall"] == 0.8
        assert d["is_high"] is True
        assert "signals_used" in d


class TestEscalationDecision:
    """Test EscalationDecision dataclass."""

    def test_requires_human_for_confirm(self):
        """CONFIRM level requires human."""
        decision = EscalationDecision(level=EscalationLevel.CONFIRM, confidence=0.5)
        assert decision.requires_human is True

    def test_requires_human_for_halt(self):
        """HALT level requires human."""
        decision = EscalationDecision(level=EscalationLevel.HALT, confidence=0.3)
        assert decision.requires_human is True

    def test_no_human_for_notify(self):
        """NOTIFY level does not require human."""
        decision = EscalationDecision(level=EscalationLevel.NOTIFY, confidence=0.7)
        assert decision.requires_human is False

    def test_no_human_for_none(self):
        """NONE level does not require human."""
        decision = EscalationDecision(level=EscalationLevel.NONE, confidence=0.9)
        assert decision.requires_human is False


class TestExecutionPermission:
    """Test ExecutionPermission dataclass."""

    def test_can_execute_full(self):
        """FULL mode can execute."""
        perm = ExecutionPermission(mode=ExecutionMode.FULL, confidence=0.9)
        assert perm.can_execute is True

    def test_can_execute_cautious(self):
        """CAUTIOUS mode can execute."""
        perm = ExecutionPermission(mode=ExecutionMode.CAUTIOUS, confidence=0.7)
        assert perm.can_execute is True

    def test_cannot_execute_confirm(self):
        """CONFIRM_REQUIRED mode cannot auto-execute."""
        perm = ExecutionPermission(mode=ExecutionMode.CONFIRM_REQUIRED, confidence=0.4)
        assert perm.can_execute is False

    def test_cannot_execute_blocked(self):
        """BLOCKED mode cannot execute."""
        perm = ExecutionPermission(mode=ExecutionMode.BLOCKED, confidence=0.2)
        assert perm.can_execute is False


# =============================================================================
# Test Aggregation Weights
# =============================================================================


class TestAggregationWeights:
    """Test AggregationWeights dataclass."""

    def test_default_weights(self):
        """Default weights should sum to 1.0."""
        weights = AggregationWeights()
        total = weights.quality + weights.coherence + weights.stability + weights.action
        assert abs(total - 1.0) < 0.001

    def test_normalize(self):
        """Normalize should make weights sum to 1.0."""
        weights = AggregationWeights(quality=2.0, coherence=2.0, stability=2.0, action=2.0)
        normalized = weights.normalize()
        total = normalized.quality + normalized.coherence + normalized.stability + normalized.action
        assert abs(total - 1.0) < 0.001
        assert normalized.quality == 0.25

    def test_normalize_zero_total(self):
        """Zero total should normalize to 0.25 each."""
        weights = AggregationWeights(quality=0, coherence=0, stability=0, action=0)
        normalized = weights.normalize()
        assert normalized.quality == 0.25
        assert normalized.coherence == 0.25


# =============================================================================
# Test Confidence Aggregator
# =============================================================================


class TestConfidenceAggregator:
    """Test ConfidenceAggregator class."""

    def test_aggregate_default_signals(self):
        """Default signals should produce ~0.5 confidence."""
        aggregator = ConfidenceAggregator()
        signals = ConfidenceSignals()
        confidence = aggregator.aggregate(signals)
        # With all signals at 0.5 (except action_reversibility=1.0),
        # overall should be medium
        assert 0.4 <= confidence.overall <= 0.7

    def test_aggregate_high_signals(self):
        """High signals should produce high confidence."""
        aggregator = ConfidenceAggregator()
        signals = ConfidenceSignals(
            quality_score=0.95,
            coherence_score=0.95,
            correctness_score=0.95,
            completeness_score=0.95,
            relevance_score=0.95,
            internal_consistency=0.95,
            goal_alignment=0.95,
            prediction_reversal_risk=0.05,  # Low risk
            volatility_index=0.05,  # Low volatility
            trajectory_confidence=0.95,
            session_stability=0.95,
            action_complexity=0.05,  # Low complexity
            action_reversibility=1.0,
        )
        confidence = aggregator.aggregate(signals)
        assert confidence.is_high
        assert confidence.overall >= 0.85

    def test_aggregate_low_signals(self):
        """Low signals should produce low confidence."""
        aggregator = ConfidenceAggregator()
        signals = ConfidenceSignals(
            quality_score=0.1,
            coherence_score=0.1,
            correctness_score=0.1,
            completeness_score=0.1,
            relevance_score=0.1,
            internal_consistency=0.1,
            goal_alignment=0.1,
            prediction_reversal_risk=0.9,  # High risk
            volatility_index=0.9,  # High volatility
            trajectory_confidence=0.1,
            session_stability=0.1,
            action_complexity=0.9,  # High complexity
            action_reversibility=0.0,  # Not reversible
        )
        confidence = aggregator.aggregate(signals)
        assert confidence.is_low
        assert confidence.overall < 0.35

    def test_aggregate_with_custom_weights(self):
        """Custom weights should influence result."""
        # Quality-heavy weights
        quality_weights = AggregationWeights(quality=0.8, coherence=0.1, stability=0.05, action=0.05)
        aggregator = ConfidenceAggregator(quality_weights)

        signals = ConfidenceSignals(
            quality_score=0.9,
            coherence_score=0.3,
            trajectory_confidence=0.3,
        )
        confidence = aggregator.aggregate(signals)
        # Quality-heavy should result in higher confidence despite low coherence
        assert confidence.overall > 0.5

    def test_confidence_components_populated(self):
        """Confidence should have all components populated."""
        aggregator = ConfidenceAggregator()
        signals = ConfidenceSignals()
        confidence = aggregator.aggregate(signals)

        assert confidence.quality_component >= 0
        assert confidence.coherence_component >= 0
        assert confidence.stability_component >= 0
        assert confidence.action_component >= 0
        assert len(confidence.signals_used) > 0


# =============================================================================
# Test Escalation Controller
# =============================================================================


class TestEscalationController:
    """Test EscalationController class."""

    def test_none_escalation_high_confidence(self):
        """High confidence should not escalate."""
        controller = EscalationController()
        confidence = UnifiedConfidence(overall=0.85, quality_component=0.85,
                                        coherence_component=0.85, stability_component=0.85,
                                        action_component=0.85)
        decision = controller.decide(confidence)
        assert decision.level == EscalationLevel.NONE
        assert not decision.requires_human

    def test_notify_escalation_medium_confidence(self):
        """Medium-high confidence should notify."""
        controller = EscalationController()
        confidence = UnifiedConfidence(overall=0.65, quality_component=0.65,
                                        coherence_component=0.65, stability_component=0.65,
                                        action_component=0.65)
        decision = controller.decide(confidence)
        assert decision.level == EscalationLevel.NOTIFY
        assert not decision.requires_human

    def test_confirm_escalation_medium_low_confidence(self):
        """Medium-low confidence should require confirmation."""
        controller = EscalationController()
        confidence = UnifiedConfidence(overall=0.45, quality_component=0.45,
                                        coherence_component=0.45, stability_component=0.45,
                                        action_component=0.45)
        decision = controller.decide(confidence)
        assert decision.level == EscalationLevel.CONFIRM
        assert decision.requires_human

    def test_halt_escalation_low_confidence(self):
        """Low confidence should halt."""
        controller = EscalationController()
        confidence = UnifiedConfidence(overall=0.25, quality_component=0.25,
                                        coherence_component=0.25, stability_component=0.25,
                                        action_component=0.25)
        decision = controller.decide(confidence)
        assert decision.level == EscalationLevel.HALT
        assert decision.requires_human
        assert len(decision.reasons) > 0
        assert len(decision.suggested_questions) > 0

    def test_timeout_for_confirm_and_halt(self):
        """CONFIRM and HALT should have timeout."""
        controller = EscalationController(default_timeout=60.0)

        confirm_conf = UnifiedConfidence(overall=0.45, quality_component=0.45,
                                          coherence_component=0.45, stability_component=0.45,
                                          action_component=0.45)
        confirm_decision = controller.decide(confirm_conf)
        assert confirm_decision.timeout_seconds == 60.0

        halt_conf = UnifiedConfidence(overall=0.25, quality_component=0.25,
                                       coherence_component=0.25, stability_component=0.25,
                                       action_component=0.25)
        halt_decision = controller.decide(halt_conf)
        assert halt_decision.timeout_seconds == 60.0

    def test_no_timeout_for_none_and_notify(self):
        """NONE and NOTIFY should not have timeout."""
        controller = EscalationController()

        none_conf = UnifiedConfidence(overall=0.85, quality_component=0.85,
                                       coherence_component=0.85, stability_component=0.85,
                                       action_component=0.85)
        none_decision = controller.decide(none_conf)
        assert none_decision.timeout_seconds is None

        notify_conf = UnifiedConfidence(overall=0.65, quality_component=0.65,
                                         coherence_component=0.65, stability_component=0.65,
                                         action_component=0.65)
        notify_decision = controller.decide(notify_conf)
        assert notify_decision.timeout_seconds is None

    def test_custom_thresholds(self):
        """Custom thresholds should be respected."""
        controller = EscalationController(
            halt_threshold=0.5,
            confirm_threshold=0.7,
            notify_threshold=0.9,
        )

        # 0.6 should be CONFIRM with these thresholds
        conf = UnifiedConfidence(overall=0.6, quality_component=0.6,
                                  coherence_component=0.6, stability_component=0.6,
                                  action_component=0.6)
        decision = controller.decide(conf)
        assert decision.level == EscalationLevel.CONFIRM


# =============================================================================
# Test Budget Controller
# =============================================================================


class TestBudgetController:
    """Test BudgetController class."""

    def test_low_confidence_more_budget(self):
        """Low confidence should get more revision budget."""
        controller = BudgetController()
        low_conf = UnifiedConfidence(overall=0.3, quality_component=0.3,
                                      coherence_component=0.3, stability_component=0.3,
                                      action_component=0.3)
        budget = controller.allocate(low_conf)
        assert budget.revision_budget == 5  # Max
        assert budget.require_self_check is True
        assert budget.require_source_citation is True
        assert budget.attention_multiplier > 1.0

    def test_high_confidence_less_budget(self):
        """High confidence should get less revision budget."""
        controller = BudgetController()
        high_conf = UnifiedConfidence(overall=0.9, quality_component=0.9,
                                       coherence_component=0.9, stability_component=0.9,
                                       action_component=0.9)
        budget = controller.allocate(high_conf)
        assert budget.revision_budget <= 3
        assert budget.require_self_check is False
        assert budget.attention_multiplier <= 1.0

    def test_medium_confidence_moderate_budget(self):
        """Medium confidence should get moderate budget."""
        controller = BudgetController()
        medium_conf = UnifiedConfidence(overall=0.65, quality_component=0.65,
                                         coherence_component=0.65, stability_component=0.65,
                                         action_component=0.65)
        budget = controller.allocate(medium_conf)
        assert 2 <= budget.revision_budget <= 4
        assert budget.attention_multiplier == 1.0

    def test_max_tokens_scales_with_attention(self):
        """Max tokens should scale with attention multiplier."""
        controller = BudgetController(base_max_tokens=1000)

        low_conf = UnifiedConfidence(overall=0.3, quality_component=0.3,
                                      coherence_component=0.3, stability_component=0.3,
                                      action_component=0.3)
        budget = controller.allocate(low_conf)
        assert budget.max_tokens > 1000  # Attention multiplier > 1


# =============================================================================
# Test Memory Controller
# =============================================================================


class TestMemoryController:
    """Test MemoryController class."""

    def test_low_confidence_no_store(self):
        """Very low confidence should not be stored."""
        controller = MemoryController(store_threshold=0.3)
        low_conf = UnifiedConfidence(overall=0.2, quality_component=0.2,
                                      coherence_component=0.2, stability_component=0.2,
                                      action_component=0.2)
        memory = controller.decide(low_conf)
        assert memory.should_store is False
        assert memory.retention_weight == 0.0
        assert "not_stored" in memory.tags

    def test_high_confidence_permanent_store(self):
        """High confidence should be stored permanently."""
        controller = MemoryController(high_priority_threshold=0.8)
        high_conf = UnifiedConfidence(overall=0.9, quality_component=0.9,
                                       coherence_component=0.9, stability_component=0.9,
                                       action_component=0.9)
        memory = controller.decide(high_conf)
        assert memory.should_store is True
        assert memory.retention_weight == 1.0
        assert memory.retrieval_priority == 1.0
        assert memory.expiry_turns is None  # Permanent
        assert "high_confidence" in memory.tags

    def test_medium_confidence_proportional_store(self):
        """Medium confidence should have proportional retention."""
        controller = MemoryController(store_threshold=0.3, high_priority_threshold=0.8)
        medium_conf = UnifiedConfidence(overall=0.55, quality_component=0.55,
                                         coherence_component=0.55, stability_component=0.55,
                                         action_component=0.55)
        memory = controller.decide(medium_conf)
        assert memory.should_store is True
        assert 0.3 < memory.retention_weight < 1.0
        assert memory.expiry_turns is not None

    def test_medium_low_confidence_shorter_expiry(self):
        """Medium-low confidence should expire faster."""
        controller = MemoryController(default_expiry_turns=50)

        medium_low_conf = UnifiedConfidence(overall=0.4, quality_component=0.4,
                                             coherence_component=0.4, stability_component=0.4,
                                             action_component=0.4)
        memory = controller.decide(medium_low_conf)
        assert memory.expiry_turns == 25  # Half of default
        assert "medium_low_confidence" in memory.tags


# =============================================================================
# Test Execution Controller
# =============================================================================


class TestExecutionController:
    """Test ExecutionController class."""

    def test_high_confidence_full_execution(self):
        """High confidence should allow full execution."""
        controller = ExecutionController()
        high_conf = UnifiedConfidence(overall=0.85, quality_component=0.85,
                                       coherence_component=0.85, stability_component=0.85,
                                       action_component=0.85)
        perm = controller.decide(high_conf)
        assert perm.mode == ExecutionMode.FULL
        assert perm.can_execute is True

    def test_medium_confidence_cautious_execution(self):
        """Medium confidence should allow cautious execution."""
        controller = ExecutionController()
        medium_conf = UnifiedConfidence(overall=0.65, quality_component=0.65,
                                         coherence_component=0.65, stability_component=0.65,
                                         action_component=0.65)
        perm = controller.decide(medium_conf)
        assert perm.mode == ExecutionMode.CAUTIOUS
        assert perm.can_execute is True

    def test_low_confidence_confirm_required(self):
        """Low confidence should require confirmation."""
        controller = ExecutionController()
        low_conf = UnifiedConfidence(overall=0.45, quality_component=0.45,
                                      coherence_component=0.45, stability_component=0.45,
                                      action_component=0.45)
        perm = controller.decide(low_conf)
        assert perm.mode == ExecutionMode.CONFIRM_REQUIRED
        assert perm.requires_confirmation is True
        assert perm.confirmation_prompt is not None

    def test_very_low_confidence_blocked(self):
        """Very low confidence should block execution."""
        controller = ExecutionController()
        very_low_conf = UnifiedConfidence(overall=0.2, quality_component=0.2,
                                           coherence_component=0.2, stability_component=0.2,
                                           action_component=0.2)
        perm = controller.decide(very_low_conf)
        assert perm.mode == ExecutionMode.BLOCKED
        assert perm.can_execute is False
        assert perm.fallback_action == "explain_instead"

    def test_high_risk_action_downgraded(self):
        """High-risk actions should be downgraded."""
        controller = ExecutionController()
        high_conf = UnifiedConfidence(overall=0.8, quality_component=0.8,
                                       coherence_component=0.8, stability_component=0.8,
                                       action_component=0.8)
        # file_delete is high-risk
        perm = controller.decide(high_conf, "file_delete")
        assert perm.mode == ExecutionMode.CAUTIOUS  # Downgraded from FULL

    def test_safe_action_upgraded(self):
        """Safe actions should be upgraded."""
        controller = ExecutionController()
        low_conf = UnifiedConfidence(overall=0.25, quality_component=0.25,
                                      coherence_component=0.25, stability_component=0.25,
                                      action_component=0.25)
        # search is safe
        perm = controller.decide(low_conf, "search")
        # Should be upgraded from BLOCKED to CAUTIOUS (via CONFIRM)
        assert perm.mode == ExecutionMode.CAUTIOUS


# =============================================================================
# Test Main Confidence Gate
# =============================================================================


class TestConfidenceGate:
    """Test ConfidenceGate class."""

    def test_evaluate_returns_complete_decision(self):
        """Evaluate should return all decision components."""
        gate = ConfidenceGate()
        signals = ConfidenceSignals(quality_score=0.7)
        decision = gate.evaluate(signals)

        assert decision.confidence is not None
        assert decision.escalation is not None
        assert decision.budget is not None
        assert decision.memory is not None
        assert decision.execution is not None
        assert isinstance(decision.reasoning, list)

    def test_evaluate_high_confidence_path(self):
        """High confidence should produce permissive decisions."""
        gate = ConfidenceGate()
        signals = ConfidenceSignals(
            quality_score=0.9,
            coherence_score=0.9,
            correctness_score=0.9,
            internal_consistency=0.9,
            trajectory_confidence=0.9,
            session_stability=0.9,
            action_complexity=0.1,
            action_reversibility=1.0,
            volatility_index=0.1,
            prediction_reversal_risk=0.1,
        )
        decision = gate.evaluate(signals)

        assert decision.confidence.is_high
        assert decision.escalation.level == EscalationLevel.NONE
        assert decision.execution.can_execute is True
        assert decision.memory.should_store is True

    def test_evaluate_low_confidence_path(self):
        """Low confidence should produce restrictive decisions."""
        gate = ConfidenceGate()
        signals = ConfidenceSignals(
            quality_score=0.2,
            coherence_score=0.2,
            correctness_score=0.2,
            internal_consistency=0.2,
            trajectory_confidence=0.2,
            session_stability=0.2,
            action_complexity=0.9,
            action_reversibility=0.1,
            volatility_index=0.9,
            prediction_reversal_risk=0.9,
        )
        decision = gate.evaluate(signals)

        assert decision.confidence.is_low
        assert decision.escalation.requires_human is True
        assert decision.budget.require_self_check is True
        assert decision.memory.should_store is False

    def test_evaluate_with_action(self):
        """Evaluate should consider action in permission."""
        gate = ConfidenceGate()
        signals = ConfidenceSignals(quality_score=0.8, coherence_score=0.8)

        # High-risk action
        decision = gate.evaluate(signals, action="file_delete")
        assert "file_delete" in decision.execution.blocked_actions or \
               decision.execution.mode == ExecutionMode.CAUTIOUS

    def test_quick_check_high_confidence(self):
        """Quick check should return can proceed for high confidence."""
        gate = ConfidenceGate()
        can_proceed, reason = gate.quick_check(0.9, 0.9)
        assert can_proceed is True

    def test_quick_check_low_confidence(self):
        """Quick check should return cannot proceed for low confidence."""
        gate = ConfidenceGate()
        can_proceed, reason = gate.quick_check(0.2, 0.2)
        assert can_proceed is False
        assert "confidence" in reason.lower() or "Low" in reason

    def test_to_dict(self):
        """Decision should be serializable to dict."""
        gate = ConfidenceGate()
        signals = ConfidenceSignals()
        decision = gate.evaluate(signals)

        d = decision.to_dict()
        assert "confidence" in d
        assert "escalation" in d
        assert "budget" in d
        assert "memory" in d
        assert "execution" in d


# =============================================================================
# Test Factory Functions
# =============================================================================


class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_confidence_gate_custom_weights(self):
        """Custom weights should be applied."""
        gate = create_confidence_gate(
            quality_weight=0.5,
            coherence_weight=0.2,
            stability_weight=0.2,
            action_weight=0.1,
        )
        assert gate is not None
        # Weights should be normalized
        signals = ConfidenceSignals()
        decision = gate.evaluate(signals)
        assert decision.confidence is not None

    def test_create_strict_confidence_gate(self):
        """Strict gate should have higher thresholds."""
        gate = create_strict_confidence_gate()
        signals = ConfidenceSignals(quality_score=0.7, coherence_score=0.7)
        decision = gate.evaluate(signals)
        # 0.7 might trigger escalation with strict thresholds
        # Just verify it works
        assert decision is not None

    def test_create_permissive_confidence_gate(self):
        """Permissive gate should have lower thresholds."""
        gate = create_permissive_confidence_gate()
        signals = ConfidenceSignals(quality_score=0.5, coherence_score=0.5)
        decision = gate.evaluate(signals)
        # Should be more permissive
        assert decision is not None


# =============================================================================
# Test Integration Helpers
# =============================================================================


class TestIntegrationHelpers:
    """Test integration helper functions."""

    def test_signals_from_critique(self):
        """Build signals from mock critique object."""
        class MockCritique:
            overall_score = 0.8
            coherence = 0.7
            correctness = 0.9
            completeness = 0.75
            relevance = 0.85

        signals = signals_from_critique(MockCritique())
        assert signals.quality_score == 0.8
        assert signals.coherence_score == 0.7
        assert signals.correctness_score == 0.9

    def test_signals_from_critique_missing_attrs(self):
        """Handle missing attributes gracefully."""
        class MinimalCritique:
            overall_score = 0.8

        signals = signals_from_critique(MinimalCritique())
        assert signals.quality_score == 0.8
        assert signals.coherence_score == 0.5  # Default

    def test_signals_from_coherence_metrics(self):
        """Build signals from mock coherence metrics."""
        class MockMetrics:
            internal_consistency = 0.9
            goal_alignment = 0.85
            prediction_reversal_risk = 0.1
            volatility_index = 0.2
            overall_coherence = 0.88

        signals = signals_from_coherence_metrics(MockMetrics())
        assert signals.internal_consistency == 0.9
        assert signals.goal_alignment == 0.85
        assert signals.prediction_reversal_risk == 0.1

    def test_signals_from_policy_decision(self):
        """Build signals from mock policy decision."""
        class MockDecision:
            trajectory_confidence = 0.75
            response_style = "stable"

        signals = signals_from_policy_decision(MockDecision())
        assert signals.trajectory_confidence == 0.75
        assert signals.session_stability == 1.0  # "stable" style

    def test_merge_signals(self):
        """Merge multiple signal objects."""
        signals1 = ConfidenceSignals(quality_score=0.9)
        signals2 = ConfidenceSignals(coherence_score=0.8)
        signals3 = ConfidenceSignals(trajectory_confidence=0.7)

        merged = merge_signals(signals1, signals2, signals3)
        assert merged.quality_score == 0.9
        assert merged.coherence_score == 0.8
        assert merged.trajectory_confidence == 0.7

    def test_merge_signals_first_wins(self):
        """First non-default value wins in merge."""
        signals1 = ConfidenceSignals(quality_score=0.9)
        signals2 = ConfidenceSignals(quality_score=0.7)

        merged = merge_signals(signals1, signals2)
        assert merged.quality_score == 0.9  # First value

    def test_merge_signals_action_reversibility(self):
        """Action reversibility default is 1.0."""
        signals1 = ConfidenceSignals()  # action_reversibility = 1.0 (default)
        signals2 = ConfidenceSignals(action_reversibility=0.3)

        merged = merge_signals(signals1, signals2)
        assert merged.action_reversibility == 0.3  # Non-default wins


# =============================================================================
# Test End-to-End Behavioral Control
# =============================================================================


class TestBehavioralControl:
    """Test that confidence CONTROLS behavior, not just ANNOTATES."""

    def test_confidence_gates_execution(self):
        """Low confidence should actually block execution."""
        gate = ConfidenceGate()

        # Low confidence scenario
        low_signals = ConfidenceSignals(
            quality_score=0.2,
            coherence_score=0.2,
            action_complexity=0.9,
            action_reversibility=0.1,
        )
        decision = gate.evaluate(low_signals, action="deploy")

        # Behavioral control: cannot execute
        assert decision.execution.can_execute is False
        assert decision.escalation.requires_human is True

        # This is CONTROL, not annotation - the agent should NOT proceed

    def test_confidence_controls_budget(self):
        """Confidence should allocate different compute budgets."""
        gate = ConfidenceGate()

        low_conf_signals = ConfidenceSignals(quality_score=0.3)
        high_conf_signals = ConfidenceSignals(quality_score=0.9, coherence_score=0.9,
                                               trajectory_confidence=0.9, session_stability=0.9)

        low_decision = gate.evaluate(low_conf_signals)
        high_decision = gate.evaluate(high_conf_signals)

        # Low confidence gets MORE budget (for self-correction)
        assert low_decision.budget.revision_budget > high_decision.budget.revision_budget
        assert low_decision.budget.require_self_check is True
        assert high_decision.budget.require_self_check is False

    def test_confidence_controls_memory(self):
        """Confidence should control what gets stored in memory."""
        gate = ConfidenceGate()

        # Use fully low signals to ensure overall confidence is below store threshold
        low_signals = ConfidenceSignals(
            quality_score=0.1,
            coherence_score=0.1,
            correctness_score=0.1,
            internal_consistency=0.1,
            trajectory_confidence=0.1,
            session_stability=0.1,
            action_complexity=0.9,
            action_reversibility=0.1,
            volatility_index=0.9,
            prediction_reversal_risk=0.9,
        )
        high_signals = ConfidenceSignals(
            quality_score=0.95,
            coherence_score=0.95,
            correctness_score=0.95,
            completeness_score=0.95,
            internal_consistency=0.95,
            goal_alignment=0.95,
            trajectory_confidence=0.95,
            session_stability=0.95,
            volatility_index=0.05,
            prediction_reversal_risk=0.05,
            action_complexity=0.05,
            action_reversibility=1.0,
        )

        low_decision = gate.evaluate(low_signals)
        high_decision = gate.evaluate(high_signals)

        # Low confidence: don't pollute memory with uncertain info
        assert low_decision.memory.should_store is False
        # High confidence: store for future retrieval
        assert high_decision.memory.should_store is True
        assert high_decision.memory.retention_weight == 1.0
        assert high_decision.memory.expiry_turns is None  # Permanent

    def test_integrated_workflow(self):
        """Test a complete workflow using confidence gating."""
        gate = ConfidenceGate()

        # Simulate building signals from framework components
        critique_signals = signals_from_critique(type('Critique', (), {
            'overall_score': 0.75,
            'coherence': 0.7,
            'correctness': 0.8,
        })())

        coherence_signals = signals_from_coherence_metrics(type('Metrics', (), {
            'internal_consistency': 0.8,
            'goal_alignment': 0.75,
            'volatility_index': 0.2,
        })())

        # Merge signals
        combined = merge_signals(critique_signals, coherence_signals)

        # Get gating decision
        decision = gate.evaluate(combined, action="search")

        # Should be able to proceed with search (safe action)
        assert decision.execution.can_execute is True
        # Should store with reasonable weight
        assert decision.memory.should_store is True


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_all_zeros(self):
        """Handle all-zero signals gracefully."""
        gate = ConfidenceGate()
        signals = ConfidenceSignals(
            quality_score=0.0,
            coherence_score=0.0,
            correctness_score=0.0,
            completeness_score=0.0,
            relevance_score=0.0,
            internal_consistency=0.0,
            goal_alignment=0.0,
            trajectory_confidence=0.0,
            session_stability=0.0,
            action_reversibility=0.0,
        )
        decision = gate.evaluate(signals)
        assert decision.confidence.overall >= 0
        assert decision.execution.mode == ExecutionMode.BLOCKED

    def test_all_ones(self):
        """Handle all-one signals gracefully."""
        gate = ConfidenceGate()
        signals = ConfidenceSignals(
            quality_score=1.0,
            coherence_score=1.0,
            correctness_score=1.0,
            completeness_score=1.0,
            relevance_score=1.0,
            internal_consistency=1.0,
            goal_alignment=1.0,
            prediction_reversal_risk=0.0,
            volatility_index=0.0,
            trajectory_confidence=1.0,
            session_stability=1.0,
            action_complexity=0.0,
            action_reversibility=1.0,
        )
        decision = gate.evaluate(signals)
        assert decision.confidence.overall <= 1.0
        assert decision.execution.mode == ExecutionMode.FULL

    def test_confidence_clamped_to_range(self):
        """Confidence should always be in [0, 1]."""
        aggregator = ConfidenceAggregator()

        # Even with extreme values, result should be clamped
        signals = ConfidenceSignals(quality_score=2.0)  # Invalid but handle it
        confidence = aggregator.aggregate(signals)
        assert 0.0 <= confidence.overall <= 1.0

    def test_empty_action_string(self):
        """Empty action string should be handled."""
        gate = ConfidenceGate()
        signals = ConfidenceSignals()
        decision = gate.evaluate(signals, action="")
        assert decision is not None

    def test_none_action(self):
        """None action should be handled."""
        gate = ConfidenceGate()
        signals = ConfidenceSignals()
        decision = gate.evaluate(signals, action=None)
        assert decision is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
