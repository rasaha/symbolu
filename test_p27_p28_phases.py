"""
Tests for P27-P28 Delivery Adaptation Band Phases.

Tests:
1. P27 Persona Selection Phase
2. P28 DHA Phase
3. P27→P28 integration flow
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# Try to import pytest, fall back to simple assertions
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


# =============================================================================
# MOCK CONTEXT
# =============================================================================


@dataclass
class MockRequest:
    """Mock UserRequest."""
    text: str = "Why do I feel stuck in my career?"
    user_id: str = "test_user"
    metadata: Dict[str, Any] = field(default_factory=dict)
    render_mode: str = "standard"


@dataclass
class MockMlcr:
    """Mock MLCR result."""
    entries: Dict[str, Any] = field(default_factory=dict)
    explain_log: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockFusion:
    """Mock Fusion result."""
    merged_output: str = "You're experiencing a common career plateau."
    trace: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockDha:
    """Mock DHA result."""
    guarded_text: str = "You're experiencing a common career plateau."
    tone_profile: str = "balanced"
    readiness_level: str = "medium"


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    request: MockRequest = field(default_factory=MockRequest)
    mlcr: Optional[MockMlcr] = None
    fusion: Optional[MockFusion] = None
    dha: Optional[MockDha] = None
    persona: Optional[Any] = None
    p27_persona: Optional[Any] = None
    p28_dha: Optional[Any] = None


# =============================================================================
# P27 SCHEMA TESTS
# =============================================================================


class TestP27Schema:
    """Tests for P27 schema definitions."""

    def test_p27_selection_signals_creation(self):
        """Test P27SelectionSignals dataclass creation."""
        from symbolu.mechanical.pipeline.p27_persona import (
            P27SelectionSignals,
            PersonaSelectionMode,
        )

        signals = P27SelectionSignals(
            query_text="Why do I feel stuck?",
            response_text="Career plateaus are common.",
            tier="hybrid",
            intent="general",
            domain="psychology",
            emotional_entropy=0.6,
            cognitive_entropy=0.4,
            readiness_score=0.7,
            resistance_score=0.2,
        )

        assert signals.query_text == "Why do I feel stuck?"
        assert signals.domain == "psychology"
        assert signals.emotional_entropy == 0.6
        assert signals.mode == PersonaSelectionMode.AUTOMATIC

    def test_p27_selection_signals_validation(self):
        """Test that P27SelectionSignals clamps values to valid ranges."""
        from symbolu.mechanical.pipeline.p27_persona import P27SelectionSignals

        signals = P27SelectionSignals(
            query_text="test",
            response_text="test",
            emotional_entropy=1.5,  # Should be clamped to 1.0
            readiness_score=-0.1,   # Should be clamped to 0.0
        )

        assert signals.emotional_entropy == 1.0
        assert signals.readiness_score == 0.0

    def test_p27_output_to_dict(self):
        """Test P27Output serialization."""
        from symbolu.mechanical.pipeline.p27_persona import (
            P27Output,
            PersonaCategory,
            PersonaSelectionMode,
            P27Authority,
            P27PersonaDirectives,
        )

        output = P27Output(
            persona_id="coach",
            persona_category=PersonaCategory.COACH,
            selection_mode=PersonaSelectionMode.AUTOMATIC,
            selection_confidence=0.85,
            authority=P27Authority.MEDIUM,
            directives=P27PersonaDirectives(tone_warmth=0.7),
            selection_reasoning=["Domain=psychology → coach persona"],
        )

        result = output.to_dict()

        assert result["phase"] == "P27"
        assert result["persona_id"] == "coach"
        assert result["persona_category"] == "coach"
        assert result["selection_confidence"] == 0.85
        assert result["directives"]["tone_warmth"] == 0.7


# =============================================================================
# P27 INTEGRATION TESTS
# =============================================================================


class TestP27Integration:
    """Tests for P27 integration functions."""

    def test_extract_p27_signals_basic(self):
        """Test signal extraction from context."""
        from symbolu.mechanical.pipeline.p27_persona import extract_p27_signals

        ctx = MockPipelineContext(
            request=MockRequest(text="Help me understand my feelings"),
            mlcr=MockMlcr(
                explain_log={
                    "meta": {"tier": "lower", "intent": "emotional", "domain": "psychology"},
                    "entropy": {"H_D": 0.7, "H_K": 0.4},
                }
            ),
            fusion=MockFusion(merged_output="Emotional awareness is important."),
        )

        signals = extract_p27_signals(ctx)

        assert signals is not None
        assert signals.query_text == "Help me understand my feelings"
        assert signals.tier == "lower"
        assert signals.domain == "psychology"

    def test_run_p27_selection_psychology_domain(self):
        """Test P27 selects coach persona for psychology domain."""
        from symbolu.mechanical.pipeline.p27_persona import (
            P27SelectionSignals,
            run_p27_selection,
            PersonaCategory,
        )

        signals = P27SelectionSignals(
            query_text="Why am I feeling anxious?",
            response_text="Anxiety can have many sources.",
            tier="lower",
            domain="psychology",
            emotional_entropy=0.6,
        )

        output = run_p27_selection(signals)

        assert output.persona_id == "coach"
        assert output.persona_category == PersonaCategory.COACH

    def test_run_p27_selection_finance_domain(self):
        """Test P27 selects analyst persona for finance domain."""
        from symbolu.mechanical.pipeline.p27_persona import (
            P27SelectionSignals,
            run_p27_selection,
            PersonaCategory,
        )

        signals = P27SelectionSignals(
            query_text="What's my portfolio risk?",
            response_text="Your portfolio has moderate risk.",
            tier="upper",
            domain="finance",
        )

        output = run_p27_selection(signals)

        assert output.persona_id == "analyst"
        assert output.persona_category == PersonaCategory.ANALYST

    def test_maybe_run_p27_returns_output(self):
        """Test maybe_run_p27 returns P27Output."""
        from symbolu.mechanical.pipeline.p27_persona import maybe_run_p27

        ctx = MockPipelineContext(
            request=MockRequest(text="Help me with my career"),
            mlcr=MockMlcr(
                explain_log={
                    "meta": {"tier": "hybrid", "intent": "general", "domain": "generic"},
                }
            ),
            fusion=MockFusion(),
        )

        output = maybe_run_p27(ctx)

        assert output is not None
        assert output.persona_id in ["neutral", "coach", "analyst", "sage", "friendly", "regulator"]


# =============================================================================
# P28 SCHEMA TESTS
# =============================================================================


class TestP28Schema:
    """Tests for P28 schema definitions."""

    def test_p28_input_signals_creation(self):
        """Test P28InputSignals dataclass creation."""
        from symbolu.mechanical.pipeline.p28_dha import P28InputSignals

        signals = P28InputSignals(
            query_text="Help me understand",
            response_text="Here's an explanation",
            persona_id="coach",
            persona_tone_warmth=0.7,
            tier="hybrid",
            domain="psychology",
            readiness_score=0.6,
            resistance_score=0.3,
        )

        assert signals.persona_id == "coach"
        assert signals.persona_tone_warmth == 0.7
        assert signals.resistance_score == 0.3

    def test_p28_tone_profile_creation(self):
        """Test P28ToneProfile dataclass."""
        from symbolu.mechanical.pipeline.p28_dha import (
            P28ToneProfile,
            DeliveryProfileType,
        )

        profile = P28ToneProfile(
            profile_type=DeliveryProfileType.SWEET_RESONANCE,
            warmth=0.8,
            directness=0.4,
            empathy=0.9,
        )

        assert profile.profile_type == DeliveryProfileType.SWEET_RESONANCE
        assert profile.warmth == 0.8

        result = profile.to_dict()
        assert result["profile_type"] == "sweet_resonance"

    def test_p28_output_to_dict(self):
        """Test P28Output serialization."""
        from symbolu.mechanical.pipeline.p28_dha import (
            P28Output,
            P28ToneProfile,
            DeliveryProfileType,
            ReadinessLevel,
            ResistanceLevel,
            P28SafetyResult,
            SafetyStatus,
        )

        output = P28Output(
            adapted_text="Your response here",
            guarded_text="Your response here",
            tone_profile=P28ToneProfile(profile_type=DeliveryProfileType.BALANCED),
            readiness_level=ReadinessLevel.MEDIUM,
            resistance_level=ResistanceLevel.LOW,
            safety_result=P28SafetyResult(status=SafetyStatus.PASSED),
        )

        result = output.to_dict()

        assert result["phase"] == "P28"
        assert result["adapted_text"] == "Your response here"
        assert result["tone_profile"]["profile_type"] == "balanced"
        assert result["readiness_level"] == "medium"


# =============================================================================
# P28 INTEGRATION TESTS
# =============================================================================


class TestP28Integration:
    """Tests for P28 integration functions."""

    def test_map_delivery_profile_high_resistance(self):
        """Test profile mapping for high resistance scenario."""
        from symbolu.mechanical.pipeline.p28_dha import (
            P28InputSignals,
            DeliveryProfileType,
        )
        from symbolu.mechanical.pipeline.p28_dha.p28_integration import map_delivery_profile

        signals = P28InputSignals(
            query_text="I don't want to hear this",
            response_text="I understand your concern",
            resistance_score=0.7,
            readiness_score=0.3,
        )

        profile = map_delivery_profile(signals)

        assert profile == DeliveryProfileType.INVERSE_JOLT

    def test_map_delivery_profile_high_emotional_entropy(self):
        """Test profile mapping for high emotional entropy."""
        from symbolu.mechanical.pipeline.p28_dha import (
            P28InputSignals,
            DeliveryProfileType,
        )
        from symbolu.mechanical.pipeline.p28_dha.p28_integration import map_delivery_profile

        signals = P28InputSignals(
            query_text="I'm feeling confused",
            response_text="Confusion is natural",
            emotional_entropy=0.8,
            resistance_score=0.3,
        )

        profile = map_delivery_profile(signals)

        assert profile == DeliveryProfileType.SYMBOLIC_METAPHOR

    def test_run_p28_adaptation_basic(self):
        """Test P28 adaptation execution."""
        from symbolu.mechanical.pipeline.p28_dha import (
            P28InputSignals,
            run_p28_adaptation,
        )

        signals = P28InputSignals(
            query_text="Help me understand",
            response_text="Here's what you need to know",
            persona_id="neutral",
            readiness_score=0.6,
            resistance_score=0.2,
        )

        output = run_p28_adaptation(signals)

        assert output is not None
        assert output.adapted_text != ""
        assert len(output.adaptation_trace) > 0

    def test_maybe_run_p28_returns_output(self):
        """Test maybe_run_p28 returns P28Output."""
        from symbolu.mechanical.pipeline.p28_dha import maybe_run_p28

        ctx = MockPipelineContext(
            request=MockRequest(text="Help me"),
            mlcr=MockMlcr(
                explain_log={
                    "meta": {"tier": "hybrid", "domain": "generic"},
                    "entropy": {"H_D": 0.5, "H_G": 0.5},
                }
            ),
            fusion=MockFusion(merged_output="Here's help"),
        )

        output = maybe_run_p28(ctx)

        assert output is not None
        assert output.guarded_text != ""


# =============================================================================
# P27 → P28 FLOW TESTS
# =============================================================================


class TestP27P28Flow:
    """Tests for P27 → P28 integration flow."""

    def test_p27_to_p28_persona_context_flows(self):
        """Test that P27 persona context flows to P28."""
        from symbolu.mechanical.pipeline.p27_persona import (
            maybe_run_p27,
            P27Output,
        )
        from symbolu.mechanical.pipeline.p28_dha import (
            maybe_run_p28,
            extract_p28_signals,
        )

        # Create context
        ctx = MockPipelineContext(
            request=MockRequest(text="Help me with stress"),
            mlcr=MockMlcr(
                explain_log={
                    "meta": {"tier": "lower", "domain": "psychology"},
                    "entropy": {"H_D": 0.6, "H_G": 0.5},
                }
            ),
            fusion=MockFusion(merged_output="Stress management is important"),
        )

        # Run P27
        p27_output = maybe_run_p27(ctx)
        ctx.p27_persona = p27_output

        # Extract P28 signals with P27 context
        signals = extract_p28_signals(ctx, p27_output)

        assert signals is not None
        assert signals.persona_id == p27_output.persona_id
        assert signals.persona_tone_warmth == p27_output.directives.tone_warmth

    def test_full_p27_p28_pipeline(self):
        """Test full P27 → P28 pipeline execution."""
        from symbolu.mechanical.pipeline.p27_persona import maybe_run_p27
        from symbolu.mechanical.pipeline.p28_dha import maybe_run_p28

        ctx = MockPipelineContext(
            request=MockRequest(text="I need career advice"),
            mlcr=MockMlcr(
                explain_log={
                    "meta": {"tier": "hybrid", "domain": "generic", "intent": "practical"},
                    "entropy": {"H_D": 0.5, "H_G": 0.5, "H_K": 0.5},
                }
            ),
            fusion=MockFusion(merged_output="Career transitions require planning"),
        )

        # Run P27
        p27_output = maybe_run_p27(ctx)
        ctx.p27_persona = p27_output

        # Run P28 with P27 context
        p28_output = maybe_run_p28(ctx, p27_output=p27_output)
        ctx.p28_dha = p28_output

        # Verify chain
        assert p27_output is not None
        assert p28_output is not None
        assert ctx.p27_persona == p27_output
        assert ctx.p28_dha == p28_output

        # Verify output structure
        assert hasattr(p27_output, 'persona_id')
        assert hasattr(p28_output, 'guarded_text')
        assert hasattr(p28_output, 'tone_profile')


# =============================================================================
# P29-P31 STUB TESTS
# =============================================================================


class TestP29P31Stubs:
    """Tests for P29-P31 stub phases."""

    def test_p29_stub_passthrough(self):
        """Test P29 stub passes through text."""
        from symbolu.mechanical.pipeline.p29_expression import maybe_run_p29

        ctx = MockPipelineContext()
        ctx.p28_dha = type('P28', (), {'guarded_text': 'Test message'})()

        output = maybe_run_p29(ctx)

        assert output is not None
        assert output.final_text == 'Test message'
        assert output.polish_applied is False

    def test_p30_stub_passthrough(self):
        """Test P30 stub passes through text."""
        from symbolu.mechanical.pipeline.p30_verification import maybe_run_p30

        ctx = MockPipelineContext()
        ctx.p28_dha = type('P28', (), {'guarded_text': 'Test message'})()

        output = maybe_run_p30(ctx)

        assert output is not None
        assert output.verified_text == 'Test message'
        assert output.verification_passed is True

    def test_p31_stub_passthrough(self):
        """Test P31 stub passes through text."""
        from symbolu.mechanical.pipeline.p31_envelope import maybe_run_p31

        ctx = MockPipelineContext()
        ctx.p28_dha = type('P28', (), {'guarded_text': 'Test message'})()

        output = maybe_run_p31(ctx)

        assert output is not None
        assert output.envelope_text == 'Test message'
        assert output.envelope_format == "plain"


# =============================================================================
# RUN TESTS
# =============================================================================

def run_tests():
    """Run all tests without pytest."""
    import traceback

    test_classes = [
        TestP27Schema,
        TestP27Integration,
        TestP28Schema,
        TestP28Integration,
        TestP27P28Flow,
        TestP29P31Stubs,
    ]

    passed = 0
    failed = 0

    for test_class in test_classes:
        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith('test_')]

        for method_name in methods:
            try:
                method = getattr(instance, method_name)
                method()
                print(f"✓ {test_class.__name__}.{method_name}")
                passed += 1
            except Exception as e:
                print(f"✗ {test_class.__name__}.{method_name}")
                print(f"  Error: {e}")
                traceback.print_exc()
                failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        success = run_tests()
        exit(0 if success else 1)
