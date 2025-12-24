"""
P27 Persona Selection Phase Unit Tests
========================================

Comprehensive tests for P27 Persona Selection phase:
- P27Authority enum
- PersonaSelectionMode enum
- PersonaCategory enum
- P27SelectionSignals dataclass
- P27PersonaDirectives dataclass
- P27Output dataclass
- Integration functions
- Domain-based persona selection
- Signal extraction from context
- Determinism verification

Test Cases:
1. Enum validation
2. Signal clamping/validation
3. Persona selection by domain
4. Persona selection by tier
5. Persona selection by resistance
6. Forced/hint-guided selection modes
7. Serialization (to_dict)
8. Determinism verification
9. Integration function behavior
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from symbolu.mechanical.pipeline.p27_persona import (
    VERSION,
    P27Authority,
    PersonaSelectionMode,
    PersonaCategory,
    P27SelectionSignals,
    P27PersonaDirectives,
    P27Output,
    get_persona_engine,
    get_persona_selector,
    extract_p27_signals,
    run_p27_selection,
    maybe_run_p27,
    get_p27_output,
    get_p27_persona_id,
)


# =============================================================================
# MOCK CONTEXT FIXTURES
# =============================================================================


@dataclass
class MockRequest:
    """Mock UserRequest for testing."""
    text: str = "Why do I feel stuck in my career?"
    user_id: str = "test_user"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockMlcr:
    """Mock MLCR result for testing."""
    entries: Dict[str, Any] = field(default_factory=dict)
    explain_log: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockFusion:
    """Mock Fusion result for testing."""
    merged_output: str = "Here is the response text."
    trace: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockDha:
    """Mock DHA result for testing."""
    guarded_text: str = "Guarded response text."
    tone_profile: str = "balanced"
    readiness_level: str = "medium"
    resistance_level: str = "low"


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    request: Optional[MockRequest] = None
    mlcr: Optional[MockMlcr] = None
    fusion: Optional[MockFusion] = None
    dha: Optional[MockDha] = None
    p27_persona: Optional[Any] = None


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestP27AuthorityEnum:
    """Tests for P27Authority enum."""

    def test_high_authority_value(self):
        """Test: HIGH authority exists."""
        assert P27Authority.HIGH.value == "high"

    def test_medium_authority_value(self):
        """Test: MEDIUM authority exists."""
        assert P27Authority.MEDIUM.value == "medium"

    def test_low_authority_value(self):
        """Test: LOW authority exists."""
        assert P27Authority.LOW.value == "low"

    def test_all_authorities_exist(self):
        """Test: all three authority levels exist."""
        authorities = list(P27Authority)
        assert len(authorities) == 3
        assert P27Authority.HIGH in authorities
        assert P27Authority.MEDIUM in authorities
        assert P27Authority.LOW in authorities


class TestPersonaSelectionModeEnum:
    """Tests for PersonaSelectionMode enum."""

    def test_automatic_mode_value(self):
        """Test: AUTOMATIC mode exists."""
        assert PersonaSelectionMode.AUTOMATIC.value == "automatic"

    def test_hint_guided_mode_value(self):
        """Test: HINT_GUIDED mode exists."""
        assert PersonaSelectionMode.HINT_GUIDED.value == "hint_guided"

    def test_forced_mode_value(self):
        """Test: FORCED mode exists."""
        assert PersonaSelectionMode.FORCED.value == "forced"

    def test_all_modes_exist(self):
        """Test: all three selection modes exist."""
        modes = list(PersonaSelectionMode)
        assert len(modes) == 3


class TestPersonaCategoryEnum:
    """Tests for PersonaCategory enum."""

    def test_sage_category_value(self):
        """Test: SAGE category exists."""
        assert PersonaCategory.SAGE.value == "sage"

    def test_analyst_category_value(self):
        """Test: ANALYST category exists."""
        assert PersonaCategory.ANALYST.value == "analyst"

    def test_coach_category_value(self):
        """Test: COACH category exists."""
        assert PersonaCategory.COACH.value == "coach"

    def test_friendly_category_value(self):
        """Test: FRIENDLY category exists."""
        assert PersonaCategory.FRIENDLY.value == "friendly"

    def test_regulator_category_value(self):
        """Test: REGULATOR category exists."""
        assert PersonaCategory.REGULATOR.value == "regulator"

    def test_neutral_category_value(self):
        """Test: NEUTRAL category exists."""
        assert PersonaCategory.NEUTRAL.value == "neutral"

    def test_all_categories_exist(self):
        """Test: all six persona categories exist."""
        categories = list(PersonaCategory)
        assert len(categories) == 6


# =============================================================================
# P27 SELECTION SIGNALS TESTS
# =============================================================================


class TestP27SelectionSignals:
    """Tests for P27SelectionSignals dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with required fields."""
        signals = P27SelectionSignals(
            query_text="Test query",
            response_text="Test response",
        )
        assert signals.query_text == "Test query"
        assert signals.response_text == "Test response"
        assert signals.tier == "hybrid"  # default
        assert signals.mode == PersonaSelectionMode.AUTOMATIC  # default

    def test_full_construction(self):
        """Test: construction with all fields."""
        signals = P27SelectionSignals(
            query_text="Why do I feel stuck?",
            response_text="Career plateaus are common.",
            tier="lower",
            intent="emotional",
            domain="psychology",
            emotional_entropy=0.7,
            cognitive_entropy=0.4,
            readiness_score=0.6,
            resistance_score=0.2,
            mode=PersonaSelectionMode.HINT_GUIDED,
            persona_hint="coach",
        )
        assert signals.domain == "psychology"
        assert signals.emotional_entropy == 0.7
        assert signals.persona_hint == "coach"

    def test_emotional_entropy_clamping_high(self):
        """Test: emotional_entropy above 1.0 is clamped to 1.0."""
        signals = P27SelectionSignals(
            query_text="test",
            response_text="test",
            emotional_entropy=1.5,
        )
        assert signals.emotional_entropy == 1.0

    def test_emotional_entropy_clamping_low(self):
        """Test: emotional_entropy below 0.0 is clamped to 0.0."""
        signals = P27SelectionSignals(
            query_text="test",
            response_text="test",
            emotional_entropy=-0.3,
        )
        assert signals.emotional_entropy == 0.0

    def test_cognitive_entropy_clamping(self):
        """Test: cognitive_entropy is clamped to [0, 1]."""
        signals_high = P27SelectionSignals(
            query_text="test",
            response_text="test",
            cognitive_entropy=2.0,
        )
        assert signals_high.cognitive_entropy == 1.0

        signals_low = P27SelectionSignals(
            query_text="test",
            response_text="test",
            cognitive_entropy=-1.0,
        )
        assert signals_low.cognitive_entropy == 0.0

    def test_readiness_score_clamping(self):
        """Test: readiness_score is clamped to [0, 1]."""
        signals = P27SelectionSignals(
            query_text="test",
            response_text="test",
            readiness_score=1.5,
        )
        assert signals.readiness_score == 1.0

    def test_resistance_score_clamping(self):
        """Test: resistance_score is clamped to [0, 1]."""
        signals = P27SelectionSignals(
            query_text="test",
            response_text="test",
            resistance_score=-0.2,
        )
        assert signals.resistance_score == 0.0

    def test_immutability(self):
        """Test: P27SelectionSignals is frozen (immutable)."""
        signals = P27SelectionSignals(
            query_text="test",
            response_text="test",
        )
        with pytest.raises(Exception):
            signals.tier = "upper"


# =============================================================================
# P27 PERSONA DIRECTIVES TESTS
# =============================================================================


class TestP27PersonaDirectives:
    """Tests for P27PersonaDirectives dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with defaults."""
        directives = P27PersonaDirectives()
        assert directives.tone_warmth == 0.5
        assert directives.formality_level == 0.5
        assert directives.directness == 0.5
        assert directives.use_metaphors is False
        assert directives.use_technical_terms is True

    def test_custom_construction(self):
        """Test: construction with custom values."""
        directives = P27PersonaDirectives(
            tone_warmth=0.8,
            formality_level=0.3,
            directness=0.7,
            use_metaphors=True,
            use_technical_terms=False,
            preferred_pronouns="we",
            domain_vocabulary={"market", "portfolio"},
        )
        assert directives.tone_warmth == 0.8
        assert directives.use_metaphors is True
        assert "market" in directives.domain_vocabulary

    def test_to_dict(self):
        """Test: to_dict serialization."""
        directives = P27PersonaDirectives(
            tone_warmth=0.7,
            use_metaphors=True,
            domain_vocabulary={"test", "word"},
        )
        result = directives.to_dict()

        assert result["tone_warmth"] == 0.7
        assert result["use_metaphors"] is True
        assert "test" in result["domain_vocabulary"]
        assert isinstance(result["domain_vocabulary"], list)

    def test_immutability(self):
        """Test: P27PersonaDirectives is frozen (immutable)."""
        directives = P27PersonaDirectives()
        with pytest.raises(Exception):
            directives.tone_warmth = 0.9


# =============================================================================
# P27 OUTPUT TESTS
# =============================================================================


class TestP27Output:
    """Tests for P27Output dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with required fields."""
        output = P27Output(
            persona_id="coach",
            persona_category=PersonaCategory.COACH,
            selection_mode=PersonaSelectionMode.AUTOMATIC,
        )
        assert output.persona_id == "coach"
        assert output.persona_category == PersonaCategory.COACH
        assert output.selection_confidence == 0.8  # default
        assert output.authority == P27Authority.MEDIUM  # default

    def test_full_construction(self):
        """Test: construction with all fields."""
        directives = P27PersonaDirectives(tone_warmth=0.7)
        output = P27Output(
            persona_id="analyst",
            persona_category=PersonaCategory.ANALYST,
            selection_mode=PersonaSelectionMode.FORCED,
            selection_confidence=0.95,
            authority=P27Authority.HIGH,
            directives=directives,
            selection_reasoning=["Forced by user"],
            alternatives=["neutral", "sage"],
        )
        assert output.selection_confidence == 0.95
        assert output.authority == P27Authority.HIGH
        assert "Forced by user" in output.selection_reasoning

    def test_confidence_clamping_high(self):
        """Test: selection_confidence above 1.0 is clamped."""
        output = P27Output(
            persona_id="neutral",
            persona_category=PersonaCategory.NEUTRAL,
            selection_mode=PersonaSelectionMode.AUTOMATIC,
            selection_confidence=1.5,
        )
        assert output.selection_confidence == 1.0

    def test_confidence_clamping_low(self):
        """Test: selection_confidence below 0.0 is clamped."""
        output = P27Output(
            persona_id="neutral",
            persona_category=PersonaCategory.NEUTRAL,
            selection_mode=PersonaSelectionMode.AUTOMATIC,
            selection_confidence=-0.2,
        )
        assert output.selection_confidence == 0.0

    def test_to_dict(self):
        """Test: to_dict serialization."""
        output = P27Output(
            persona_id="coach",
            persona_category=PersonaCategory.COACH,
            selection_mode=PersonaSelectionMode.AUTOMATIC,
            selection_confidence=0.85,
            authority=P27Authority.MEDIUM,
            selection_reasoning=["Domain=psychology → coach"],
            alternatives=["neutral", "friendly"],
        )
        result = output.to_dict()

        assert result["phase"] == "P27"
        assert result["version"] == VERSION
        assert result["persona_id"] == "coach"
        assert result["persona_category"] == "coach"
        assert result["selection_mode"] == "automatic"
        assert result["selection_confidence"] == 0.85
        assert result["authority"] == "medium"
        assert "Domain=psychology → coach" in result["selection_reasoning"]

    def test_immutability(self):
        """Test: P27Output is frozen (immutable)."""
        output = P27Output(
            persona_id="neutral",
            persona_category=PersonaCategory.NEUTRAL,
            selection_mode=PersonaSelectionMode.AUTOMATIC,
        )
        with pytest.raises(Exception):
            output.persona_id = "sage"


# =============================================================================
# PERSONA SELECTION LOGIC TESTS
# =============================================================================


class TestPersonaSelectionByDomain:
    """Tests for domain-based persona selection."""

    def test_psychology_domain_selects_coach(self):
        """Test: psychology domain → coach persona."""
        signals = P27SelectionSignals(
            query_text="Why am I feeling anxious?",
            response_text="Anxiety can have many sources.",
            domain="psychology",
        )
        output = run_p27_selection(signals)

        assert output.persona_id == "coach"
        assert output.persona_category == PersonaCategory.COACH

    def test_finance_domain_selects_analyst(self):
        """Test: finance domain → analyst persona."""
        signals = P27SelectionSignals(
            query_text="What's my portfolio risk?",
            response_text="Your portfolio has moderate risk.",
            domain="finance",
        )
        output = run_p27_selection(signals)

        assert output.persona_id == "analyst"
        assert output.persona_category == PersonaCategory.ANALYST

    def test_medical_domain_selects_sage(self):
        """Test: medical domain → sage persona."""
        signals = P27SelectionSignals(
            query_text="What are my treatment options?",
            response_text="Several treatments are available.",
            domain="medical",
        )
        output = run_p27_selection(signals)

        assert output.persona_id == "sage"
        assert output.persona_category == PersonaCategory.SAGE

    def test_generic_domain_selects_neutral(self):
        """Test: generic domain → neutral persona."""
        signals = P27SelectionSignals(
            query_text="What time is it?",
            response_text="It's noon.",
            domain="generic",
        )
        output = run_p27_selection(signals)

        # Generic domain with no other signals → neutral
        assert output.persona_id in ["neutral", "friendly", "coach", "analyst", "sage"]


class TestPersonaSelectionByTier:
    """Tests for tier-based persona selection."""

    def test_lower_tier_high_emotional_entropy_selects_friendly(self):
        """Test: lower tier + high emotional entropy → friendly persona."""
        signals = P27SelectionSignals(
            query_text="I'm so confused and upset.",
            response_text="I understand your feelings.",
            tier="lower",
            domain="generic",
            emotional_entropy=0.8,
        )
        output = run_p27_selection(signals)

        assert output.persona_id == "friendly"
        assert output.persona_category == PersonaCategory.FRIENDLY

    def test_upper_tier_low_cognitive_entropy_selects_analyst(self):
        """Test: upper tier + low cognitive entropy → analyst persona."""
        signals = P27SelectionSignals(
            query_text="Calculate the optimal allocation.",
            response_text="The optimal allocation is 60/40.",
            tier="upper",
            domain="generic",
            cognitive_entropy=0.2,
        )
        output = run_p27_selection(signals)

        assert output.persona_id == "analyst"
        assert output.persona_category == PersonaCategory.ANALYST


class TestPersonaSelectionByResistance:
    """Tests for resistance-based persona selection."""

    def test_high_resistance_selects_coach(self):
        """Test: high resistance → coach persona for support."""
        signals = P27SelectionSignals(
            query_text="I don't want to hear this.",
            response_text="I understand your concern.",
            domain="generic",
            resistance_score=0.7,
        )
        output = run_p27_selection(signals)

        assert output.persona_id == "coach"
        assert output.persona_category == PersonaCategory.COACH
        assert "resistance" in " ".join(output.selection_reasoning).lower()


class TestPersonaSelectionModes:
    """Tests for different selection modes."""

    def test_forced_mode_uses_hint(self):
        """Test: FORCED mode uses persona_hint directly."""
        signals = P27SelectionSignals(
            query_text="Test",
            response_text="Test",
            mode=PersonaSelectionMode.FORCED,
            persona_hint="sage",
        )
        output = run_p27_selection(signals)

        assert output.persona_id == "sage"
        assert output.selection_confidence == 1.0
        assert output.authority == P27Authority.HIGH

    def test_hint_guided_mode_uses_hint(self):
        """Test: HINT_GUIDED mode uses persona_hint."""
        signals = P27SelectionSignals(
            query_text="Test",
            response_text="Test",
            mode=PersonaSelectionMode.HINT_GUIDED,
            persona_hint="friendly",
        )
        output = run_p27_selection(signals)

        assert output.persona_id == "friendly"
        assert output.selection_confidence == 0.9

    def test_automatic_mode_ignores_hint(self):
        """Test: AUTOMATIC mode selects based on signals."""
        signals = P27SelectionSignals(
            query_text="What's my risk?",
            response_text="Risk analysis here.",
            domain="finance",
            mode=PersonaSelectionMode.AUTOMATIC,
        )
        output = run_p27_selection(signals)

        # Should select analyst for finance domain
        assert output.persona_id == "analyst"


# =============================================================================
# INTEGRATION FUNCTION TESTS
# =============================================================================


class TestSignalExtraction:
    """Tests for extract_p27_signals function."""

    def test_extract_from_minimal_context(self):
        """Test: extraction from minimal context."""
        ctx = MockPipelineContext(
            request=MockRequest(text="Test question"),
            fusion=MockFusion(merged_output="Test response"),
        )
        signals = extract_p27_signals(ctx)

        assert signals is not None
        assert signals.query_text == "Test question"
        assert signals.response_text == "Test response"

    def test_extract_from_full_context(self):
        """Test: extraction from full context with MLCR."""
        ctx = MockPipelineContext(
            request=MockRequest(text="Help me with finances"),
            mlcr=MockMlcr(
                explain_log={
                    "meta": {"tier": "upper", "intent": "practical", "domain": "finance"},
                    "entropy": {"H_D": 0.3, "H_K": 0.4},
                }
            ),
            fusion=MockFusion(merged_output="Financial advice here."),
        )
        signals = extract_p27_signals(ctx)

        assert signals is not None
        assert signals.tier == "upper"
        assert signals.domain == "finance"
        assert signals.emotional_entropy == 0.3

    def test_extract_with_dha_context(self):
        """Test: extraction includes DHA readiness/resistance."""
        ctx = MockPipelineContext(
            request=MockRequest(text="Test"),
            fusion=MockFusion(),
            dha=MockDha(
                guarded_text="DHA output",
                readiness_level="high",
                resistance_level="low",
            ),
        )
        signals = extract_p27_signals(ctx)

        assert signals is not None
        assert signals.response_text == "DHA output"
        # Readiness "high" maps to 0.7, resistance "low" maps to 0.2
        assert signals.readiness_score == 0.7
        assert signals.resistance_score == 0.2

    def test_extract_with_persona_hint(self):
        """Test: extraction detects persona hint in request metadata."""
        ctx = MockPipelineContext(
            request=MockRequest(
                text="Test",
                metadata={"persona_hint": "sage"},
            ),
            fusion=MockFusion(),
        )
        signals = extract_p27_signals(ctx)

        assert signals is not None
        assert signals.persona_hint == "sage"
        assert signals.mode == PersonaSelectionMode.HINT_GUIDED

    def test_extract_returns_none_on_error(self):
        """Test: extraction returns None on error."""
        # Empty context
        ctx = MockPipelineContext()
        signals = extract_p27_signals(ctx)

        # Should still return signals with defaults (not None)
        assert signals is not None


class TestMaybeRunP27:
    """Tests for maybe_run_p27 function."""

    def test_maybe_run_returns_output(self):
        """Test: maybe_run_p27 returns P27Output."""
        ctx = MockPipelineContext(
            request=MockRequest(text="Help me"),
            mlcr=MockMlcr(
                explain_log={
                    "meta": {"tier": "hybrid", "domain": "generic"},
                }
            ),
            fusion=MockFusion(),
        )
        output = maybe_run_p27(ctx)

        assert output is not None
        assert isinstance(output, P27Output)
        assert output.persona_id in ["neutral", "coach", "analyst", "sage", "friendly", "regulator"]

    def test_maybe_run_with_psychology_domain(self):
        """Test: maybe_run_p27 selects coach for psychology domain."""
        ctx = MockPipelineContext(
            request=MockRequest(text="I feel anxious"),
            mlcr=MockMlcr(
                explain_log={
                    "meta": {"tier": "lower", "domain": "psychology"},
                }
            ),
            fusion=MockFusion(),
        )
        output = maybe_run_p27(ctx)

        assert output is not None
        assert output.persona_id == "coach"


class TestGetP27Output:
    """Tests for get_p27_output function."""

    def test_get_output_when_present(self):
        """Test: get_p27_output returns output when present."""
        expected = P27Output(
            persona_id="coach",
            persona_category=PersonaCategory.COACH,
            selection_mode=PersonaSelectionMode.AUTOMATIC,
        )
        ctx = MockPipelineContext(p27_persona=expected)

        result = get_p27_output(ctx)
        assert result is expected

    def test_get_output_when_absent(self):
        """Test: get_p27_output returns None when absent."""
        ctx = MockPipelineContext()
        result = get_p27_output(ctx)
        assert result is None


class TestGetP27PersonaId:
    """Tests for get_p27_persona_id function."""

    def test_get_persona_id_when_present(self):
        """Test: get_p27_persona_id returns persona_id when present."""
        output = P27Output(
            persona_id="analyst",
            persona_category=PersonaCategory.ANALYST,
            selection_mode=PersonaSelectionMode.AUTOMATIC,
        )
        ctx = MockPipelineContext(p27_persona=output)

        result = get_p27_persona_id(ctx)
        assert result == "analyst"

    def test_get_persona_id_when_absent(self):
        """Test: get_p27_persona_id returns 'neutral' when absent."""
        ctx = MockPipelineContext()
        result = get_p27_persona_id(ctx)
        assert result == "neutral"


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingletons:
    """Tests for singleton instances."""

    def test_persona_engine_singleton(self):
        """Test: get_persona_engine returns singleton."""
        engine1 = get_persona_engine()
        engine2 = get_persona_engine()
        assert engine1 is engine2

    def test_persona_selector_singleton(self):
        """Test: get_persona_selector returns singleton."""
        selector1 = get_persona_selector()
        selector2 = get_persona_selector()
        assert selector1 is selector2


# =============================================================================
# DETERMINISM TESTS
# =============================================================================


class TestDeterminism:
    """Tests verifying deterministic behavior."""

    def test_same_input_same_output(self):
        """Test: same signals produce same output."""
        signals = P27SelectionSignals(
            query_text="Test query",
            response_text="Test response",
            domain="psychology",
            tier="lower",
        )

        results = []
        for _ in range(10):
            output = run_p27_selection(signals)
            results.append((output.persona_id, output.selection_confidence))

        # All results should be identical
        assert all(r == results[0] for r in results)

    def test_serialization_consistent(self):
        """Test: serialization is consistent."""
        signals = P27SelectionSignals(
            query_text="Test",
            response_text="Test",
            domain="finance",
        )

        serialized = []
        for _ in range(5):
            output = run_p27_selection(signals)
            serialized.append(output.to_dict()["persona_id"])

        assert all(s == serialized[0] for s in serialized)


# =============================================================================
# ARCHITECTURAL PHASE TESTS
# =============================================================================


class TestArchitecturalPhase:
    """Tests verifying architectural phase identification."""

    def test_output_identifies_as_p27(self):
        """Test: output correctly identifies as P27."""
        output = P27Output(
            persona_id="neutral",
            persona_category=PersonaCategory.NEUTRAL,
            selection_mode=PersonaSelectionMode.AUTOMATIC,
        )

        result = output.to_dict()
        assert result["phase"] == "P27"

    def test_output_includes_version(self):
        """Test: output includes version."""
        output = P27Output(
            persona_id="neutral",
            persona_category=PersonaCategory.NEUTRAL,
            selection_mode=PersonaSelectionMode.AUTOMATIC,
        )

        result = output.to_dict()
        assert result["version"] == VERSION


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
