"""
Tests for the pipeline router.

Verifies:
- Routing decisions based on request context
- Pipeline A (deterministic) execution
- Pipeline B (semantic) execution with delegation
- Hybrid mode
"""

import pytest
from symbolu.orchestration.pipeline_router import (
    PipelineType,
    RequestIntent,
    RoutingDecision,
    UnifiedRequest,
    UnifiedResponse,
    PipelineRouter,
    PipelineADeterministic,
    PipelineBSemantic,
    generate,
)


class TestUnifiedRequest:
    """Tests for UnifiedRequest dataclass."""

    def test_minimal_request(self):
        """Minimal request with defaults."""
        req = UnifiedRequest(request_type="generate")
        assert req.request_type == "generate"
        assert req.target_constraints is None
        assert req.semantic_intent is None
        assert req.preferred_pipeline == PipelineType.AUTO

    def test_mechanical_request(self):
        """Request with mechanical constraints."""
        req = UnifiedRequest(
            request_type="generate",
            target_constraints={"final_magnitude": ">= 1.3"},
        )
        assert req.target_constraints is not None
        assert "final_magnitude" in req.target_constraints

    def test_semantic_request(self):
        """Request with semantic intent."""
        req = UnifiedRequest(
            request_type="generate",
            semantic_intent="calm and gentle",
        )
        assert req.semantic_intent == "calm and gentle"


class TestRoutingDecision:
    """Tests for routing decision logic."""

    def test_explicit_pipeline_preference(self):
        """Explicit pipeline preference is honored."""
        router = PipelineRouter()
        req = UnifiedRequest(
            request_type="generate",
            preferred_pipeline=PipelineType.DETERMINISTIC,
        )
        decision = router._make_routing_decision(req)
        assert decision.pipeline == PipelineType.DETERMINISTIC
        assert decision.confidence == 1.0

    def test_mechanical_constraints_route_to_a(self):
        """Requests with mechanical constraints route to Pipeline A."""
        router = PipelineRouter()
        req = UnifiedRequest(
            request_type="generate",
            target_constraints={"final_magnitude": ">= 1.0"},
        )
        decision = router._make_routing_decision(req)
        assert decision.pipeline == PipelineType.DETERMINISTIC
        assert decision.intent == RequestIntent.CONSTRAINT_SATISFACTION

    def test_semantic_intent_routes_to_b(self):
        """Requests with semantic intent route to Pipeline B."""
        router = PipelineRouter()
        req = UnifiedRequest(
            request_type="generate",
            semantic_intent="something creative",
        )
        decision = router._make_routing_decision(req)
        assert decision.pipeline == PipelineType.SEMANTIC
        assert decision.intent == RequestIntent.CREATIVE_GENERATION

    def test_conversation_history_routes_to_b(self):
        """Requests with conversation history route to Pipeline B."""
        router = PipelineRouter()
        req = UnifiedRequest(
            request_type="generate",
            context_history=[{"role": "user", "content": "hello"}],
        )
        decision = router._make_routing_decision(req)
        assert decision.pipeline == PipelineType.SEMANTIC
        assert decision.intent == RequestIntent.CONVERSATIONAL

    def test_validation_routes_to_a(self):
        """Validation requests route to Pipeline A."""
        router = PipelineRouter()
        req = UnifiedRequest(request_type="validate")
        decision = router._make_routing_decision(req)
        assert decision.pipeline == PipelineType.DETERMINISTIC
        assert decision.intent == RequestIntent.VALIDATION

    def test_exploration_defaults_to_a(self):
        """Exploration requests default to Pipeline A."""
        router = PipelineRouter()
        req = UnifiedRequest(request_type="explore")
        decision = router._make_routing_decision(req)
        assert decision.pipeline == PipelineType.DETERMINISTIC


class TestPipelineADeterministic:
    """Tests for Pipeline A execution."""

    def test_can_handle_mechanical_constraints(self):
        """Pipeline A can handle mechanical constraints."""
        pipeline = PipelineADeterministic()
        req = UnifiedRequest(
            request_type="generate",
            target_constraints={"final_magnitude": ">= 1.0"},
        )
        assert pipeline.can_handle(req)

    def test_can_handle_no_semantic(self):
        """Pipeline A can handle requests without semantic intent."""
        pipeline = PipelineADeterministic()
        req = UnifiedRequest(request_type="generate")
        assert pipeline.can_handle(req)

    def test_execute_produces_sequences(self):
        """Pipeline A execution produces sequences."""
        pipeline = PipelineADeterministic()
        req = UnifiedRequest(
            request_type="generate",
            target_constraints={"final_magnitude": ">= 1.0"},
            selection_config={"max_results": 5},
        )
        response = pipeline.execute(req)
        assert response.success
        assert len(response.sequences) > 0
        assert response.pipeline_used == PipelineType.DETERMINISTIC
        assert response.deterministic is True

    def test_capabilities(self):
        """Pipeline A reports correct capabilities."""
        pipeline = PipelineADeterministic()
        caps = pipeline.get_capabilities()
        assert caps["deterministic"] is True
        assert caps["constraint_satisfaction"] is True
        assert caps["semantic_understanding"] is False


class TestPipelineBSemantic:
    """Tests for Pipeline B execution."""

    def test_can_handle_semantic_intent(self):
        """Pipeline B can handle semantic intent."""
        pipeline = PipelineBSemantic()
        req = UnifiedRequest(
            request_type="generate",
            semantic_intent="calm and gentle",
        )
        assert pipeline.can_handle(req)

    def test_can_handle_creativity(self):
        """Pipeline B can handle creativity requests."""
        pipeline = PipelineBSemantic()
        req = UnifiedRequest(
            request_type="generate",
            creativity_level=0.5,
        )
        assert pipeline.can_handle(req)

    def test_execute_delegates_to_a(self):
        """Pipeline B delegates to Pipeline A for generation."""
        pipeline = PipelineBSemantic()
        req = UnifiedRequest(
            request_type="generate",
            semantic_intent="calm and gentle",
            selection_config={"max_results": 5},
        )
        response = pipeline.execute(req)
        # Should succeed via delegation
        assert response.success
        assert response.pipeline_used == PipelineType.SEMANTIC
        assert response.deterministic is False

    def test_semantic_translation_calm(self):
        """Semantic translation of 'calm' produces constraints."""
        pipeline = PipelineBSemantic()
        req = UnifiedRequest(
            request_type="generate",
            semantic_intent="calm gentle",
        )
        translated = pipeline._translate_semantic_to_mechanical(req)
        assert translated.target_constraints is not None
        # Should have magnitude constraints
        assert "final_magnitude" in translated.target_constraints

    def test_semantic_translation_energetic(self):
        """Semantic translation of 'energetic' produces constraints."""
        pipeline = PipelineBSemantic()
        req = UnifiedRequest(
            request_type="generate",
            semantic_intent="energetic active",
        )
        translated = pipeline._translate_semantic_to_mechanical(req)
        assert translated.target_constraints is not None
        assert "final_magnitude" in translated.target_constraints

    def test_capabilities(self):
        """Pipeline B reports correct capabilities."""
        pipeline = PipelineBSemantic()
        caps = pipeline.get_capabilities()
        assert caps["deterministic"] is False
        assert caps["semantic_understanding"] is True
        assert caps["conversation"] is True


class TestPipelineRouter:
    """Tests for the main router."""

    def test_route_to_deterministic(self):
        """Router routes mechanical requests to Pipeline A."""
        router = PipelineRouter()
        req = UnifiedRequest(
            request_type="generate",
            target_constraints={"final_magnitude": ">= 1.0"},
            selection_config={"max_results": 3},
        )
        response = router.route(req)
        assert response.success
        assert response.pipeline_used == PipelineType.DETERMINISTIC

    def test_route_to_semantic(self):
        """Router routes semantic requests to Pipeline B."""
        router = PipelineRouter()
        req = UnifiedRequest(
            request_type="generate",
            semantic_intent="calm",
            selection_config={"max_results": 3},
        )
        response = router.route(req)
        assert response.success
        assert response.pipeline_used == PipelineType.SEMANTIC

    def test_get_pipeline_status(self):
        """Router reports status of both pipelines."""
        router = PipelineRouter()
        status = router.get_pipeline_status()
        assert "pipeline_a" in status
        assert "pipeline_b" in status
        assert status["pipeline_a"]["available"] is True
        assert status["pipeline_b"]["available"] is True


class TestConvenienceFunction:
    """Tests for the generate() convenience function."""

    def test_generate_with_constraints(self):
        """Generate with mechanical constraints."""
        response = generate(
            target={"final_magnitude": ">= 1.0"},
            selection_config={"max_results": 3},
        )
        assert response.success
        assert len(response.sequences) > 0

    def test_generate_with_intent(self):
        """Generate with semantic intent."""
        response = generate(
            intent="calm",
            selection_config={"max_results": 3},
        )
        assert response.success
        assert response.pipeline_used == PipelineType.SEMANTIC

    def test_generate_with_explicit_pipeline(self):
        """Generate with explicit pipeline selection."""
        response = generate(
            target={"final_magnitude": ">= 1.0"},
            pipeline=PipelineType.DETERMINISTIC,
            selection_config={"max_results": 3},
        )
        assert response.pipeline_used == PipelineType.DETERMINISTIC

    def test_generate_auto_routing(self):
        """Generate auto-routes based on input."""
        # With constraints only → Pipeline A
        resp_a = generate(
            target={"final_magnitude": ">= 1.0"},
            selection_config={"max_results": 3},
        )
        assert resp_a.pipeline_used == PipelineType.DETERMINISTIC

        # With intent only → Pipeline B
        resp_b = generate(
            intent="calm gentle",
            selection_config={"max_results": 3},
        )
        assert resp_b.pipeline_used == PipelineType.SEMANTIC
