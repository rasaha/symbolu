"""
LCM Integration Tests

Tests simulating integration with TTOR (Two-Tier Ontology Router):
- Build LCMInput from TTOR RouterContext/RoutingPlan equivalents
- Validate LCM behavior under various routing scenarios
- Test task type detection with realistic TTOR-like inputs
- Verify recommended engine is appropriate for downstream Fusion/Renderer
"""

import json
import pytest
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any

from symbolu.mechanical.lcm.lcm_engine import LCMEngine, get_lcm_engine
from symbolu.mechanical.lcm.models import LCMInput, LowContextMap


# =============================================================================
# MOCK TTOR MODELS (to avoid circular imports)
# =============================================================================
# These are lightweight mock versions of TTOR models for testing purposes.
# They mirror the interface of the real TTOR models without triggering
# heavy pipeline imports.


class Tier(str, Enum):
    """Mock TTOR Tier enum."""
    LOWER = "lower"
    UPPER = "upper"
    HYBRID = "hybrid"


class FlowMode(str, Enum):
    """Mock TTOR FlowMode enum."""
    OUTER_ONLY = "outer_only"
    OUTER_PLUS_INNER = "outer_plus_inner"
    INNER_PRIORITY = "inner_priority"


@dataclass
class MockRouterContext:
    """Mock TTOR RouterContext for testing."""
    text: str
    aspect_probs: Dict[str, float]
    H_D: float
    H_G: float
    H_K: float = 0.0
    anchor_scores: Dict[str, float] = field(default_factory=dict)
    domain: str = "generic"
    risk_level: str = "low"
    long_arc_tension: float = 0.0


@dataclass
class MockRoutingPlan:
    """Mock TTOR RoutingPlan for testing."""
    tier: Tier
    flow_mode: FlowMode
    preferred_engine_family: str
    use_hrm: bool
    use_lcm: bool
    use_lam: bool
    regulated_mode: bool
    allow_metaphor: bool
    explanation: str
    debug: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def lcm_engine() -> LCMEngine:
    """Create a fresh LCM engine for integration tests."""
    return LCMEngine()


def build_lcm_input_from_context(
    router_context: MockRouterContext,
    routing_plan: MockRoutingPlan,
) -> LCMInput:
    """
    Build LCMInput from TTOR RouterContext and RoutingPlan.

    This simulates how the pipeline would construct LCMInput
    from TTOR outputs.

    Args:
        router_context: TTOR input context with text/aspects/anchors/entropy.
        routing_plan: TTOR output plan with tier/flow_mode decisions.

    Returns:
        LCMInput for processing by LCMEngine.
    """
    return LCMInput(
        text=router_context.text,
        domain=routing_plan.debug.get("domain", router_context.domain),
        aspect_probs=router_context.aspect_probs,
        anchor_scores=router_context.anchor_scores,
        H_D=router_context.H_D,
        H_G=router_context.H_G,
        H_K=router_context.H_K,
        tier=routing_plan.tier.value,
        flow_mode=routing_plan.flow_mode.value,
    )


# =============================================================================
# TTOR INTEGRATION SCENARIOS
# =============================================================================


class TestTTORIntegration:
    """Tests simulating TTOR -> LCM integration."""

    def test_lower_tier_task_domain(self, lcm_engine: LCMEngine) -> None:
        """Test LCM with lower tier task domain from TTOR."""
        router_context = MockRouterContext(
            text="Sort this list alphabetically",
            aspect_probs={
                "Execution": 0.6,
                "Form": 0.2,
                "Cognition": 0.1,
                "Identity": 0.1,
            },
            anchor_scores={
                "Needs": 0.5,
                "Exchange": 0.3,
                "Challenge": 0.2,
            },
            H_D=0.4,  # Low entropy
            H_G=0.25,
            H_K=0.3,
            domain="task",
            risk_level="low",
        )

        routing_plan = MockRoutingPlan(
            tier=Tier.LOWER,
            flow_mode=FlowMode.OUTER_ONLY,
            preferred_engine_family="renderer_only",
            use_hrm=False,
            use_lcm=True,  # LCM should be used
            use_lam=False,
            regulated_mode=False,
            allow_metaphor=False,
            explanation="Lower tier for simple task query",
            debug={"domain": "task", "entropy_mix": 0.18},
        )

        lcm_input = build_lcm_input_from_context(router_context, routing_plan)
        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.task_type == "action"
        assert lcm_map.entropy_regime == "low"
        assert lcm_map.recommended_engine == "fusion"
        assert "sort" in lcm_map.key_terms
        assert "list" in lcm_map.key_terms

    def test_lower_tier_math_domain(self, lcm_engine: LCMEngine) -> None:
        """Test LCM with lower tier math domain from TTOR."""
        router_context = MockRouterContext(
            text="25 17",  # Short text with just numbers for renderer_only
            aspect_probs={
                "Cognition": 0.7,
                "Execution": 0.2,
                "Form": 0.1,
            },
            anchor_scores={
                "Needs": 0.6,
                "Exchange": 0.3,
                "Challenge": 0.1,
            },
            H_D=0.3,
            H_G=0.2,
            H_K=0.25,
            domain="math",
            risk_level="low",
        )

        routing_plan = MockRoutingPlan(
            tier=Tier.LOWER,
            flow_mode=FlowMode.OUTER_ONLY,
            preferred_engine_family="renderer_only",
            use_hrm=False,
            use_lcm=True,
            use_lam=False,
            regulated_mode=False,
            allow_metaphor=False,
            explanation="Lower tier for simple math query",
            debug={"domain": "math", "entropy_mix": 0.14},
        )

        lcm_input = build_lcm_input_from_context(router_context, routing_plan)
        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.task_type == "math"
        assert lcm_map.entropy_regime == "low"
        assert lcm_map.recommended_engine == "renderer_only"
        assert lcm_map.numeric_features["count"] == 2
        assert lcm_map.numeric_features["sum"] == 42

    def test_lower_tier_code_domain(self, lcm_engine: LCMEngine) -> None:
        """Test LCM with lower tier code domain from TTOR."""
        router_context = MockRouterContext(
            text="Fix the function in main.py",
            aspect_probs={
                "Execution": 0.5,
                "Cognition": 0.3,
                "Form": 0.2,
            },
            anchor_scores={
                "Needs": 0.5,
                "Exchange": 0.3,
                "Challenge": 0.2,
            },
            H_D=0.5,
            H_G=0.3,
            H_K=0.35,
            domain="code",
            risk_level="low",
        )

        routing_plan = MockRoutingPlan(
            tier=Tier.LOWER,
            flow_mode=FlowMode.OUTER_ONLY,
            preferred_engine_family="fusion",
            use_hrm=False,
            use_lcm=True,
            use_lam=False,
            regulated_mode=False,
            allow_metaphor=False,
            explanation="Lower tier for code task",
            debug={"domain": "code", "entropy_mix": 0.22},
        )

        lcm_input = build_lcm_input_from_context(router_context, routing_plan)
        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.task_type == "code"
        assert lcm_map.recommended_engine == "fusion"
        assert "main" in lcm_map.key_terms
        assert "function" in lcm_map.key_terms

    def test_lower_tier_lookup_domain(self, lcm_engine: LCMEngine) -> None:
        """Test LCM with lower tier lookup domain from TTOR."""
        router_context = MockRouterContext(
            text="Where is the config file?",
            aspect_probs={
                "Execution": 0.4,
                "Form": 0.4,
                "Cognition": 0.2,
            },
            anchor_scores={
                "Needs": 0.6,
                "Exchange": 0.3,
                "Challenge": 0.1,
            },
            H_D=0.4,
            H_G=0.25,
            H_K=0.3,
            domain="lookup",
            risk_level="low",
        )

        routing_plan = MockRoutingPlan(
            tier=Tier.LOWER,
            flow_mode=FlowMode.OUTER_ONLY,
            preferred_engine_family="fusion",
            use_hrm=False,
            use_lcm=True,
            use_lam=False,
            regulated_mode=False,
            allow_metaphor=False,
            explanation="Lower tier for lookup query",
            debug={"domain": "lookup", "entropy_mix": 0.18},
        )

        lcm_input = build_lcm_input_from_context(router_context, routing_plan)
        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.task_type == "lookup"
        assert lcm_map.recommended_engine == "fusion"
        assert "config" in lcm_map.key_terms
        assert "file" in lcm_map.key_terms


# =============================================================================
# ENTROPY-BASED ROUTING SCENARIOS
# =============================================================================


class TestEntropyScenarios:
    """Tests for entropy-based LCM behavior."""

    def test_low_entropy_simple_query(self, lcm_engine: LCMEngine) -> None:
        """Low entropy should result in 'low' regime."""
        lcm_input = LCMInput(
            text="Sort this list",
            domain="task",
            aspect_probs={"Execution": 0.8, "Form": 0.2},
            anchor_scores={"Needs": 0.7, "Exchange": 0.3},
            H_D=0.3,
            H_G=0.2,
            H_K=0.25,
            tier="lower",
            flow_mode="outer_only",
        )

        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.entropy_regime == "low"

    def test_medium_entropy_moderate_query(self, lcm_engine: LCMEngine) -> None:
        """Medium entropy should result in 'medium' regime."""
        lcm_input = LCMInput(
            text="Help me understand this code pattern",
            domain="code",
            aspect_probs={"Execution": 0.4, "Cognition": 0.4, "Reasoning": 0.2},
            anchor_scores={"Needs": 0.4, "Exchange": 0.3, "Challenge": 0.3},
            H_D=1.1,
            H_G=0.55,
            H_K=0.8,
            tier="hybrid",
            flow_mode="outer_plus_inner",
        )

        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.entropy_regime == "medium"

    def test_high_entropy_complex_query(self, lcm_engine: LCMEngine) -> None:
        """High entropy should result in 'high' regime."""
        lcm_input = LCMInput(
            text="Calculate the sum of 10 and 20 and 30",
            domain="math",
            aspect_probs={"Cognition": 0.5, "Reasoning": 0.3, "Purpose": 0.2},
            anchor_scores={"Needs": 0.3, "Challenge": 0.4, "Change": 0.3},
            H_D=2.0,
            H_G=0.95,
            H_K=1.4,
            tier="upper",
            flow_mode="inner_priority",
        )

        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.entropy_regime == "high"


# =============================================================================
# COMPLEXITY SCENARIOS
# =============================================================================


class TestComplexityScenarios:
    """Tests for complexity-based LCM behavior."""

    def test_simple_query_low_complexity(self, lcm_engine: LCMEngine) -> None:
        """Simple short query should have low complexity."""
        lcm_input = LCMInput(
            text="5 3",  # Very short text: 2 tokens / 7 = 0.29
            domain="math",
            aspect_probs={"Cognition": 0.8},
            anchor_scores={"Needs": 0.7},
            H_D=0.3,
            H_G=0.2,
            H_K=0.25,
            tier="lower",
            flow_mode="outer_only",
        )

        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.complexity_score < 0.5
        # Simple math -> renderer_only (complexity < 0.3)
        assert lcm_map.recommended_engine == "renderer_only"

    def test_complex_query_high_complexity(self, lcm_engine: LCMEngine) -> None:
        """Complex query should have high complexity."""
        lcm_input = LCMInput(
            text="Sort this list alphabetically then reverse it and find the middle element",
            domain="task",
            aspect_probs={"Execution": 0.7, "Cognition": 0.3},
            anchor_scores={"Needs": 0.5, "Challenge": 0.5},
            H_D=0.5,
            H_G=0.3,
            H_K=0.35,
            tier="lower",
            flow_mode="outer_only",
        )

        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.complexity_score == 1.0  # Capped at 1.0


# =============================================================================
# PIPELINE INTEGRATION SIMULATION
# =============================================================================


class TestPipelineIntegration:
    """Tests simulating full pipeline integration."""

    def test_lcm_output_structure_for_fusion(self, lcm_engine: LCMEngine) -> None:
        """LCM output should have all fields needed by Fusion engine."""
        lcm_input = LCMInput(
            text="Sort this list and count the items",
            domain="task",
            aspect_probs={"Execution": 0.6, "Cognition": 0.4},
            anchor_scores={"Needs": 0.5, "Exchange": 0.3, "Challenge": 0.2},
            H_D=0.5,
            H_G=0.3,
            H_K=0.35,
            tier="lower",
            flow_mode="outer_only",
        )

        lcm_map = lcm_engine.build_map(lcm_input)

        # Verify all required fields for Fusion/Renderer
        assert isinstance(lcm_map.task_type, str)
        assert isinstance(lcm_map.key_terms, list)
        assert isinstance(lcm_map.numeric_features, dict)
        assert isinstance(lcm_map.complexity_score, float)
        assert isinstance(lcm_map.entropy_regime, str)
        assert isinstance(lcm_map.recommended_engine, str)

        # Complexity should be in [0, 1]
        assert 0.0 <= lcm_map.complexity_score <= 1.0

        # Entropy regime should be valid
        assert lcm_map.entropy_regime in ("low", "medium", "high")

        # Recommended engine should be valid
        assert lcm_map.recommended_engine in ("renderer_only", "fusion", "persona")

    def test_serialization_for_pipeline_context(self, lcm_engine: LCMEngine) -> None:
        """LCM map should serialize properly for pipeline context."""
        lcm_input = LCMInput(
            text="Calculate 10 plus 20",
            domain="math",
            aspect_probs={"Cognition": 0.8, "Execution": 0.2},
            anchor_scores={"Needs": 0.6, "Exchange": 0.4},
            H_D=0.4,
            H_G=0.25,
            H_K=0.3,
            tier="lower",
            flow_mode="outer_only",
        )

        lcm_map = lcm_engine.build_map(lcm_input)
        serialized = lcm_map.to_dict()

        # Should be JSON-serializable (no objects, only primitives)
        json_str = json.dumps(serialized)
        assert isinstance(json_str, str)

        # Should round-trip
        deserialized = json.loads(json_str)
        assert deserialized["task_type"] == lcm_map.task_type
        assert deserialized["entropy_regime"] == lcm_map.entropy_regime
        assert deserialized["recommended_engine"] == lcm_map.recommended_engine

    def test_deterministic_output(self, lcm_engine: LCMEngine) -> None:
        """LCM should produce identical output for identical input."""
        lcm_input = LCMInput(
            text="Sort this list alphabetically",
            domain="task",
            aspect_probs={"Execution": 0.7, "Form": 0.3},
            anchor_scores={"Needs": 0.5, "Exchange": 0.5},
            H_D=0.4,
            H_G=0.25,
            H_K=0.3,
            tier="lower",
            flow_mode="outer_only",
        )

        # Run multiple times
        results = [lcm_engine.build_map(lcm_input) for _ in range(5)]

        # All results should be identical
        first = results[0].to_dict()
        for result in results[1:]:
            assert result.to_dict() == first


# =============================================================================
# ENGINE RECOMMENDATION SCENARIOS
# =============================================================================


class TestEngineRecommendation:
    """Tests for engine recommendation logic."""

    def test_simple_math_recommends_renderer(self, lcm_engine: LCMEngine) -> None:
        """Simple math query should recommend renderer_only."""
        lcm_input = LCMInput(
            text="2 2",  # Very short: 2 tokens / 7 = 0.29 < 0.3
            domain="math",
            aspect_probs={"Cognition": 0.9},
            anchor_scores={"Needs": 0.8},
            H_D=0.2,
            H_G=0.1,
            H_K=0.15,
            tier="lower",
            flow_mode="outer_only",
        )

        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.task_type == "math"
        assert lcm_map.complexity_score < 0.3
        assert lcm_map.recommended_engine == "renderer_only"

    def test_code_query_recommends_fusion(self, lcm_engine: LCMEngine) -> None:
        """Code query should recommend fusion."""
        lcm_input = LCMInput(
            text="Write a function to calculate sum",
            domain="code",
            aspect_probs={"Execution": 0.6, "Cognition": 0.4},
            anchor_scores={"Needs": 0.5, "Challenge": 0.5},
            H_D=0.5,
            H_G=0.3,
            H_K=0.35,
            tier="lower",
            flow_mode="outer_only",
        )

        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.task_type == "code"
        assert lcm_map.recommended_engine == "fusion"

    def test_lookup_query_recommends_fusion(self, lcm_engine: LCMEngine) -> None:
        """Lookup query should recommend fusion."""
        lcm_input = LCMInput(
            text="What is the capital of France?",
            domain="lookup",
            aspect_probs={"Cognition": 0.6, "Form": 0.4},
            anchor_scores={"Needs": 0.7, "Exchange": 0.3},
            H_D=0.4,
            H_G=0.25,
            H_K=0.3,
            tier="lower",
            flow_mode="outer_only",
        )

        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.task_type == "lookup"
        assert lcm_map.recommended_engine == "fusion"

    def test_generic_query_recommends_persona(self, lcm_engine: LCMEngine) -> None:
        """Generic query should recommend persona."""
        lcm_input = LCMInput(
            text="Hello, how are you today?",
            domain="generic",
            aspect_probs={"Identity": 0.5, "Cognition": 0.5},
            anchor_scores={"Belonging": 0.5, "Relation": 0.5},
            H_D=0.6,
            H_G=0.4,
            H_K=0.5,
            tier="hybrid",
            flow_mode="outer_plus_inner",
        )

        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.task_type == "generic"
        assert lcm_map.recommended_engine == "persona"


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_lcm_engine_returns_singleton(self) -> None:
        """get_lcm_engine should return the same instance."""
        engine1 = get_lcm_engine()
        engine2 = get_lcm_engine()
        assert engine1 is engine2


# =============================================================================
# END-TO-END SCENARIOS
# =============================================================================


class TestEndToEndScenarios:
    """End-to-end test scenarios."""

    @pytest.mark.parametrize(
        "text,expected_task_type,expected_engine",
        [
            ("Sort this list", "action", "fusion"),
            ("5 3", "math", "renderer_only"),  # Short math -> renderer_only
            ("Open main.py", "code", "fusion"),
            ("Where is the file?", "lookup", "fusion"),
            ("Hello world", "generic", "persona"),
            ("Add 5 and 7", "math", "persona"),  # 4 tokens = complexity > 0.3 -> persona
            ("Arrange items by size", "action", "fusion"),
            ("Create a class for users", "code", "fusion"),
            ("What is the answer?", "lookup", "fusion"),
            ("Calculate 100 divided by 5", "math", "persona"),  # 5 tokens = complexity > 0.3 -> persona
        ],
    )
    def test_task_type_and_engine_mapping(
        self,
        lcm_engine: LCMEngine,
        text: str,
        expected_task_type: str,
        expected_engine: str,
    ) -> None:
        """Test task type detection and engine recommendation mapping."""
        lcm_input = LCMInput(
            text=text,
            domain="generic",
            aspect_probs={"Execution": 0.5, "Cognition": 0.5},
            anchor_scores={"Needs": 0.5, "Exchange": 0.5},
            H_D=0.3,  # Low entropy for simple renderer recommendations
            H_G=0.2,
            H_K=0.25,
            tier="lower",
            flow_mode="outer_only",
        )

        lcm_map = lcm_engine.build_map(lcm_input)

        assert lcm_map.task_type == expected_task_type
        assert lcm_map.recommended_engine == expected_engine

    def test_complete_workflow_simulation(self, lcm_engine: LCMEngine) -> None:
        """Simulate complete TTOR -> LCM -> Pipeline workflow."""
        # Step 1: TTOR creates RouterContext
        router_context = MockRouterContext(
            text="Fix the function in utils.py",
            aspect_probs={
                "Execution": 0.6,
                "Form": 0.3,
                "Cognition": 0.1,
            },
            anchor_scores={
                "Needs": 0.5,
                "Exchange": 0.3,
                "Challenge": 0.2,
            },
            H_D=0.4,
            H_G=0.25,
            H_K=0.3,
            domain="task",
        )

        # Step 2: TTOR produces RoutingPlan with use_lcm=True
        routing_plan = MockRoutingPlan(
            tier=Tier.LOWER,
            flow_mode=FlowMode.OUTER_ONLY,
            preferred_engine_family="fusion",
            use_hrm=False,
            use_lcm=True,
            use_lam=False,
            regulated_mode=False,
            allow_metaphor=False,
            explanation="Lower tier for task domain with low entropy",
            debug={"domain": "task", "entropy_mix": 0.18},
        )

        # Step 3: Pipeline builds LCMInput
        lcm_input = build_lcm_input_from_context(router_context, routing_plan)

        # Step 4: LCM engine processes input
        lcm_map = lcm_engine.build_map(lcm_input)

        # Step 5: Verify output is suitable for Fusion/Renderer
        assert lcm_map.task_type == "code"  # .py extension detected
        assert lcm_map.entropy_regime == "low"
        assert lcm_map.recommended_engine == "fusion"
        assert len(lcm_map.key_terms) > 0

        # Step 6: Output can be serialized for pipeline context
        context_data = lcm_map.to_dict()
        assert "task_type" in context_data
        assert "key_terms" in context_data
        assert "recommended_engine" in context_data
