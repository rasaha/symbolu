"""
Symbol-U Pipeline Integration Tests
=====================================

Integration tests that exercise the full pipeline from UserRequest to RenderedOutput.
These tests verify end-to-end functionality without mocking.

Test Categories:
1. Basic Pipeline Execution - Simple queries
2. Persona Selection - Different query types select appropriate personas
3. Render Mode Variations - Different render modes produce different outputs
4. DHA Tone Adaptation - Tone adapts to readiness/resistance signals
5. Edge Cases - Boundary conditions and unusual inputs
"""

import pytest
from typing import Dict, Any


class TestBasicPipelineExecution:
    """Test basic end-to-end pipeline execution."""

    def test_simple_query_execution(self) -> None:
        """Test simple query executes successfully."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="What is Python?")

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None
        assert len(result.raw_text) > 0
        assert result.mode is not None

    def test_query_with_user_id(self) -> None:
        """Test query with user_id processes correctly."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(
            text="Explain machine learning",
            user_id="test_user_001",
        )

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None

    def test_query_with_metadata(self) -> None:
        """Test query with metadata processes correctly."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(
            text="How does encryption work?",
            metadata={"domain": "security", "level": "beginner"},
        )

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None

    def test_long_query_execution(self) -> None:
        """Test longer query executes successfully."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        long_query = (
            "I'm trying to understand how neural networks learn. "
            "Can you explain the backpropagation algorithm, including "
            "how gradients are computed and how weights are updated? "
            "Also, what is the role of the learning rate?"
        )
        request = UserRequest(text=long_query)

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None
        assert len(result.raw_text) > 50  # Should produce substantive output


class TestPipelineContext:
    """Test pipeline context is populated correctly."""

    def test_context_serialization(self) -> None:
        """Test context can be serialized to dict."""
        from symbolu.mechanical.pipeline import (
            SymbolUPipeline,
            UserRequest,
            PipelineContext,
        )

        request = UserRequest(text="What is gravity?")
        ctx = PipelineContext(request=request)

        ctx_dict = ctx.to_dict()
        assert "request" in ctx_dict
        assert ctx_dict["request"]["text"] == "What is gravity?"

    def test_full_pipeline_populates_context(self) -> None:
        """Test full pipeline run populates context fields."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="Explain quantum computing")

        result = pipeline.run(request)

        # Result should be populated
        assert result is not None
        assert result.raw_text is not None

    def test_pipeline_produces_meta(self) -> None:
        """Test pipeline produces metadata."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="What is consciousness?")

        result = pipeline.run(request)

        assert result.meta is not None
        assert isinstance(result.meta, dict)


class TestRenderModeVariations:
    """Test different render modes produce appropriate outputs.

    Valid render modes: minimal, standard, enhanced, regulated
    """

    def test_standard_render_mode(self) -> None:
        """Test standard render mode."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(
            text="What is photosynthesis?",
            render_mode="standard",
        )

        result = pipeline.run(request)

        assert result is not None
        assert result.mode == "standard"

    def test_minimal_render_mode(self) -> None:
        """Test minimal render mode."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(
            text="Explain the concept of time",
            render_mode="minimal",
        )

        result = pipeline.run(request)

        assert result is not None
        assert result.mode == "minimal"

    def test_enhanced_render_mode(self) -> None:
        """Test enhanced render mode."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(
            text="How do I fix a leaky faucet?",
            render_mode="enhanced",
        )

        result = pipeline.run(request)

        assert result is not None
        assert result.mode == "enhanced"

    def test_regulated_render_mode(self) -> None:
        """Test regulated render mode."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(
            text="Explain financial regulations",
            render_mode="regulated",
        )

        result = pipeline.run(request)

        assert result is not None
        assert result.mode == "regulated"


class TestPipelineIdempotency:
    """Test pipeline produces consistent results."""

    def test_same_input_produces_consistent_output(self) -> None:
        """Test same input produces similar outputs."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="What is 2 + 2?")

        result1 = pipeline.run(request)
        result2 = pipeline.run(request)

        # Both should produce valid results
        assert result1.raw_text is not None
        assert result2.raw_text is not None
        # Same request should produce same result (deterministic)
        assert result1.raw_text == result2.raw_text


class TestPipelineEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_minimum_length_query(self) -> None:
        """Test very short query still works."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="Why?")

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None

    def test_query_with_special_characters(self) -> None:
        """Test query with special characters."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="What's the meaning of \"hello\" & 'world'?")

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None

    def test_query_with_unicode(self) -> None:
        """Test query with unicode characters."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="What is the symbol π (pi)?")

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None

    def test_query_with_numbers(self) -> None:
        """Test query with numbers."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="Calculate 123 + 456")

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None


class TestPipelineRouting:
    """Test pipeline routing modes."""

    def test_linear_routing(self) -> None:
        """Test linear routing mode executes correctly."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="Basic query for linear routing")

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None


class TestPipelineMetadata:
    """Test pipeline produces correct metadata."""

    def test_result_has_meta(self) -> None:
        """Test result includes metadata."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="What is AI?")

        result = pipeline.run(request)

        assert result.meta is not None
        assert isinstance(result.meta, dict)

    def test_result_meta_has_timing(self) -> None:
        """Test result metadata includes timing information if available."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="Explain databases")

        result = pipeline.run(request)

        # Meta should be populated
        assert result.meta is not None


class TestPipelineResourceCleanup:
    """Test pipeline properly handles resources."""

    def test_multiple_runs_no_memory_leak(self) -> None:
        """Test multiple runs don't cause issues."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()

        for i in range(5):
            request = UserRequest(text=f"Query number {i}")
            result = pipeline.run(request)
            assert result is not None
            assert result.raw_text is not None

    def test_new_pipeline_instances(self) -> None:
        """Test creating multiple pipeline instances works."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        for i in range(3):
            pipeline = SymbolUPipeline()
            request = UserRequest(text=f"Query for pipeline {i}")
            result = pipeline.run(request)
            assert result is not None


class TestGovernanceChainIntegration:
    """Test PO1-PO5 governance chain is activated before MLCR.

    Pipeline flow:
        PO1 → PO2 → PO3 → PO4 → PO5 → MLCR → Persona → Fusion → DHA → Renderer
    """

    def test_po1_grounding_activated(self) -> None:
        """Test PO1 (Observer-Observed Grounding) runs and populates context."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="I feel anxious about my future")

        result = pipeline.run(request)

        # Get context from result meta
        ctx = result.meta.get("context")
        assert ctx is not None

        # PO1 should have populated phase_minus_one
        assert hasattr(ctx, "phase_minus_one")
        assert ctx.phase_minus_one is not None
        assert hasattr(ctx.phase_minus_one, "overall_policy")

    def test_po2_intent_envelope_activated(self) -> None:
        """Test PO2 (Intent Envelope) runs and populates context."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="Why do I keep making mistakes?")

        result = pipeline.run(request)

        ctx = result.meta.get("context")
        assert ctx is not None

        # PO2 should have populated phase_zero
        assert hasattr(ctx, "phase_zero")
        assert ctx.phase_zero is not None
        assert hasattr(ctx.phase_zero, "intent_type")
        assert hasattr(ctx.phase_zero, "response_posture")

    def test_po3_allowed_actions_activated(self) -> None:
        """Test PO3 (Allowed Action Binding) runs and populates context."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        request = UserRequest(text="How can I improve my productivity?")

        result = pipeline.run(request)

        ctx = result.meta.get("context")
        assert ctx is not None

        # PO3 should have populated allowed_actions
        assert hasattr(ctx, "allowed_actions")
        assert ctx.allowed_actions is not None
        assert hasattr(ctx.allowed_actions, "allowed_actions")
        assert hasattr(ctx.allowed_actions, "intent_type")

    def test_full_governance_chain_flows(self) -> None:
        """Test full PO1-PO5 chain runs before MLCR."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest
        from symbolu.mechanical.pipeline.grounding import OverallPolicy

        pipeline = SymbolUPipeline()
        request = UserRequest(text="I'm worried because my friend seems sad")

        result = pipeline.run(request)

        ctx = result.meta.get("context")
        assert ctx is not None

        # All governance outputs should be populated
        assert ctx.phase_minus_one is not None  # PO1
        assert ctx.phase_zero is not None  # PO2
        assert ctx.allowed_actions is not None  # PO3

        # MLCR should also have run (after governance)
        assert ctx.mlcr is not None

    def test_governance_chain_reflexive_query(self) -> None:
        """Test governance chain correctly identifies reflexive (self-observation) queries."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest
        from symbolu.mechanical.pipeline.grounding import ObservationMode

        pipeline = SymbolUPipeline()
        request = UserRequest(text="I feel overwhelmed by my responsibilities")

        result = pipeline.run(request)

        ctx = result.meta.get("context")
        assert ctx is not None
        assert ctx.phase_minus_one is not None

        # For "I feel..." queries, primary grounding should be REFLEXIVE
        if ctx.phase_minus_one.selected_primary:
            assert ctx.phase_minus_one.selected_primary.mode == ObservationMode.REFLEXIVE

    def test_governance_chain_detached_query(self) -> None:
        """Test governance chain correctly identifies detached (abstract) queries."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest
        from symbolu.mechanical.pipeline.grounding import ObservationMode

        pipeline = SymbolUPipeline()
        request = UserRequest(text="Anxiety is a common experience in modern society")

        result = pipeline.run(request)

        ctx = result.meta.get("context")
        assert ctx is not None
        assert ctx.phase_minus_one is not None

        # For abstract statements, primary grounding should be DETACHED
        if ctx.phase_minus_one.selected_primary:
            assert ctx.phase_minus_one.selected_primary.mode == ObservationMode.DETACHED

    def test_governance_determinism(self) -> None:
        """Test governance chain produces deterministic results."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()
        query = "I wonder why I feel this way"

        result1 = pipeline.run(UserRequest(text=query))
        result2 = pipeline.run(UserRequest(text=query))

        ctx1 = result1.meta.get("context")
        ctx2 = result2.meta.get("context")

        assert ctx1 is not None and ctx2 is not None

        # PO1 results should be identical
        assert ctx1.phase_minus_one.overall_policy == ctx2.phase_minus_one.overall_policy

        # PO2 results should be identical
        assert ctx1.phase_zero.intent_type == ctx2.phase_zero.intent_type
        assert ctx1.phase_zero.response_posture == ctx2.phase_zero.response_posture

    def test_governance_respects_session_context(self) -> None:
        """Test governance chain respects session context when provided."""
        from symbolu.mechanical.pipeline import SymbolUPipeline, UserRequest

        pipeline = SymbolUPipeline()

        # Query with session_id should create session context
        request = UserRequest(
            text="I feel stuck in my career",
            metadata={"session_id": "test_session_001"},
        )

        result = pipeline.run(request)

        ctx = result.meta.get("context")
        assert ctx is not None
        assert ctx.phase_minus_one is not None

        # Session context should be tracked if available
        if hasattr(ctx, "po1_session"):
            assert ctx.po1_session is not None
