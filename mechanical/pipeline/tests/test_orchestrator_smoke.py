"""
Symbol-U Pipeline Smoke Tests

Lightweight smoke tests for the v3.0 pipeline.
These tests verify basic functionality without deep integration testing.

Run with:
    pytest mechanical/pipeline/tests/test_orchestrator_smoke.py -v
"""

import pytest
from typing import Dict, Any


class TestPipelineModelsSmoke:
    """Smoke tests for pipeline models."""

    def test_user_request_creation(self) -> None:
        """Test UserRequest can be instantiated."""
        from mechanical.pipeline.models import UserRequest

        request = UserRequest(text="Test query")
        assert request.text == "Test query"
        assert request.user_id is None
        assert request.metadata == {}
        assert request.render_mode is None

    def test_user_request_with_all_fields(self) -> None:
        """Test UserRequest with all fields populated."""
        from mechanical.pipeline.models import UserRequest

        request = UserRequest(
            text="Test query",
            user_id="user_001",
            metadata={"key": "value"},
            render_mode="standard",
        )
        assert request.text == "Test query"
        assert request.user_id == "user_001"
        assert request.metadata == {"key": "value"}
        assert request.render_mode == "standard"

    def test_user_request_empty_text_raises(self) -> None:
        """Test UserRequest raises on empty text."""
        from mechanical.pipeline.models import UserRequest

        with pytest.raises(ValueError):
            UserRequest(text="")

    def test_rendered_output_creation(self) -> None:
        """Test RenderedOutput can be instantiated."""
        from mechanical.pipeline.models import RenderedOutput

        output = RenderedOutput(
            raw_text="Test output",
            mode="standard",
            meta={"key": "value"},
        )
        assert output.raw_text == "Test output"
        assert output.mode == "standard"
        assert output.meta == {"key": "value"}

    def test_pipeline_context_creation(self) -> None:
        """Test PipelineContext can be instantiated."""
        from mechanical.pipeline.models import UserRequest, PipelineContext

        request = UserRequest(text="Test query")
        ctx = PipelineContext(request=request)

        assert ctx.request == request
        assert ctx.persona is None
        assert ctx.mlcr is None
        assert ctx.fusion is None
        assert ctx.dha is None
        assert ctx.rendered is None
        assert ctx.router_mode == "linear"

    def test_pipeline_context_to_dict(self) -> None:
        """Test PipelineContext serialization."""
        from mechanical.pipeline.models import UserRequest, PipelineContext

        request = UserRequest(text="Test query", user_id="user_001")
        ctx = PipelineContext(request=request)
        ctx_dict = ctx.to_dict()

        assert ctx_dict["request"]["text"] == "Test query"
        assert ctx_dict["request"]["user_id"] == "user_001"
        assert ctx_dict["router_mode"] == "linear"


class TestPipelineRouterSmoke:
    """Smoke tests for pipeline router."""

    def test_router_creation(self) -> None:
        """Test PipelineRouter can be instantiated."""
        from mechanical.pipeline.routing import PipelineRouter

        router = PipelineRouter()
        assert router is not None

    def test_router_default_mode_is_linear(self) -> None:
        """Test router returns linear mode by default."""
        from mechanical.pipeline.routing import PipelineRouter
        from mechanical.pipeline.models import UserRequest, PipelineContext

        router = PipelineRouter()
        request = UserRequest(text="Test query")
        ctx = PipelineContext(request=request)

        mode = router.decide(ctx)
        assert mode == "linear"

    def test_get_default_router(self) -> None:
        """Test get_default_router factory function."""
        from mechanical.pipeline.routing import get_default_router

        router = get_default_router()
        assert router is not None

    def test_router_explain(self) -> None:
        """Test router explain method."""
        from mechanical.pipeline.routing import PipelineRouter

        router = PipelineRouter()
        explanation = router.explain("linear")
        assert "linear" in explanation.lower() or "sequential" in explanation.lower()

    def test_router_valid_modes(self) -> None:
        """Test router has expected valid modes."""
        from mechanical.pipeline.routing import PipelineRouter

        expected_modes = {"linear", "dha_first", "dual_branch", "resistance_loop", "entropy_priority"}
        assert PipelineRouter.VALID_MODES == expected_modes


class TestPipelineValidatorsSmoke:
    """Smoke tests for pipeline validators."""

    def test_validate_request_valid(self) -> None:
        """Test validate_request passes for valid request."""
        from mechanical.pipeline.validators import validate_request
        from mechanical.pipeline.models import UserRequest

        request = UserRequest(text="Test query")
        # Should not raise
        validate_request(request)

    def test_validate_request_none_raises(self) -> None:
        """Test validate_request raises for None."""
        from mechanical.pipeline.validators import validate_request

        with pytest.raises(ValueError):
            validate_request(None)

    def test_validate_request_invalid_render_mode(self) -> None:
        """Test validate_request raises for invalid render mode."""
        from mechanical.pipeline.validators import validate_request
        from mechanical.pipeline.models import UserRequest

        request = UserRequest(text="Test query", render_mode="invalid_mode")
        with pytest.raises(ValueError):
            validate_request(request)

    def test_ensure_persona_missing(self) -> None:
        """Test ensure_persona raises when persona is None."""
        from mechanical.pipeline.validators import ensure_persona
        from mechanical.pipeline.models import UserRequest, PipelineContext

        request = UserRequest(text="Test query")
        ctx = PipelineContext(request=request)

        with pytest.raises(ValueError):
            ensure_persona(ctx)


class TestSymbolUPipelineSmoke:
    """Smoke tests for SymbolUPipeline."""

    def test_pipeline_instantiation(self) -> None:
        """Test SymbolUPipeline can be instantiated."""
        from mechanical.pipeline.orchestrator import SymbolUPipeline

        pipeline = SymbolUPipeline()
        assert pipeline is not None
        assert pipeline.router is not None
        assert pipeline.mlcr is not None
        assert pipeline.fusion_engine is not None
        assert pipeline.dha_engine is not None

    def test_pipeline_with_custom_router(self) -> None:
        """Test SymbolUPipeline accepts custom router."""
        from mechanical.pipeline.orchestrator import SymbolUPipeline
        from mechanical.pipeline.routing import PipelineRouter

        custom_router = PipelineRouter()
        pipeline = SymbolUPipeline(router=custom_router)
        assert pipeline.router is custom_router

    # TODO: Add integration test for full pipeline run
    # This requires mocking or having all engines available
    # def test_pipeline_run_basic(self) -> None:
    #     """Test full pipeline execution."""
    #     from mechanical.pipeline import SymbolUPipeline, UserRequest
    #
    #     pipeline = SymbolUPipeline()
    #     request = UserRequest(text="Test query")
    #     result = pipeline.run(request)
    #
    #     assert result is not None
    #     assert result.raw_text is not None
    #     assert result.mode == "standard"


class TestPipelinePackageExports:
    """Test that all expected exports are available from the package."""

    def test_core_exports(self) -> None:
        """Test core classes are exported."""
        from mechanical.pipeline import (
            SymbolUPipeline,
            UserRequest,
            RenderedOutput,
            PipelineContext,
        )

        assert SymbolUPipeline is not None
        assert UserRequest is not None
        assert RenderedOutput is not None
        assert PipelineContext is not None

    def test_model_exports(self) -> None:
        """Test all model classes are exported."""
        from mechanical.pipeline import (
            PersonaContext,
            MlcrResult,
            FusionResult,
            DhaDecision,
        )

        assert PersonaContext is not None
        assert MlcrResult is not None
        assert FusionResult is not None
        assert DhaDecision is not None

    def test_router_exports(self) -> None:
        """Test router exports."""
        from mechanical.pipeline import (
            PipelineRouter,
            get_default_router,
        )

        assert PipelineRouter is not None
        assert get_default_router is not None

    def test_validator_exports(self) -> None:
        """Test validator exports."""
        from mechanical.pipeline import (
            validate_request,
            ensure_persona,
            ensure_mlcr,
            ensure_fusion,
            ensure_dha,
            ensure_rendered,
        )

        assert validate_request is not None
        assert ensure_persona is not None
        assert ensure_mlcr is not None
        assert ensure_fusion is not None
        assert ensure_dha is not None
        assert ensure_rendered is not None

    def test_run_pipeline_convenience_function(self) -> None:
        """Test run_pipeline convenience function is exported."""
        from mechanical.pipeline import run_pipeline

        assert run_pipeline is not None


# Placeholder for future integration tests
class TestPipelineIntegration:
    """
    Integration tests for full pipeline execution.

    TODO: These tests require all engines to be properly set up.
    For now, they serve as documentation of expected behavior.
    """

    @pytest.mark.skip(reason="TODO: Requires full engine integration")
    def test_full_pipeline_execution(self) -> None:
        """Test complete pipeline execution from request to output."""
        pass

    @pytest.mark.skip(reason="TODO: Requires full engine integration")
    def test_pipeline_with_different_render_modes(self) -> None:
        """Test pipeline produces different outputs for different render modes."""
        pass

    @pytest.mark.skip(reason="TODO: Requires full engine integration")
    def test_pipeline_persona_selection(self) -> None:
        """Test correct persona is selected based on query."""
        pass

    @pytest.mark.skip(reason="TODO: Requires full engine integration")
    def test_pipeline_dha_adaptation(self) -> None:
        """Test DHA correctly adapts delivery based on readiness/resistance."""
        pass
