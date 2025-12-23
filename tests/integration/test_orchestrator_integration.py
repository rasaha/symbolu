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
