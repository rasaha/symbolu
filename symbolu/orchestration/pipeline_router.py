"""
Dual-Pipeline Router

Dynamically routes requests between:
- Pipeline A: Deterministic constraint satisfaction (Phase-7 current)
- Pipeline B: Extended generation with semantic capabilities (future)

The router examines the request context and selects the appropriate pipeline
while presenting a unified API to consumers.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Union, Callable
from abc import ABC, abstractmethod


class PipelineType(Enum):
    """Available pipeline types."""
    DETERMINISTIC = "deterministic"      # Pipeline A: Current Phase-7
    SEMANTIC = "semantic"                # Pipeline B: Extended with semantics
    HYBRID = "hybrid"                    # Uses both pipelines
    AUTO = "auto"                        # Router decides based on request


class RequestIntent(Enum):
    """Detected intent categories for routing."""
    CONSTRAINT_SATISFACTION = "constraint_satisfaction"  # → Pipeline A
    CREATIVE_GENERATION = "creative_generation"          # → Pipeline B
    CONVERSATIONAL = "conversational"                    # → Pipeline B
    EXPLORATION = "exploration"                          # → Pipeline A or B
    VALIDATION = "validation"                            # → Pipeline A
    UNKNOWN = "unknown"                                  # → Default pipeline


@dataclass(frozen=True)
class RoutingDecision:
    """Result of routing analysis."""
    pipeline: PipelineType
    intent: RequestIntent
    confidence: float  # 0.0 to 1.0
    reasoning: str     # Mechanical explanation (no interpretation)


@dataclass(frozen=True)
class UnifiedRequest:
    """
    Unified request format that can be routed to either pipeline.

    Contains both mechanical constraints (for Pipeline A) and
    semantic hints (for Pipeline B).
    """
    # Core request
    request_type: str

    # Pipeline A fields (mechanical)
    target_constraints: Optional[Dict[str, Any]] = None
    generation_config: Optional[Dict[str, Any]] = None
    selection_config: Optional[Dict[str, Any]] = None

    # Pipeline B fields (semantic - ignored by Pipeline A)
    semantic_intent: Optional[str] = None
    context_history: Optional[list] = None
    creativity_level: Optional[float] = None  # 0.0 = deterministic, 1.0 = max creativity

    # Routing hints
    preferred_pipeline: PipelineType = PipelineType.AUTO
    fallback_allowed: bool = True


@dataclass(frozen=True)
class UnifiedResponse:
    """
    Unified response format from either pipeline.

    Contains common fields that both pipelines produce,
    plus pipeline-specific metadata.
    """
    # Common fields
    success: bool
    sequences: tuple  # Generated sequences

    # Pipeline metadata
    pipeline_used: PipelineType
    deterministic: bool

    # Pipeline A specific (always present, may be empty for Pipeline B)
    constraint_satisfaction: Optional[Dict[str, Any]] = None
    execution_metadata: Optional[Dict[str, Any]] = None

    # Pipeline B specific (only present for Pipeline B)
    semantic_projection: Optional[Dict[str, Any]] = None
    conversation_state: Optional[Dict[str, Any]] = None


class PipelineInterface(ABC):
    """Abstract interface that both pipelines must implement."""

    @abstractmethod
    def execute(self, request: UnifiedRequest) -> UnifiedResponse:
        """Execute the pipeline on a unified request."""
        pass

    @abstractmethod
    def can_handle(self, request: UnifiedRequest) -> bool:
        """Check if this pipeline can handle the request."""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """Return capability flags for this pipeline."""
        pass


class PipelineADeterministic(PipelineInterface):
    """
    Pipeline A: Deterministic Constraint Satisfaction

    Wraps the current Phase-7 implementation.
    """

    def __init__(self):
        # Import Phase-7 components
        from symbolu.phases.phase7_targeted_generation import execute_phase7
        self._execute_phase7 = execute_phase7

    def execute(self, request: UnifiedRequest) -> UnifiedResponse:
        """Execute deterministic constraint satisfaction."""
        if not self.can_handle(request):
            return UnifiedResponse(
                success=False,
                sequences=tuple(),
                pipeline_used=PipelineType.DETERMINISTIC,
                deterministic=True,
                constraint_satisfaction={"error": "Cannot handle request"},
            )

        # Extract Phase-7 parameters
        target = request.target_constraints or {"final_magnitude": ">= 1.0"}
        gen_config = request.generation_config or {
            "max_sequence_length": 4,
            "max_candidates": None,
        }
        sel_config = request.selection_config or {
            "max_results": 10,
            "scoring_mode": "binary",
        }

        # Execute Phase-7
        result = self._execute_phase7(target, gen_config, sel_config)

        # Convert to unified response
        sequences = tuple(r.sequence for r in result.results)

        return UnifiedResponse(
            success=len(result.errors) == 0,
            sequences=sequences,
            pipeline_used=PipelineType.DETERMINISTIC,
            deterministic=True,
            constraint_satisfaction={
                "results_count": len(result.results),
                "satisfying_count": result.metadata.candidates_satisfying,
                "feasible": result.metadata.target_feasible,
            },
            execution_metadata={
                "candidates_generated": result.metadata.candidates_generated,
                "candidates_checked": result.metadata.candidates_checked,
                "early_terminated": result.metadata.early_terminated,
                "cache_hits": result.metadata.cache_hits,
            },
        )

    def can_handle(self, request: UnifiedRequest) -> bool:
        """Pipeline A can handle requests with mechanical constraints."""
        # Can handle if we have target constraints
        if request.target_constraints:
            return True
        # Can handle exploration without semantic intent
        if request.semantic_intent is None:
            return True
        return False

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "deterministic": True,
            "constraint_satisfaction": True,
            "exhaustive_search": True,
            "semantic_understanding": False,
            "creative_generation": False,
            "conversation": False,
            "learning": False,
        }


class PipelineBSemantic(PipelineInterface):
    """
    Pipeline B: Semantic/Creative Generation

    Extended pipeline with semantic projection capabilities.
    This is a placeholder for future implementation.
    """

    def __init__(self, llm_adapter: Optional[Callable] = None):
        self._llm_adapter = llm_adapter
        self._pipeline_a = PipelineADeterministic()

    def execute(self, request: UnifiedRequest) -> UnifiedResponse:
        """Execute semantic generation."""
        if not self.can_handle(request):
            return UnifiedResponse(
                success=False,
                sequences=tuple(),
                pipeline_used=PipelineType.SEMANTIC,
                deterministic=False,
                semantic_projection={"error": "Pipeline B not fully implemented"},
            )

        # FUTURE IMPLEMENTATION:
        # 1. Parse semantic intent
        # 2. Translate to mechanical constraints
        # 3. Execute Pipeline A for valid generation
        # 4. Project results through semantic layer
        # 5. Return with semantic annotations

        # For now, delegate to Pipeline A with translated constraints
        translated_request = self._translate_semantic_to_mechanical(request)
        base_response = self._pipeline_a.execute(translated_request)

        # Add semantic projection (placeholder)
        return UnifiedResponse(
            success=base_response.success,
            sequences=base_response.sequences,
            pipeline_used=PipelineType.SEMANTIC,
            deterministic=False,  # Semantic layer adds non-determinism
            constraint_satisfaction=base_response.constraint_satisfaction,
            execution_metadata=base_response.execution_metadata,
            semantic_projection={
                "intent_parsed": request.semantic_intent,
                "projection_applied": False,  # Not yet implemented
            },
            conversation_state={
                "context_length": len(request.context_history or []),
            },
        )

    def _translate_semantic_to_mechanical(
        self,
        request: UnifiedRequest
    ) -> UnifiedRequest:
        """
        Translate semantic intent to mechanical constraints.

        FUTURE: This would use an LLM or learned mapping.
        For now, uses simple heuristics.
        """
        intent = request.semantic_intent or ""
        constraints = request.target_constraints or {}

        # Simple keyword-based translation (placeholder)
        if "calm" in intent.lower() or "gentle" in intent.lower():
            constraints.setdefault("final_magnitude", "in [1.0, 1.2]")
            constraints.setdefault("monotonic_decreasing(steps[].magnitude)", "== true")

        if "energetic" in intent.lower() or "active" in intent.lower():
            constraints.setdefault("final_magnitude", ">= 1.3")
            constraints.setdefault("len(steps)", ">= 3")

        if "short" in intent.lower():
            constraints.setdefault("len(steps)", "<= 2")

        if "long" in intent.lower():
            constraints.setdefault("len(steps)", ">= 4")

        return UnifiedRequest(
            request_type=request.request_type,
            target_constraints=constraints,
            generation_config=request.generation_config,
            selection_config=request.selection_config,
            semantic_intent=request.semantic_intent,
            context_history=request.context_history,
            creativity_level=request.creativity_level,
            preferred_pipeline=PipelineType.SEMANTIC,
        )

    def can_handle(self, request: UnifiedRequest) -> bool:
        """Pipeline B can handle semantic/creative requests."""
        # Can handle if we have semantic intent
        if request.semantic_intent:
            return True
        # Can handle if creativity is requested
        if request.creativity_level and request.creativity_level > 0:
            return True
        # Can handle conversation
        if request.context_history:
            return True
        return False

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "deterministic": False,
            "constraint_satisfaction": True,  # Via Pipeline A delegation
            "exhaustive_search": False,
            "semantic_understanding": True,  # Future
            "creative_generation": True,     # Future
            "conversation": True,            # Future
            "learning": False,               # Not planned
        }


class PipelineRouter:
    """
    Dynamic router that selects between Pipeline A and Pipeline B
    based on request context.
    """

    def __init__(
        self,
        pipeline_a: Optional[PipelineInterface] = None,
        pipeline_b: Optional[PipelineInterface] = None,
        default_pipeline: PipelineType = PipelineType.DETERMINISTIC,
    ):
        self._pipeline_a = pipeline_a or PipelineADeterministic()
        self._pipeline_b = pipeline_b or PipelineBSemantic()
        self._default_pipeline = default_pipeline

    def route(self, request: UnifiedRequest) -> UnifiedResponse:
        """
        Route request to appropriate pipeline.

        Routing logic:
        1. If preferred_pipeline is specified (not AUTO), use it
        2. Otherwise, analyze request to determine best pipeline
        3. Fall back to default if analysis fails
        """
        decision = self._make_routing_decision(request)

        if decision.pipeline == PipelineType.DETERMINISTIC:
            return self._pipeline_a.execute(request)
        elif decision.pipeline == PipelineType.SEMANTIC:
            return self._pipeline_b.execute(request)
        elif decision.pipeline == PipelineType.HYBRID:
            return self._execute_hybrid(request)
        else:
            # Default fallback
            return self._pipeline_a.execute(request)

    def _make_routing_decision(self, request: UnifiedRequest) -> RoutingDecision:
        """Analyze request and decide which pipeline to use."""

        # Honor explicit preference
        if request.preferred_pipeline != PipelineType.AUTO:
            return RoutingDecision(
                pipeline=request.preferred_pipeline,
                intent=RequestIntent.UNKNOWN,
                confidence=1.0,
                reasoning="Explicit pipeline preference specified",
            )

        # Detect intent
        intent = self._detect_intent(request)

        # Route based on intent
        if intent == RequestIntent.CONSTRAINT_SATISFACTION:
            return RoutingDecision(
                pipeline=PipelineType.DETERMINISTIC,
                intent=intent,
                confidence=0.95,
                reasoning="Request contains mechanical constraints only",
            )

        elif intent == RequestIntent.VALIDATION:
            return RoutingDecision(
                pipeline=PipelineType.DETERMINISTIC,
                intent=intent,
                confidence=0.99,
                reasoning="Validation requires deterministic execution",
            )

        elif intent == RequestIntent.CREATIVE_GENERATION:
            return RoutingDecision(
                pipeline=PipelineType.SEMANTIC,
                intent=intent,
                confidence=0.85,
                reasoning="Creative request benefits from semantic layer",
            )

        elif intent == RequestIntent.CONVERSATIONAL:
            return RoutingDecision(
                pipeline=PipelineType.SEMANTIC,
                intent=intent,
                confidence=0.90,
                reasoning="Conversation requires context and semantic understanding",
            )

        elif intent == RequestIntent.EXPLORATION:
            # Exploration can go either way - prefer deterministic for reproducibility
            return RoutingDecision(
                pipeline=PipelineType.DETERMINISTIC,
                intent=intent,
                confidence=0.70,
                reasoning="Exploration defaults to deterministic for reproducibility",
            )

        else:
            # Unknown intent - use default
            return RoutingDecision(
                pipeline=self._default_pipeline,
                intent=intent,
                confidence=0.50,
                reasoning="Unknown intent, using default pipeline",
            )

    def _detect_intent(self, request: UnifiedRequest) -> RequestIntent:
        """Detect the intent category of a request."""

        # Has semantic intent → creative or conversational
        if request.semantic_intent:
            if request.context_history:
                return RequestIntent.CONVERSATIONAL
            return RequestIntent.CREATIVE_GENERATION

        # Has conversation history → conversational
        if request.context_history:
            return RequestIntent.CONVERSATIONAL

        # Has creativity level > 0 → creative
        if request.creativity_level and request.creativity_level > 0:
            return RequestIntent.CREATIVE_GENERATION

        # Has target constraints → constraint satisfaction
        if request.target_constraints:
            return RequestIntent.CONSTRAINT_SATISFACTION

        # Request type hints
        if request.request_type == "validate":
            return RequestIntent.VALIDATION
        if request.request_type == "explore":
            return RequestIntent.EXPLORATION
        if request.request_type == "generate":
            return RequestIntent.CONSTRAINT_SATISFACTION

        return RequestIntent.UNKNOWN

    def _execute_hybrid(self, request: UnifiedRequest) -> UnifiedResponse:
        """
        Execute hybrid mode: Pipeline A for generation, Pipeline B for projection.
        """
        # First, generate with Pipeline A
        a_response = self._pipeline_a.execute(request)

        if not a_response.success:
            return a_response

        # Then, project through Pipeline B (if it can add value)
        if request.semantic_intent or request.context_history:
            # Create a request for semantic projection only
            projection_request = UnifiedRequest(
                request_type="project",
                semantic_intent=request.semantic_intent,
                context_history=request.context_history,
                preferred_pipeline=PipelineType.SEMANTIC,
            )
            # This would add semantic annotations to the results
            # For now, just return Pipeline A results

        return UnifiedResponse(
            success=a_response.success,
            sequences=a_response.sequences,
            pipeline_used=PipelineType.HYBRID,
            deterministic=True,  # Core generation is deterministic
            constraint_satisfaction=a_response.constraint_satisfaction,
            execution_metadata=a_response.execution_metadata,
            semantic_projection={"hybrid_mode": True},
        )

    def get_pipeline_status(self) -> Dict[str, Any]:
        """Return status of both pipelines."""
        return {
            "pipeline_a": {
                "type": "deterministic",
                "available": True,
                "capabilities": self._pipeline_a.get_capabilities(),
            },
            "pipeline_b": {
                "type": "semantic",
                "available": True,
                "capabilities": self._pipeline_b.get_capabilities(),
            },
            "default_pipeline": self._default_pipeline.value,
        }


# Convenience function for simple usage
def generate(
    target: Optional[Dict[str, Any]] = None,
    intent: Optional[str] = None,
    pipeline: PipelineType = PipelineType.AUTO,
    **kwargs
) -> UnifiedResponse:
    """
    Simple generation interface that auto-routes to appropriate pipeline.

    Args:
        target: Mechanical constraints (for Pipeline A)
        intent: Semantic intent string (for Pipeline B)
        pipeline: Explicit pipeline preference
        **kwargs: Additional configuration

    Returns:
        UnifiedResponse with generated sequences

    Examples:
        # Deterministic constraint satisfaction
        generate(target={"final_magnitude": ">= 1.3"})

        # Semantic/creative generation
        generate(intent="something calm and gentle")

        # Explicit pipeline selection
        generate(target={...}, pipeline=PipelineType.DETERMINISTIC)
    """
    request = UnifiedRequest(
        request_type="generate",
        target_constraints=target,
        semantic_intent=intent,
        generation_config=kwargs.get("generation_config"),
        selection_config=kwargs.get("selection_config"),
        context_history=kwargs.get("context_history"),
        creativity_level=kwargs.get("creativity_level"),
        preferred_pipeline=pipeline,
    )

    router = PipelineRouter()
    return router.route(request)
