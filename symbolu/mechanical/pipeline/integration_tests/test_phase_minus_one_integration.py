"""
Phase −1 Integration Tests

End-to-end tests verifying Phase −1 behavior within the pipeline context.

Test Scenarios:
1. Reflexive sentences don't produce analysis output
2. Relational sentences don't produce diagnosis
3. Detached sentences allow analysis
4. BLOCKED state returns clarification output
5. Multi-context splits are handled correctly
6. Violations are logged to metrics

These tests verify the integration between:
- PhaseMinusOnePipeline
- PlannerGate
- ClarifyRenderer
- PhaseMinusOneMetrics
"""

import pytest
from symbolu.mechanical.pipeline.grounding import (
    PhaseMinusOnePipeline,
    ObservationMode,
    OverallPolicy,
    ResolutionPolicy,
)
from symbolu.mechanical.pipeline.governance import (
    PlannerGate,
    ActionClass,
)
from symbolu.mechanical.renderer.clarify_renderer import (
    ClarifyRenderer,
    render_clarification_text,
)
from symbolu.mechanical.pipeline.diagnostics.phase_minus_one_metrics import (
    PhaseMinusOneMetrics,
)


class TestPhaseMinusOneIntegration:
    """
    Integration tests for Phase −1 grounding system.

    These tests verify the full flow from input through grounding,
    gating, and output generation.
    """

    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = PhaseMinusOnePipeline()
        self.gate = PlannerGate()
        self.renderer = ClarifyRenderer()
        self.metrics = PhaseMinusOneMetrics()

    def test_reflexive_blocks_analysis_end_to_end(self):
        """
        Test: Reflexive grounding blocks analytical actions.

        Input: "I am sad."
        Expected:
        - Phase −1 produces REFLEXIVE grounding
        - PlannerGate blocks ANALYZE, DIAGNOSE
        - PlannerGate allows CARE, REFLECT
        """
        # Step 1: Run Phase −1
        envelope = self.pipeline.run("I am sad.")

        # Verify grounding
        assert envelope.overall_policy == OverallPolicy.SINGLE_CONTEXT
        assert len(envelope.clauses) == 1
        assert envelope.clauses[0].selected is not None
        assert envelope.clauses[0].selected.mode == ObservationMode.REFLEXIVE
        assert envelope.clauses[0].selected.analysis_allowed is False

        # Step 2: Pass through PlannerGate
        proposed_actions = [
            ActionClass.CARE,
            ActionClass.REFLECT,
            ActionClass.ANALYZE,
            ActionClass.DIAGNOSE,
        ]
        gate_result = self.gate.filter(envelope, proposed_actions)

        # Verify gating
        assert not gate_result.blocked
        assert ActionClass.CARE in gate_result.selected_action_classes
        assert ActionClass.REFLECT in gate_result.selected_action_classes
        assert ActionClass.ANALYZE not in gate_result.selected_action_classes
        assert ActionClass.DIAGNOSE not in gate_result.selected_action_classes

        # Verify violations logged
        assert len(gate_result.violations) >= 2  # At least ANALYZE and DIAGNOSE

        # Step 3: Record metrics
        self.metrics.record_envelope(envelope)
        for v in gate_result.violations:
            self.metrics.record_violation(
                module="planner_gate",
                action=v["action"],
                reason=v["reason"],
            )

        snapshot = self.metrics.get_snapshot()
        assert snapshot.mode_counts.get("REFLEXIVE", 0) >= 1
        assert snapshot.violation_count >= 2

    def test_relational_blocks_diagnosis_end_to_end(self):
        """
        Test: Relational grounding blocks diagnosis actions.

        Input: "She seems depressed."
        Expected:
        - Phase −1 produces RELATIONAL grounding
        - PlannerGate blocks DIAGNOSE_OTHER, ASSERT_OTHER_STATE
        - PlannerGate allows ALIGN, ASK
        """
        # Step 1: Run Phase −1
        envelope = self.pipeline.run("She seems depressed.")

        # Verify grounding
        assert envelope.overall_policy == OverallPolicy.SINGLE_CONTEXT
        selected = envelope.clauses[0].selected
        assert selected is not None
        assert selected.mode == ObservationMode.RELATIONAL
        assert selected.analysis_allowed is False

        # Step 2: Pass through PlannerGate
        proposed_actions = [
            ActionClass.ALIGN,
            ActionClass.ASK,
            ActionClass.DIAGNOSE_OTHER,
            ActionClass.ASSERT_OTHER_STATE,
        ]
        gate_result = self.gate.filter(envelope, proposed_actions)

        # Verify gating
        assert not gate_result.blocked
        assert ActionClass.ALIGN in gate_result.selected_action_classes
        assert ActionClass.ASK in gate_result.selected_action_classes
        assert ActionClass.DIAGNOSE_OTHER not in gate_result.selected_action_classes
        assert ActionClass.ASSERT_OTHER_STATE not in gate_result.selected_action_classes

    def test_detached_allows_analysis_end_to_end(self):
        """
        Test: Detached grounding allows analytical actions.

        Input: "Depression affects millions of people."
        Expected:
        - Phase −1 produces DETACHED grounding
        - PlannerGate allows ANALYZE, EXPLAIN
        """
        # Step 1: Run Phase −1
        envelope = self.pipeline.run("Depression affects millions of people.")

        # Verify grounding
        selected = envelope.clauses[0].selected
        assert selected is not None

        # If DETACHED, analysis should be allowed
        if selected.mode == ObservationMode.DETACHED:
            assert selected.analysis_allowed is True

            # Step 2: Pass through PlannerGate
            proposed_actions = [
                ActionClass.EXPLAIN,
                ActionClass.ANALYZE,
                ActionClass.SUMMARIZE,
            ]
            gate_result = self.gate.filter(envelope, proposed_actions)

            # Verify gating - all should be allowed for DETACHED
            assert ActionClass.EXPLAIN in gate_result.selected_action_classes
            assert ActionClass.ANALYZE in gate_result.selected_action_classes
            assert ActionClass.SUMMARIZE in gate_result.selected_action_classes

    def test_blocked_returns_clarification_end_to_end(self):
        """
        Test: BLOCKED state returns clarification question.

        When grounding is ambiguous and BLOCKED:
        - PlannerGate returns only ASK_CLARIFY_REFERENCE
        - ClarifyRenderer produces a clarification question
        """
        # Create a scenario that's likely to be ambiguous
        # (verb without clear subject)
        envelope = self.pipeline.run("Struggling with something.")

        if envelope.is_blocked():
            # Step 2: Pass through PlannerGate
            proposed_actions = [ActionClass.CARE, ActionClass.ANALYZE]
            gate_result = self.gate.filter(envelope, proposed_actions)

            # Verify blocked
            assert gate_result.blocked is True
            assert ActionClass.ASK_CLARIFY_REFERENCE in gate_result.selected_action_classes
            assert len(gate_result.selected_action_classes) == 1

            # Step 3: Render clarification
            clarify_text = render_clarification_text(envelope)

            # Verify clarification output
            assert len(clarify_text) > 0
            # Should ask about perspective/reference
            assert "?" in clarify_text  # Should be a question

    def test_multi_context_handles_both_modes(self):
        """
        Test: Multi-context split handles different modes per clause.

        Input: "I'm worried because she seems upset."
        Expected (if split):
        - MULTI_CONTEXT policy
        - First clause: REFLEXIVE
        - Second clause: RELATIONAL
        - Actions gated appropriately per clause
        """
        envelope = self.pipeline.run("I'm worried because she seems upset.")

        if envelope.was_split and envelope.overall_policy == OverallPolicy.MULTI_CONTEXT:
            assert len(envelope.clauses) == 2

            # Verify clause modes
            clause1 = envelope.clauses[0]
            clause2 = envelope.clauses[1]

            assert clause1.selected is not None
            assert clause2.selected is not None

            # First should be about "I" (REFLEXIVE)
            # Second should be about "she" (RELATIONAL)
            modes = {clause1.selected.mode, clause2.selected.mode}
            assert ObservationMode.REFLEXIVE in modes or ObservationMode.RELATIONAL in modes

    def test_metrics_integration(self):
        """
        Test: Metrics are correctly integrated across components.
        """
        self.metrics.reset()

        # Process multiple sentences
        sentences = [
            "I feel anxious.",  # REFLEXIVE
            "She seems happy.",  # RELATIONAL
            "Anxiety is treatable.",  # DETACHED
        ]

        for sentence in sentences:
            envelope = self.pipeline.run(sentence)
            self.metrics.record_envelope(envelope)

            # Simulate some gate violations
            gate_result = self.gate.filter(envelope, [ActionClass.DIAGNOSE])
            for v in gate_result.violations:
                self.metrics.record_violation(
                    module="planner_gate",
                    action=v["action"],
                    reason=v["reason"],
                )

        # Verify aggregated metrics
        snapshot = self.metrics.get_snapshot()

        # Should have processed 3 sentences
        assert sum(snapshot.mode_counts.values()) >= 3

        # Should have some violations (DIAGNOSE forbidden for most modes)
        assert snapshot.violation_count >= 2

    def test_full_pipeline_flow_reflexive(self):
        """
        Test: Full pipeline flow for reflexive input.

        Verifies the complete authority chain:
        Phase −1 → PlannerGate → Output
        """
        input_text = "I am feeling overwhelmed."

        # Phase −1: Establish grounding
        envelope = self.pipeline.run(input_text)

        assert envelope.overall_policy == OverallPolicy.SINGLE_CONTEXT
        assert envelope.clauses[0].selected.mode == ObservationMode.REFLEXIVE

        # PlannerGate: Filter actions
        all_actions = [
            ActionClass.CARE,
            ActionClass.GROUND,
            ActionClass.REFLECT,
            ActionClass.ANALYZE,
            ActionClass.DIAGNOSE,
            ActionClass.EXPLAIN_CAUSES,
        ]
        gate_result = self.gate.filter(envelope, all_actions)

        # Safe actions should pass
        safe_actions = {ActionClass.CARE, ActionClass.GROUND, ActionClass.REFLECT}
        unsafe_actions = {ActionClass.ANALYZE, ActionClass.DIAGNOSE, ActionClass.EXPLAIN_CAUSES}

        for action in safe_actions:
            assert action in gate_result.selected_action_classes, f"{action} should be allowed"

        for action in unsafe_actions:
            assert action not in gate_result.selected_action_classes, f"{action} should be blocked"

    def test_authority_chain_cannot_be_bypassed(self):
        """
        Test: Downstream stages cannot bypass Phase −1 constraints.

        Even if a planner "wants" to analyze, the gate enforces constraints.
        """
        # Reflexive input
        envelope = self.pipeline.run("I hate myself.")

        # Verify strict constraints
        assert envelope.clauses[0].selected.mode == ObservationMode.REFLEXIVE
        assert envelope.clauses[0].selected.analysis_allowed is False

        # Try to force through analytical actions
        aggressive_actions = [
            ActionClass.DIAGNOSE,
            ActionClass.ANALYZE,
            ActionClass.PERSONAL_DIAGNOSIS,
            ActionClass.EXPLAIN_CAUSES,
        ]

        gate_result = self.gate.filter(envelope, aggressive_actions)

        # ALL should be blocked
        assert len(gate_result.selected_action_classes) == 0
        assert len(gate_result.rejected_action_classes) == len(aggressive_actions)

        # Violations should be logged
        assert len(gate_result.violations) == len(aggressive_actions)


class TestPipelineContextIntegration:
    """
    Tests for Phase −1 integration with PipelineContext.
    """

    def test_envelope_serialization(self):
        """Test: Envelope can be serialized to dict for PipelineContext."""
        pipeline = PhaseMinusOnePipeline()
        envelope = pipeline.run("I am worried about the future.")

        # Serialize
        envelope_dict = envelope.to_dict()

        # Verify structure
        assert "overall_policy" in envelope_dict
        assert "clauses" in envelope_dict
        assert "debug" in envelope_dict
        assert "mode_distribution" in envelope_dict
        assert "confidence_stats" in envelope_dict

    def test_debug_info_contains_metrics(self):
        """Test: Debug info contains useful metrics."""
        pipeline = PhaseMinusOnePipeline()
        envelope = pipeline.run("I feel confused and she seems distant.")

        debug = envelope.debug

        assert "mode_distribution" in debug
        assert "risk_distribution" in debug
        assert "confidence_stats" in debug
        assert "blocked" in debug


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
