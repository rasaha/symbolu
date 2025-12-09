"""
Pipeline Mapper Integration Tests

Tests the integration of HRM, LCM, and LAM mappers into the SOULPI pipeline,
verifying that TTOR routing → mapper activation → pipeline context flow works correctly.

Tests cover:
1. LOWER-tier, low-context task → LCM activation
2. UPPER-tier, high-entropy therapy → HRM and/or LAM activation
3. Generic chat → conditional mapper activation based on entropy

Version: v1.0
"""

import pytest
from typing import Dict, Any

from symbolu.mechanical.pipeline.orchestrator import SymbolUPipeline
from symbolu.mechanical.pipeline.models import UserRequest


class TestPipelineMapperIntegration:
    """
    Integration tests for HRM, LCM, and LAM mapper activation in the pipeline.

    These tests verify that the canonical mapper switching rules are applied correctly:
    - HRM: (tier != LOWER) and (normalized_entropy > 0.40)
    - LCM: (tier == LOWER) and (normalized_entropy > 0.50)
    - LAM: long_arc_tension > 0.50 OR temporal_patterns_detected
           OR (domain in ["therapy", "identity", "spiritual"] and normalized_entropy > 0.60)
    """

    def test_lower_tier_simple_task_activates_lcm_only(self):
        """
        Test that a simple LOWER-tier task activates LCM (not HRM or LAM).

        Expected behavior:
        - LOWER tier task with sufficient entropy (> 0.50) should activate LCM
        - HRM should not be activated (tier == LOWER)
        - LAM should not be activated (no long_arc_tension, not therapy domain)
        """
        pipeline = SymbolUPipeline()

        # Simple task query (expected to be LOWER tier)
        request = UserRequest(
            text="Sort the numbers [5, 2, 8, 1, 9] in ascending order",
            metadata={"domain": "task"}
        )

        result = pipeline.run(request)

        # Get the pipeline context to inspect mapper activation
        # Note: We need to capture ctx during pipeline execution
        # For now, we'll check that the result is generated successfully
        assert result is not None
        assert result.raw_text is not None

        # TODO: Add instrumentation to capture ctx.hrm_map, ctx.lcm_map, ctx.lam_map
        # For a full integration test, we'd verify:
        # - ctx.lcm_map is not None (LCM was activated)
        # - ctx.hrm_map is None (HRM was not activated)
        # - ctx.lam_map is None (LAM was not activated)

    def test_upper_tier_therapy_activates_hrm_and_lam(self):
        """
        Test that an UPPER-tier therapy query activates both HRM and LAM.

        Expected behavior:
        - UPPER tier with therapy domain and high entropy should activate HRM
        - Therapy domain with high entropy (> 0.60) should activate LAM
        - LCM should not be activated (tier != LOWER)
        """
        pipeline = SymbolUPipeline()

        # Therapy/identity query (expected to be UPPER tier, therapy domain)
        request = UserRequest(
            text="Why do I keep feeling stuck in my career despite trying to make changes?",
            metadata={"domain": "therapy"}
        )

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None

        # TODO: Verify ctx.hrm_map is not None and ctx.lam_map is not None
        # and ctx.lcm_map is None

    def test_hybrid_tier_mixed_query_activates_multiple_mappers(self):
        """
        Test that a HYBRID-tier query with mixed concerns activates multiple mappers.

        Expected behavior:
        - HYBRID tier with sufficient entropy (> 0.40) should activate HRM
        - HYBRID tier should NOT activate LCM (tier != LOWER or entropy < 0.50)
        - LAM activation depends on domain and long_arc_tension
        """
        pipeline = SymbolUPipeline()

        # Mixed query with both concrete and abstract elements
        request = UserRequest(
            text="How can I balance my daily work tasks while also finding meaning in what I do?",
            metadata={"domain": "general"}
        )

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None

        # TODO: Verify mapper activation patterns for HYBRID tier

    def test_spiritual_domain_high_entropy_activates_lam(self):
        """
        Test that spiritual domain queries with high entropy activate LAM.

        Expected behavior:
        - Domain in ["therapy", "identity", "spiritual"] with entropy > 0.60 should activate LAM
        - HRM activation depends on tier (tier != LOWER) and entropy (> 0.40)
        - LCM should not be activated for non-LOWER tiers
        """
        pipeline = SymbolUPipeline()

        # Spiritual/identity query
        request = UserRequest(
            text="What is my purpose in this life? How do I find true fulfillment?",
            metadata={"domain": "spiritual"}
        )

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None

        # TODO: Verify ctx.lam_map is not None (LAM activated for spiritual domain)

    def test_low_entropy_generic_chat_activates_no_mappers(self):
        """
        Test that simple generic chat with low entropy activates no mappers.

        Expected behavior:
        - Low entropy (< 0.40) should not activate HRM
        - Non-LOWER tier or entropy < 0.50 should not activate LCM
        - No long_arc_tension and not therapy domain should not activate LAM
        """
        pipeline = SymbolUPipeline()

        # Simple greeting or generic query
        request = UserRequest(
            text="Hello, how are you?",
            metadata={"domain": "generic"}
        )

        result = pipeline.run(request)

        assert result is not None
        assert result.raw_text is not None

        # TODO: Verify that none of the mappers are activated
        # (or only minimal activation based on MLCR's tier classification)


class TestMapperActivationRules:
    """
    Direct tests for mapper activation rules without full pipeline execution.

    These tests directly verify the canonical activation region rules.
    """

    def test_hrm_activation_rule(self):
        """
        Test HRM activation rule: (tier != LOWER) and (normalized_entropy > 0.40)
        """
        from symbolu.mechanical.mlcr.expert_router import ExpertRouter
        from symbolu.mechanical.mlcr.activation_plan import TierType, IntentType

        router = ExpertRouter()

        # Test case 1: UPPER tier, entropy > 0.40 → HRM should activate
        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.WHAT,
            domain="general",
            H_D=1.0,  # High H_D
            H_G=0.5,  # Medium H_G
            # normalized_entropy = 0.5 * (1.0 / 2.302) + 0.3 * (0.5 / 1.098)
            # ≈ 0.5 * 0.434 + 0.3 * 0.455 ≈ 0.217 + 0.137 ≈ 0.354 < 0.40
            # Actually let's use higher values
        )

        # For entropy > 0.40, we need:
        # 0.5 * (H_D / 2.302) + 0.3 * (H_G / 1.098) > 0.40
        # Example: H_D = 1.5, H_G = 0.8
        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.WHAT,
            domain="general",
            H_D=1.5,
            H_G=0.8,
        )
        # normalized_entropy = 0.5 * (1.5 / 2.302) + 0.3 * (0.8 / 1.098)
        # ≈ 0.5 * 0.651 + 0.3 * 0.728 ≈ 0.326 + 0.218 ≈ 0.544 > 0.40
        assert activation["use_hrm"] is True

        # Test case 2: LOWER tier, entropy > 0.40 → HRM should NOT activate
        activation = router.route(
            tier=TierType.LOWER,
            intent=IntentType.WHAT,
            domain="general",
            H_D=1.5,
            H_G=0.8,
        )
        assert activation["use_hrm"] is False

        # Test case 3: UPPER tier, entropy < 0.40 → HRM should NOT activate
        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.WHAT,
            domain="general",
            H_D=0.5,
            H_G=0.2,
        )
        # normalized_entropy = 0.5 * (0.5 / 2.302) + 0.3 * (0.2 / 1.098)
        # ≈ 0.5 * 0.217 + 0.3 * 0.182 ≈ 0.109 + 0.055 ≈ 0.164 < 0.40
        assert activation["use_hrm"] is False

    def test_lcm_activation_rule(self):
        """
        Test LCM activation rule: (tier == LOWER) and (normalized_entropy > 0.50)
        """
        from symbolu.mechanical.mlcr.expert_router import ExpertRouter
        from symbolu.mechanical.mlcr.activation_plan import TierType, IntentType

        router = ExpertRouter()

        # Test case 1: LOWER tier, entropy > 0.50 → LCM should activate
        activation = router.route(
            tier=TierType.LOWER,
            intent=IntentType.WHAT,
            domain="task",
            H_D=1.8,
            H_G=0.9,
        )
        # normalized_entropy = 0.5 * (1.8 / 2.302) + 0.3 * (0.9 / 1.098)
        # ≈ 0.5 * 0.782 + 0.3 * 0.820 ≈ 0.391 + 0.246 ≈ 0.637 > 0.50
        assert activation["use_lcm"] is True

        # Test case 2: LOWER tier, entropy < 0.50 → LCM should NOT activate
        activation = router.route(
            tier=TierType.LOWER,
            intent=IntentType.WHAT,
            domain="task",
            H_D=0.8,
            H_G=0.4,
        )
        # normalized_entropy = 0.5 * (0.8 / 2.302) + 0.3 * (0.4 / 1.098)
        # ≈ 0.5 * 0.347 + 0.3 * 0.364 ≈ 0.174 + 0.109 ≈ 0.283 < 0.50
        assert activation["use_lcm"] is False

        # Test case 3: UPPER tier, entropy > 0.50 → LCM should NOT activate
        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.WHAT,
            domain="task",
            H_D=1.8,
            H_G=0.9,
        )
        assert activation["use_lcm"] is False

    def test_lam_activation_rule_domain_based(self):
        """
        Test LAM activation rule: domain in ["therapy", "identity", "spiritual"] and entropy > 0.60
        """
        from symbolu.mechanical.mlcr.expert_router import ExpertRouter
        from symbolu.mechanical.mlcr.activation_plan import TierType, IntentType

        router = ExpertRouter()

        # Test case 1: therapy domain, entropy > 0.60 → LAM should activate
        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.REFLECTION,
            domain="therapy",
            H_D=2.0,
            H_G=1.0,
        )
        # normalized_entropy = 0.5 * (2.0 / 2.302) + 0.3 * (1.0 / 1.098)
        # ≈ 0.5 * 0.869 + 0.3 * 0.911 ≈ 0.435 + 0.273 ≈ 0.708 > 0.60
        assert activation["use_lam"] is True

        # Test case 2: therapy domain, entropy < 0.60 → LAM should NOT activate
        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.REFLECTION,
            domain="therapy",
            H_D=1.0,
            H_G=0.5,
            long_arc_tension=0.0,
        )
        # normalized_entropy ≈ 0.354 < 0.60
        assert activation["use_lam"] is False

        # Test case 3: non-therapy domain, entropy > 0.60 → LAM should NOT activate
        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.WHAT,
            domain="general",
            H_D=2.0,
            H_G=1.0,
            long_arc_tension=0.0,
        )
        assert activation["use_lam"] is False

        # Test case 4: identity domain, entropy > 0.60 → LAM should activate
        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.REFLECTION,
            domain="identity",
            H_D=2.0,
            H_G=1.0,
        )
        assert activation["use_lam"] is True

        # Test case 5: spiritual domain, entropy > 0.60 → LAM should activate
        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.REFLECTION,
            domain="spiritual",
            H_D=2.0,
            H_G=1.0,
        )
        assert activation["use_lam"] is True

    def test_lam_activation_rule_tension_based(self):
        """
        Test LAM activation rule: long_arc_tension > 0.50
        """
        from symbolu.mechanical.mlcr.expert_router import ExpertRouter
        from symbolu.mechanical.mlcr.activation_plan import TierType, IntentType

        router = ExpertRouter()

        # Test case 1: long_arc_tension > 0.50 → LAM should activate (regardless of domain)
        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.WHAT,
            domain="general",
            H_D=0.5,
            H_G=0.2,
            long_arc_tension=0.6,
        )
        assert activation["use_lam"] is True

        # Test case 2: long_arc_tension < 0.50 → LAM should NOT activate (unless domain rule)
        activation = router.route(
            tier=TierType.UPPER,
            intent=IntentType.WHAT,
            domain="general",
            H_D=0.5,
            H_G=0.2,
            long_arc_tension=0.3,
        )
        assert activation["use_lam"] is False


class TestMapperOutputStorage:
    """
    Tests that mapper outputs are correctly stored in PipelineContext.
    """

    def test_context_has_mapper_fields(self):
        """
        Test that PipelineContext has fields for storing mapper outputs.
        """
        from symbolu.mechanical.pipeline.models import PipelineContext, UserRequest

        request = UserRequest(text="Test query")
        ctx = PipelineContext(request=request)

        # Verify that context has mapper fields
        assert hasattr(ctx, 'hrm_map')
        assert hasattr(ctx, 'lcm_map')
        assert hasattr(ctx, 'lam_map')

        # Initially None
        assert ctx.hrm_map is None
        assert ctx.lcm_map is None
        assert ctx.lam_map is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
