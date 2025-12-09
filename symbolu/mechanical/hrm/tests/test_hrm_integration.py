"""
HRM Integration Tests

Tests simulating integration with TTOR (Two-Tier Ontology Router):
- Build HRMInput from TTOR RouterContext/RoutingPlan equivalents
- Validate HRM behavior under various routing scenarios
- Test conflict detection with realistic TTOR-like inputs
- Verify resolution hints are appropriate for downstream Fusion/DHA
"""

import pytest
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any

from symbolu.mechanical.hrm.hrm_engine import (
    HRMEngine,
    REFLECTIVE_DOMAINS,
    TASK_DOMAINS,
    H_D_MAX,
    H_G_MAX,
    H_K_MAX,
)
from symbolu.mechanical.hrm.models import HRMInput, HighResolutionMap


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
def hrm_engine() -> HRMEngine:
    """Create a fresh HRM engine for integration tests."""
    return HRMEngine()


def build_hrm_input_from_context(
    router_context: MockRouterContext,
    routing_plan: MockRoutingPlan,
) -> HRMInput:
    """
    Build HRMInput from TTOR RouterContext and RoutingPlan.

    This simulates how the pipeline would construct HRMInput
    from TTOR outputs.

    Args:
        router_context: TTOR input context with aspects/anchors/entropy.
        routing_plan: TTOR output plan with tier/flow_mode decisions.

    Returns:
        HRMInput for processing by HRMEngine.
    """
    return HRMInput(
        aspect_probs=router_context.aspect_probs,
        anchor_scores=router_context.anchor_scores,
        H_D=router_context.H_D,
        H_G=router_context.H_G,
        H_K=router_context.H_K,
        domain=routing_plan.debug.get("domain", router_context.domain),
        tier=routing_plan.tier.value,
        flow_mode=routing_plan.flow_mode.value,
    )


# =============================================================================
# TTOR INTEGRATION SCENARIOS
# =============================================================================


class TestTTORIntegration:
    """Tests simulating TTOR → HRM integration."""

    def test_upper_tier_therapy_domain(self, hrm_engine: HRMEngine) -> None:
        """Test HRM with upper tier therapy domain from TTOR."""
        # Simulate TTOR RouterContext for therapy/reflective scenario
        router_context = MockRouterContext(
            aspect_probs={
                "Execution": 0.1,
                "Identity": 0.15,
                "Form": 0.05,
                "Cognition": 0.1,
                "Agency": 0.1,
                "Reasoning": 0.1,
                "Purpose": 0.2,
                "Observation": 0.1,
                "Core": 0.05,
                "Universal": 0.05,
            },
            anchor_scores={
                "Needs": 0.2,
                "Exchange": 0.1,
                "Challenge": 0.15,
                "Belonging": 0.15,
                "Relation": 0.1,
                "Change": 0.1,
                "Meaning": 0.1,
                "Role": 0.05,
                "Collective": 0.05,
            },
            H_D=1.8,  # High dimensional entropy
            H_G=0.85,  # High guna entropy
            H_K=1.2,
            domain="therapy",
            risk_level="low",
            long_arc_tension=0.3,
        )

        # Simulate RoutingPlan output from TTOR
        routing_plan = MockRoutingPlan(
            tier=Tier.UPPER,
            flow_mode=FlowMode.INNER_PRIORITY,
            preferred_engine_family="fusion",
            use_hrm=True,
            use_lcm=False,
            use_lam=False,
            regulated_mode=False,
            allow_metaphor=True,
            explanation="Upper tier selected for therapy domain with high entropy",
            debug={"domain": "therapy", "entropy_mix": 0.72},
        )

        # Build HRMInput as pipeline would
        hrm_input = build_hrm_input_from_context(router_context, routing_plan)

        # Run HRM
        hrm_map = hrm_engine.build_map(hrm_input)

        # Assertions
        assert hrm_map.tier == "upper"
        assert hrm_map.domain == "therapy"
        assert hrm_map.entropy_profile["regime"] == "high"
        assert "upper_tier_deep_processing" in hrm_map.resolution_hints
        assert "reflective_domain_emphasis" in hrm_map.resolution_hints
        assert "therapeutic_sensitivity" in hrm_map.resolution_hints

    def test_lower_tier_code_domain(self, hrm_engine: HRMEngine) -> None:
        """Test HRM with lower tier code domain from TTOR."""
        router_context = MockRouterContext(
            aspect_probs={
                "Execution": 0.4,
                "Identity": 0.1,
                "Form": 0.2,
                "Cognition": 0.15,
                "Agency": 0.05,
                "Reasoning": 0.05,
                "Purpose": 0.02,
                "Observation": 0.02,
                "Core": 0.005,
                "Universal": 0.005,
            },
            anchor_scores={
                "Needs": 0.4,
                "Exchange": 0.3,
                "Challenge": 0.2,
                "Belonging": 0.03,
                "Relation": 0.03,
                "Change": 0.02,
                "Meaning": 0.01,
                "Role": 0.005,
                "Collective": 0.005,
            },
            H_D=0.4,  # Low entropy
            H_G=0.25,
            H_K=0.3,
            domain="code",
            risk_level="low",
            long_arc_tension=0.1,
        )

        routing_plan = MockRoutingPlan(
            tier=Tier.LOWER,
            flow_mode=FlowMode.OUTER_ONLY,
            preferred_engine_family="renderer_only",
            use_hrm=True,  # HRM can be used in lower tier for certain scenarios
            use_lcm=True,
            use_lam=False,
            regulated_mode=False,
            allow_metaphor=False,
            explanation="Lower tier for concrete code task",
            debug={"domain": "code", "entropy_mix": 0.18},
        )

        hrm_input = build_hrm_input_from_context(router_context, routing_plan)
        hrm_map = hrm_engine.build_map(hrm_input)

        assert hrm_map.tier == "lower"
        assert hrm_map.domain == "code"
        assert hrm_map.entropy_profile["regime"] == "low"
        assert "lower_tier_concrete_focus" in hrm_map.resolution_hints
        assert "task_domain_efficiency" in hrm_map.resolution_hints
        assert "technical_precision" in hrm_map.resolution_hints

    def test_hybrid_tier_identity_domain(self, hrm_engine: HRMEngine) -> None:
        """Test HRM with hybrid tier identity domain from TTOR."""
        router_context = MockRouterContext(
            aspect_probs={
                "Execution": 0.15,
                "Identity": 0.25,  # Strong identity focus
                "Form": 0.1,
                "Cognition": 0.1,
                "Agency": 0.15,
                "Reasoning": 0.1,
                "Purpose": 0.1,
                "Observation": 0.03,
                "Core": 0.01,
                "Universal": 0.01,
            },
            anchor_scores={
                "Needs": 0.15,
                "Exchange": 0.1,
                "Challenge": 0.2,
                "Belonging": 0.15,
                "Relation": 0.15,
                "Change": 0.1,
                "Meaning": 0.1,
                "Role": 0.03,
                "Collective": 0.02,
            },
            H_D=1.2,
            H_G=0.6,
            H_K=0.8,
            domain="identity",
            risk_level="low",
            long_arc_tension=0.4,
        )

        routing_plan = MockRoutingPlan(
            tier=Tier.HYBRID,
            flow_mode=FlowMode.OUTER_PLUS_INNER,
            preferred_engine_family="fusion",
            use_hrm=True,
            use_lcm=True,
            use_lam=False,
            regulated_mode=False,
            allow_metaphor=True,
            explanation="Hybrid tier for identity exploration with balanced entropy",
            debug={"domain": "identity", "entropy_mix": 0.45},
        )

        hrm_input = build_hrm_input_from_context(router_context, routing_plan)
        hrm_map = hrm_engine.build_map(hrm_input)

        assert hrm_map.tier == "hybrid"
        assert hrm_map.domain == "identity"
        assert hrm_map.entropy_profile["regime"] == "medium"
        assert "hybrid_tier_balanced_approach" in hrm_map.resolution_hints
        assert "reflective_domain_emphasis" in hrm_map.resolution_hints
        assert "identity_exploration_support" in hrm_map.resolution_hints


# =============================================================================
# ENTROPY-BASED ROUTING SCENARIOS
# =============================================================================


class TestEntropyScenarios:
    """Tests for entropy-based HRM behavior."""

    def test_high_entropy_triggers_upper_tilt(self, hrm_engine: HRMEngine) -> None:
        """High entropy should trigger upper-tier oriented hints."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.2,
                "Identity": 0.2,
                "Purpose": 0.3,
                "Reasoning": 0.3,
            },
            anchor_scores={
                "Needs": 0.3,
                "Meaning": 0.4,
                "Change": 0.3,
            },
            H_D=2.1,  # ~91% of H_D_MAX
            H_G=0.95,  # ~86% of H_G_MAX
            H_K=1.4,  # ~87% of H_K_MAX
            domain="philosophy",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = hrm_engine.build_map(hrm_input)

        assert hrm_map.entropy_profile["regime"] == "high"
        assert "high_entropy_upper_tilt" in hrm_map.resolution_hints
        assert "uncertainty_acknowledgment" in hrm_map.resolution_hints

    def test_low_entropy_enables_confident_response(
        self, hrm_engine: HRMEngine
    ) -> None:
        """Low entropy should enable confident, stable responses."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.7,
                "Form": 0.2,
                "Cognition": 0.1,
            },
            anchor_scores={
                "Needs": 0.6,
                "Exchange": 0.3,
                "Challenge": 0.1,
            },
            H_D=0.2,
            H_G=0.1,
            H_K=0.15,
            domain="task",
            tier="lower",
            flow_mode="outer_only",
        )

        hrm_map = hrm_engine.build_map(hrm_input)

        assert hrm_map.entropy_profile["regime"] == "low"
        assert "low_entropy_stability" in hrm_map.resolution_hints
        assert "confident_response_appropriate" in hrm_map.resolution_hints


# =============================================================================
# CONFLICT DETECTION SCENARIOS
# =============================================================================


class TestConflictScenarios:
    """Tests for conflict detection in realistic scenarios."""

    def test_survival_transcendence_tension_hybrid(
        self, hrm_engine: HRMEngine
    ) -> None:
        """Strong lower anchors + strong upper aspects should trigger tension."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.1,
                "Identity": 0.1,
                "Purpose": 0.4,  # Strong upper
                "Universal": 0.3,  # Strong upper
                "Core": 0.1,
            },
            anchor_scores={
                "Needs": 0.35,  # Strong lower
                "Exchange": 0.25,  # Strong lower
                "Challenge": 0.2,  # Strong lower
                "Meaning": 0.1,
                "Belonging": 0.1,
            },
            H_D=1.5,
            H_G=0.7,
            H_K=0.9,
            domain="therapy",
            tier="hybrid",
            flow_mode="outer_plus_inner",
        )

        hrm_map = hrm_engine.build_map(hrm_input)

        assert "survival_transcendence_tension" in hrm_map.conflict_zones
        assert "anchor_tension_survival_vs_transcendence" in hrm_map.resolution_hints

    def test_grounding_deficit_spiritual_domain(self, hrm_engine: HRMEngine) -> None:
        """High upper aspects + low grounding should trigger grounding deficit."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.02,  # Very low
                "Form": 0.02,  # Very low
                "Identity": 0.05,
                "Purpose": 0.35,  # High
                "Universal": 0.35,  # High
                "Core": 0.21,
            },
            anchor_scores={
                "Meaning": 0.5,
                "Collective": 0.3,
                "Belonging": 0.2,
            },
            H_D=1.8,
            H_G=0.85,
            H_K=1.1,
            domain="spiritual",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = hrm_engine.build_map(hrm_input)

        assert "grounding_deficit" in hrm_map.conflict_zones
        assert "abstract_without_ground" in hrm_map.resolution_hints
        assert "add_concrete_elements" in hrm_map.resolution_hints

    def test_multiple_conflicts_complex_scenario(self, hrm_engine: HRMEngine) -> None:
        """Complex scenario with multiple overlapping conflicts."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.03,  # Very low
                "Identity": 0.03,  # Very low
                "Form": 0.03,  # Very low
                "Purpose": 0.45,  # High
                "Universal": 0.35,  # High
                "Agency": 0.11,
            },
            anchor_scores={
                "Needs": 0.35,  # High
                "Exchange": 0.15,
                "Challenge": 0.15,
                "Meaning": 0.2,  # Significant
                "Collective": 0.15,  # Significant
            },
            H_D=2.0,  # High
            H_G=0.9,  # High
            H_K=1.3,  # High
            domain="identity",
            tier="hybrid",
            flow_mode="outer_plus_inner",
        )

        hrm_map = hrm_engine.build_map(hrm_input)

        # Should detect multiple conflicts
        assert len(hrm_map.conflict_zones) >= 2
        # Resolution hints should be non-empty
        assert len(hrm_map.resolution_hints) > 5


# =============================================================================
# PIPELINE INTEGRATION SIMULATION
# =============================================================================


class TestPipelineIntegration:
    """Tests simulating full pipeline integration."""

    def test_hrm_output_structure_for_fusion(self, hrm_engine: HRMEngine) -> None:
        """HRM output should have all fields needed by Fusion engine."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.3,
                "Purpose": 0.4,
                "Reasoning": 0.3,
            },
            anchor_scores={
                "Needs": 0.3,
                "Meaning": 0.4,
                "Change": 0.3,
            },
            H_D=1.5,
            H_G=0.7,
            H_K=0.9,
            domain="therapy",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = hrm_engine.build_map(hrm_input)

        # Verify all required fields for Fusion/DHA
        assert isinstance(hrm_map.dominant_aspects, list)
        assert isinstance(hrm_map.suppressed_aspects, list)
        assert isinstance(hrm_map.anchor_profile, dict)
        assert isinstance(hrm_map.entropy_profile, dict)
        assert isinstance(hrm_map.conflict_zones, list)
        assert isinstance(hrm_map.resolution_hints, list)
        assert isinstance(hrm_map.tier, str)
        assert isinstance(hrm_map.domain, str)

        # Entropy profile should have required keys
        assert "H_D_norm" in hrm_map.entropy_profile
        assert "H_G_norm" in hrm_map.entropy_profile
        assert "H_K_norm" in hrm_map.entropy_profile
        assert "entropy_mix" in hrm_map.entropy_profile
        assert "regime" in hrm_map.entropy_profile

    def test_serialization_for_pipeline_context(self, hrm_engine: HRMEngine) -> None:
        """HRM map should serialize properly for pipeline context."""
        hrm_input = HRMInput(
            aspect_probs={"Execution": 0.5, "Purpose": 0.5},
            anchor_scores={"Needs": 0.5, "Meaning": 0.5},
            H_D=1.0,
            H_G=0.5,
            H_K=0.7,
            domain="generic",
            tier="hybrid",
            flow_mode="outer_plus_inner",
        )

        hrm_map = hrm_engine.build_map(hrm_input)
        serialized = hrm_map.to_dict()

        # Should be JSON-serializable (no objects, only primitives)
        import json

        json_str = json.dumps(serialized)
        assert isinstance(json_str, str)

        # Should round-trip
        deserialized = json.loads(json_str)
        assert deserialized["tier"] == hrm_map.tier
        assert deserialized["domain"] == hrm_map.domain

    def test_deterministic_output(self, hrm_engine: HRMEngine) -> None:
        """HRM should produce identical output for identical input."""
        hrm_input = HRMInput(
            aspect_probs={
                "Execution": 0.3,
                "Purpose": 0.4,
                "Reasoning": 0.3,
            },
            anchor_scores={
                "Needs": 0.3,
                "Meaning": 0.4,
                "Change": 0.3,
            },
            H_D=1.5,
            H_G=0.7,
            H_K=0.9,
            domain="therapy",
            tier="upper",
            flow_mode="inner_priority",
        )

        # Run multiple times
        results = [hrm_engine.build_map(hrm_input) for _ in range(5)]

        # All results should be identical
        first = results[0].to_dict()
        for result in results[1:]:
            assert result.to_dict() == first


# =============================================================================
# DOMAIN-SPECIFIC SCENARIOS
# =============================================================================


class TestDomainScenarios:
    """Tests for domain-specific HRM behavior."""

    @pytest.mark.parametrize(
        "domain,expected_hint",
        [
            ("therapy", "therapeutic_sensitivity"),
            ("spiritual", "spiritual_openness"),
            ("identity", "identity_exploration_support"),
            ("code", "technical_precision"),
            ("math", "logical_rigor"),
        ],
    )
    def test_domain_specific_hints(
        self,
        hrm_engine: HRMEngine,
        domain: str,
        expected_hint: str,
    ) -> None:
        """Each domain should generate appropriate domain-specific hints."""
        # Adjust tier based on domain type
        if domain in REFLECTIVE_DOMAINS:
            tier = "upper"
            flow_mode = "inner_priority"
            aspects = {"Purpose": 0.6, "Identity": 0.4}
            anchors = {"Meaning": 0.5, "Belonging": 0.5}
        else:
            tier = "lower"
            flow_mode = "outer_only"
            aspects = {"Execution": 0.6, "Form": 0.4}
            anchors = {"Needs": 0.5, "Exchange": 0.5}

        hrm_input = HRMInput(
            aspect_probs=aspects,
            anchor_scores=anchors,
            H_D=1.0,
            H_G=0.5,
            H_K=0.7,
            domain=domain,
            tier=tier,
            flow_mode=flow_mode,
        )

        hrm_map = hrm_engine.build_map(hrm_input)

        assert expected_hint in hrm_map.resolution_hints

    def test_regulated_domain_handled(self, hrm_engine: HRMEngine) -> None:
        """Regulated domains should be handled appropriately."""
        # Finance domain (regulated)
        hrm_input = HRMInput(
            aspect_probs={"Execution": 0.5, "Reasoning": 0.3, "Form": 0.2},
            anchor_scores={"Needs": 0.5, "Exchange": 0.3, "Challenge": 0.2},
            H_D=0.8,
            H_G=0.4,
            H_K=0.5,
            domain="finance",  # Regulated domain
            tier="lower",
            flow_mode="outer_only",
        )

        hrm_map = hrm_engine.build_map(hrm_input)

        # Should process without error
        assert hrm_map.domain == "finance"
        assert hrm_map.tier == "lower"


# =============================================================================
# FLOW MODE SCENARIOS
# =============================================================================


class TestFlowModeScenarios:
    """Tests for flow mode influence on HRM."""

    def test_inner_priority_flow_hints(self, hrm_engine: HRMEngine) -> None:
        """Inner priority flow should generate introspective hints."""
        hrm_input = HRMInput(
            aspect_probs={"Purpose": 0.6, "Core": 0.4},
            anchor_scores={"Meaning": 0.5, "Collective": 0.5},
            H_D=1.5,
            H_G=0.7,
            H_K=0.9,
            domain="philosophy",
            tier="upper",
            flow_mode="inner_priority",
        )

        hrm_map = hrm_engine.build_map(hrm_input)

        assert "inner_flow_introspective" in hrm_map.resolution_hints

    def test_outer_only_flow_hints(self, hrm_engine: HRMEngine) -> None:
        """Outer only flow should generate practical hints."""
        hrm_input = HRMInput(
            aspect_probs={"Execution": 0.7, "Form": 0.3},
            anchor_scores={"Needs": 0.6, "Exchange": 0.4},
            H_D=0.5,
            H_G=0.3,
            H_K=0.4,
            domain="task",
            tier="lower",
            flow_mode="outer_only",
        )

        hrm_map = hrm_engine.build_map(hrm_input)

        assert "outer_flow_practical" in hrm_map.resolution_hints

    def test_balanced_flow_hints(self, hrm_engine: HRMEngine) -> None:
        """Outer plus inner flow should generate balanced hints."""
        hrm_input = HRMInput(
            aspect_probs={"Execution": 0.4, "Purpose": 0.3, "Identity": 0.3},
            anchor_scores={"Needs": 0.4, "Meaning": 0.3, "Belonging": 0.3},
            H_D=1.1,
            H_G=0.55,
            H_K=0.7,
            domain="generic",
            tier="hybrid",
            flow_mode="outer_plus_inner",
        )

        hrm_map = hrm_engine.build_map(hrm_input)

        assert "balanced_flow_mode" in hrm_map.resolution_hints
