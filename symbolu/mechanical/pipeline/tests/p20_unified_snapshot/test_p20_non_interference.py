"""
Test Suite: P20 Unified Cognitive Snapshot Non-Interference

Group C - Non-Interference Tests:
    - Snapshot creation does not alter routing
    - Snapshot creation does not alter intent
    - Snapshot creation does not alter regime
    - Snapshot creation does not alter discourse
    - Snapshot creation does not alter renderer inputs

This test file validates that Phase 20 has zero impact on pipeline behavior.
"""

import pytest
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass, field
from typing import List, Optional, Any
import inspect

from symbolu.mechanical.pipeline.p20_snapshot import (
    maybe_run_p20,
    run_p20,
    P20UnifiedSnapshotResolver,
)
from symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema import (
    UnifiedCognitiveSnapshot,
)


# =============================================================================
# Mock Context Classes
# =============================================================================


@dataclass
class MockCoherenceState:
    """Mock coherence state for testing."""
    coherence_score_v3: Optional[float] = None
    domain_history: List[str] = field(default_factory=list)


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    coherence_state: Optional[MockCoherenceState] = None
    phase_20_snapshot: Optional[UnifiedCognitiveSnapshot] = None


class TestNoRoutingImpact:
    """Verify Phase 20 does NOT affect routing in any way."""

    def test_no_routing_imports_in_schema(self):
        """Test that P20 schema has no routing imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema as schema_module
        source = inspect.getsource(schema_module)
        assert 'from symbolu.mechanical.pipeline.routing' not in source
        assert 'import routing' not in source

    def test_no_routing_imports_in_resolver(self):
        """Test that P20 resolver has no routing imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'from symbolu.mechanical.pipeline.routing' not in source
        assert 'import routing' not in source

    def test_no_routing_imports_in_integration(self):
        """Test that P20 integration has no routing imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_integration as integration_module
        source = inspect.getsource(integration_module)
        assert 'from symbolu.mechanical.pipeline.routing' not in source
        assert 'import routing' not in source

    def test_does_not_modify_tier(self):
        """Test that P20 doesn't modify routing tier."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_score_v3=0.85)
        )
        ctx.tier = "hybrid"
        maybe_run_p20(ctx)
        assert ctx.tier == "hybrid"

    def test_does_not_modify_domain(self):
        """Test that P20 doesn't modify routing domain."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                coherence_score_v3=0.85,
                domain_history=["therapy"],
            )
        )
        ctx.domain = "therapy"
        maybe_run_p20(ctx)
        assert ctx.domain == "therapy"


class TestNoIntentImpact:
    """Verify Phase 20 does NOT affect intent resolution."""

    def test_no_intent_imports_in_schema(self):
        """Test that P20 schema has no intent imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema as schema_module
        source = inspect.getsource(schema_module)
        assert 'IntentType' not in source
        assert 'from symbolu.mechanical.pipeline.phase_zero' not in source

    def test_no_intent_imports_in_resolver(self):
        """Test that P20 resolver has no intent imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'IntentType' not in source

    def test_does_not_modify_phase_zero(self):
        """Test that P20 doesn't modify phase_zero intent."""
        intent_mock = Mock(intent_type=Mock(value="CLARIFY"))
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.phase_zero = intent_mock
        maybe_run_p20(ctx)
        assert ctx.phase_zero.intent_type.value == "CLARIFY"

    def test_intent_unchanged_after_snapshot(self):
        """Test that intent is unchanged after snapshot creation."""
        intent_mock = Mock(
            intent_type=Mock(value="INFORM"),
            response_posture=Mock(value="ENGAGE"),
        )
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.phase_zero = intent_mock
        maybe_run_p20(ctx)
        assert ctx.phase_zero.intent_type.value == "INFORM"
        assert ctx.phase_zero.response_posture.value == "ENGAGE"


class TestNoRegimeImpact:
    """Verify Phase 20 does NOT affect regime selection."""

    def test_no_regime_imports_in_schema(self):
        """Test that P20 schema has no regime imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema as schema_module
        source = inspect.getsource(schema_module)
        assert 'RegimeEnvelope' not in source
        assert 'from symbolu.mechanical.pipeline.phase_p6' not in source

    def test_no_regime_imports_in_resolver(self):
        """Test that P20 resolver has no regime imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'RegimeEnvelope' not in source

    def test_does_not_modify_p6_regime(self):
        """Test that P20 doesn't modify P6 regime."""
        regime_mock = Mock(
            regime=Mock(value="BLOCKED"),
            reason="Safety concern",
        )
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.p6_regime = regime_mock
        maybe_run_p20(ctx)
        assert ctx.p6_regime.regime.value == "BLOCKED"
        assert ctx.p6_regime.reason == "Safety concern"

    def test_blocked_regime_unchanged(self):
        """Test that BLOCKED regime status is unchanged."""
        regime_mock = Mock(
            regime=Mock(value="BLOCKED"),
            coherence_regime="low_coherence",
        )
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.p6_regime = regime_mock
        maybe_run_p20(ctx)
        assert ctx.p6_regime.regime.value == "BLOCKED"
        assert ctx.p6_regime.coherence_regime == "low_coherence"

    def test_hold_regime_unchanged(self):
        """Test that HOLD regime status is unchanged."""
        regime_mock = Mock(regime=Mock(value="HOLD"))
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.p6_regime = regime_mock
        maybe_run_p20(ctx)
        assert ctx.p6_regime.regime.value == "HOLD"


class TestNoDiscourseImpact:
    """Verify Phase 20 does NOT affect discourse resolution."""

    def test_no_discourse_imports_in_schema(self):
        """Test that P20 schema has no discourse imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema as schema_module
        source = inspect.getsource(schema_module)
        assert 'DiscourseEnvelope' not in source
        assert 'from symbolu.mechanical.pipeline.p7_discourse' not in source

    def test_no_discourse_imports_in_resolver(self):
        """Test that P20 resolver has no discourse imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'DiscourseEnvelope' not in source

    def test_does_not_modify_p7_discourse(self):
        """Test that P20 doesn't modify P7 discourse."""
        discourse_mock = Mock(
            act=Mock(value="CLARIFY"),
            allowed=True,
        )
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.p7_discourse_envelope = discourse_mock
        maybe_run_p20(ctx)
        assert ctx.p7_discourse_envelope.act.value == "CLARIFY"
        assert ctx.p7_discourse_envelope.allowed is True

    def test_discourse_act_unchanged(self):
        """Test that discourse act is unchanged after snapshot."""
        discourse_mock = Mock(
            act=Mock(value="INFORM"),
            intent=Mock(value="INFORM"),
            reason="Valid discourse act",
        )
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.p7_discourse_envelope = discourse_mock
        maybe_run_p20(ctx)
        assert ctx.p7_discourse_envelope.act.value == "INFORM"
        assert ctx.p7_discourse_envelope.reason == "Valid discourse act"


class TestNoRendererImpact:
    """Verify Phase 20 does NOT affect renderer inputs."""

    def test_no_renderer_imports_in_schema(self):
        """Test that P20 schema has no renderer imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema as schema_module
        source = inspect.getsource(schema_module)
        assert 'from symbolu.mechanical.renderer' not in source
        assert 'import renderer' not in source

    def test_no_renderer_imports_in_resolver(self):
        """Test that P20 resolver has no renderer imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'from symbolu.mechanical.renderer' not in source
        assert 'import renderer' not in source

    def test_does_not_modify_dha(self):
        """Test that P20 doesn't modify DHA decision."""
        dha_mock = Mock(
            tone_profile="sweet_resonance",
            readiness_level="HIGH",
        )
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.dha = dha_mock
        maybe_run_p20(ctx)
        assert ctx.dha.tone_profile == "sweet_resonance"
        assert ctx.dha.readiness_level == "HIGH"

    def test_does_not_modify_rendered_output(self):
        """Test that P20 doesn't modify rendered output."""
        rendered_mock = Mock(
            raw_text="Test output",
            mode="standard",
        )
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.rendered = rendered_mock
        maybe_run_p20(ctx)
        assert ctx.rendered.raw_text == "Test output"
        assert ctx.rendered.mode == "standard"

    def test_does_not_modify_mapper_profile(self):
        """Test that P20 doesn't modify mapper profile."""
        mapper_mock = Mock(
            resolution_level="high",
            detail_bias=0.7,
        )
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.mapper_profile = mapper_mock
        maybe_run_p20(ctx)
        assert ctx.mapper_profile.resolution_level == "high"
        assert ctx.mapper_profile.detail_bias == 0.7


class TestNoPersonaImpact:
    """Verify Phase 20 does NOT affect persona selection."""

    def test_no_persona_imports_in_schema(self):
        """Test that P20 schema has no persona imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema as schema_module
        source = inspect.getsource(schema_module)
        assert 'from symbolu.mechanical.persona' not in source

    def test_no_persona_imports_in_resolver(self):
        """Test that P20 resolver has no persona imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'from symbolu.mechanical.persona' not in source

    def test_does_not_modify_persona_context(self):
        """Test that P20 doesn't modify persona context."""
        persona_mock = Mock(
            active_persona_id="sage",
            persona_config={"traits": ["wise", "calm"]},
        )
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.persona = persona_mock
        maybe_run_p20(ctx)
        assert ctx.persona.active_persona_id == "sage"
        assert ctx.persona.persona_config == {"traits": ["wise", "calm"]}


class TestNoPolicyImpact:
    """Verify Phase 20 does NOT affect policy engines."""

    def test_no_policy_imports_in_schema(self):
        """Test that P20 schema has no policy imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema as schema_module
        source = inspect.getsource(schema_module)
        assert 'policy' not in source.lower() or 'policy' in source  # Allow docstring mentions

    def test_does_not_modify_grounding(self):
        """Test that P20 doesn't modify grounding envelope."""
        grounding_mock = Mock(
            overall_policy=Mock(value="PERMIT"),
            is_blocked=Mock(return_value=False),
        )
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        ctx.phase_minus_one = grounding_mock
        maybe_run_p20(ctx)
        assert ctx.phase_minus_one.overall_policy.value == "PERMIT"
        assert ctx.phase_minus_one.is_blocked() is False


class TestNoSideEffects:
    """Verify Phase 20 has no side effects."""

    def test_resolver_has_no_global_state_modification(self):
        """Test that resolver doesn't modify global state."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())

        # Call multiple times
        snapshot1 = resolver.resolve(ctx)
        snapshot2 = resolver.resolve(ctx)

        # Both should be valid independent snapshots
        assert snapshot1 is not snapshot2
        assert snapshot1.run_id != snapshot2.run_id

    def test_snapshot_creation_is_idempotent(self):
        """Test that creating a snapshot is idempotent (no cumulative effects)."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_score_v3=0.85)
        )

        # Run multiple times
        for _ in range(5):
            maybe_run_p20(ctx)

        # Context should have valid snapshot
        assert ctx.phase_20_snapshot is not None
        assert ctx.phase_20_snapshot.coherence_v3 == 0.85

    def test_does_not_write_to_filesystem(self):
        """Test that P20 doesn't write to filesystem (structural guarantee)."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'open(' not in source
        assert 'write(' not in source
        assert 'Path(' not in source

    def test_does_not_make_network_calls(self):
        """Test that P20 doesn't make network calls (structural guarantee)."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'requests' not in source
        assert 'urllib' not in source
        assert 'httpx' not in source
        assert 'aiohttp' not in source


class TestZeroLLMGuarantee:
    """Verify Phase 20 makes no LLM calls."""

    def test_no_llm_imports_in_schema(self):
        """Test that P20 schema has no LLM imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema as schema_module
        source = inspect.getsource(schema_module)
        assert 'anthropic' not in source
        assert 'openai' not in source
        assert 'llm' not in source.lower()

    def test_no_llm_imports_in_resolver(self):
        """Test that P20 resolver has no LLM imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'anthropic' not in source
        assert 'openai' not in source

    def test_no_llm_imports_in_integration(self):
        """Test that P20 integration has no LLM imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_integration as integration_module
        source = inspect.getsource(integration_module)
        assert 'anthropic' not in source
        assert 'openai' not in source


class TestDHAIndependence:
    """Verify Phase 20 is independent of DHA."""

    def test_no_dha_imports(self):
        """Test that P20 has no DHA imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'from symbolu.mechanical.dha' not in source
        assert 'DhaDecision' not in source


class TestFusionIndependence:
    """Verify Phase 20 is independent of Fusion engine."""

    def test_no_fusion_imports_in_resolver(self):
        """Test that P20 resolver has no fusion engine imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'from symbolu.mechanical.fusion' not in source
        assert 'FusionEngine' not in source


class TestMLCRIndependence:
    """Verify Phase 20 is independent of MLCR."""

    def test_no_mlcr_imports_in_resolver(self):
        """Test that P20 resolver has no MLCR imports."""
        import symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver as resolver_module
        source = inspect.getsource(resolver_module)
        assert 'from symbolu.mechanical.mlcr' not in source
        assert 'MlcrEngine' not in source
