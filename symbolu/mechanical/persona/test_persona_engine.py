"""
Persona Engine Test Suite (v2.8.2)
====================================

Comprehensive testing for all Persona Engine components:
    - Unit tests for each class
    - Integration tests for complete pipeline
    - Scenario tests for real-world use cases
    - Tone-persona interaction tests
    - Layer integrity validation tests
    - Metadata propagation tests
    - Edge case and negative tests

Run with: pytest test_persona_engine.py -v
"""

import pytest
from typing import Dict, Any
from .models import RendererOutputV3, DHAResult, PersonaProfile
from .engine import PersonaEngine
from .selector import PersonaSelector
from .registry import PersonaRegistry, reset_default_registry
from .default_personas import (
    DEFAULT_PERSONAS,
    SAGE_PERSONA,
    ANALYST_PERSONA,
    COACH_PERSONA,
    FRIENDLY_PERSONA,
    REGULATOR_PERSONA,
    NEUTRAL_PERSONA
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def reset_registry():
    """Reset default registry before each test."""
    reset_default_registry()
    yield
    reset_default_registry()


@pytest.fixture
def registry():
    """Create a fresh registry with default personas."""
    return PersonaRegistry()


@pytest.fixture
def selector():
    """Create a fresh selector."""
    return PersonaSelector()


@pytest.fixture
def engine(registry, selector):
    """Create a fresh engine."""
    return PersonaEngine(registry, selector)


@pytest.fixture
def renderer_output_trading():
    """Sample renderer output for trading domain."""
    return RendererOutputV3(
        symbolic_layer={"pattern": "seeking certainty in uncertainty"},
        practical_layer={"steps": ["assess risk", "define position", "set stop-loss"]},
        mirror_truth_layer={"reflection": "avoiding emotional decision"},
        metadata={
            "tier": "HYBRID",
            "domain": "trading",
            "intent": "how",
            "confidence": {"symbolic": 0.71, "practical": 0.88, "mirror": 0.65}
        }
    )


@pytest.fixture
def renderer_output_emotional():
    """Sample renderer output for emotional domain."""
    return RendererOutputV3(
        symbolic_layer={"pattern": "grief and acceptance"},
        practical_layer={"steps": ["acknowledge feelings", "seek support"]},
        mirror_truth_layer={"reflection": "resisting the pain of loss"},
        metadata={
            "tier": "UPPER",
            "domain": "emotional",
            "intent": "why",
            "confidence": {"symbolic": 0.85, "practical": 0.65, "mirror": 0.92}
        }
    )


@pytest.fixture
def dha_resonance():
    """DHA result with resonance tone."""
    return DHAResult(
        tone="resonance",
        confidence=0.88,
        justification={
            "entropy_reason": "Low entropy suggests stability",
            "bhava_reason": "Upward Bhava indicates receptivity"
        }
    )


@pytest.fixture
def dha_inverse_jolt():
    """DHA result with inverse_jolt tone."""
    return DHAResult(
        tone="inverse_jolt",
        confidence=0.92,
        justification={
            "entropy_reason": "High entropy requires grounding"
        }
    )


@pytest.fixture
def dha_symbolic():
    """DHA result with symbolic tone."""
    return DHAResult(
        tone="symbolic",
        confidence=0.76,
        justification={
            "bhava_reason": "Upward movement supports metaphor"
        }
    )


@pytest.fixture
def explain_log_trading():
    """Explain log for trading domain."""
    return {
        "meta": {
            "domain": "trading",
            "tier": "HYBRID",
            "intent": "how",
            "bhava_direction": "neutral"
        }
    }


@pytest.fixture
def explain_log_emotional():
    """Explain log for emotional domain."""
    return {
        "meta": {
            "domain": "emotional",
            "tier": "UPPER",
            "intent": "why",
            "bhava_direction": "downward"
        }
    }


# =============================================================================
# TEST 1: PERSONA SELECTOR LOGIC
# =============================================================================

class TestPersonaSelector:
    """Test persona selection logic."""
    
    def test_selector_trading_domain(self, selector, explain_log_trading):
        """Trading domain should select analyst."""
        persona_id = selector.auto_select(explain_log_trading)
        assert persona_id == "analyst"
    
    def test_selector_emotional_domain(self, selector, explain_log_emotional):
        """Emotional domain should select friendly."""
        persona_id = selector.auto_select(explain_log_emotional)
        assert persona_id == "friendly"
    
    def test_selector_user_override(self, selector, explain_log_trading):
        """User override should always win."""
        persona_id = selector.auto_select(explain_log_trading, user_override="coach")
        assert persona_id == "coach"
    
    def test_selector_medical_domain(self, selector):
        """Medical domain should always select regulator."""
        log = {"meta": {"domain": "medical"}}
        persona_id = selector.auto_select(log)
        assert persona_id == "regulator"
    
    def test_selector_upper_tier(self, selector):
        """UPPER tier should prefer sage."""
        log = {"meta": {"tier": "UPPER", "intent": "why"}}
        persona_id = selector.auto_select(log)
        assert persona_id == "sage"
    
    def test_selector_lower_tier_how(self, selector):
        """LOWER tier with 'how' intent should select coach."""
        log = {"meta": {"tier": "LOWER", "intent": "how"}}
        persona_id = selector.auto_select(log)
        assert persona_id == "coach"
    
    def test_selector_fallback_neutral(self, selector):
        """Empty log should fallback to neutral."""
        persona_id = selector.auto_select({})
        assert persona_id == "neutral"


# =============================================================================
# TEST 2: PERSONA ORDERING LOGIC
# =============================================================================

class TestPersonaOrdering:
    """Test layer ordering logic."""
    
    def test_ordering_analyst(self, engine, renderer_output_trading, dha_resonance):
        """Analyst should order: practical, symbolic, mirror."""
        persona = engine.registry.get("analyst")
        ordered = engine._order_layers(
            persona, dha_resonance.tone,
            renderer_output_trading.symbolic_layer,
            renderer_output_trading.practical_layer,
            renderer_output_trading.mirror_truth_layer
        )
        names = [name for name, _ in ordered]
        assert names == ["practical", "symbolic", "mirror"]
    
    def test_ordering_sage(self, engine, renderer_output_trading, dha_resonance):
        """Sage should order: symbolic, practical, mirror."""
        persona = engine.registry.get("sage")
        ordered = engine._order_layers(
            persona, dha_resonance.tone,
            renderer_output_trading.symbolic_layer,
            renderer_output_trading.practical_layer,
            renderer_output_trading.mirror_truth_layer
        )
        names = [name for name, _ in ordered]
        assert names == ["symbolic", "practical", "mirror"]
    
    def test_ordering_coach(self, engine, renderer_output_trading, dha_resonance):
        """Coach should order: mirror, practical, symbolic."""
        persona = engine.registry.get("coach")
        ordered = engine._order_layers(
            persona, dha_resonance.tone,
            renderer_output_trading.symbolic_layer,
            renderer_output_trading.practical_layer,
            renderer_output_trading.mirror_truth_layer
        )
        names = [name for name, _ in ordered]
        assert names == ["mirror", "practical", "symbolic"]


# =============================================================================
# TEST 3: TONE OVERRIDES
# =============================================================================

class TestToneOverrides:
    """Test that tone overrides persona ordering."""
    
    def test_inverse_jolt_overrides_sage(self, engine, renderer_output_trading, dha_inverse_jolt):
        """Inverse jolt should move mirror first, even for sage."""
        persona = engine.registry.get("sage")
        ordered = engine._order_layers(
            persona, dha_inverse_jolt.tone,
            renderer_output_trading.symbolic_layer,
            renderer_output_trading.practical_layer,
            renderer_output_trading.mirror_truth_layer
        )
        names = [name for name, _ in ordered]
        assert names[0] == "mirror"
    
    def test_symbolic_tone_overrides_analyst(self, engine, renderer_output_trading, dha_symbolic):
        """Symbolic tone should move symbolic first, even for analyst."""
        persona = engine.registry.get("analyst")
        ordered = engine._order_layers(
            persona, dha_symbolic.tone,
            renderer_output_trading.symbolic_layer,
            renderer_output_trading.practical_layer,
            renderer_output_trading.mirror_truth_layer
        )
        names = [name for name, _ in ordered]
        assert names[0] == "symbolic"


# =============================================================================
# TEST 4: TEXT COMPOSITION
# =============================================================================

class TestTextComposition:
    """Test text generation."""
    
    def test_text_includes_intro(self, engine, renderer_output_trading, dha_resonance):
        """Text should include persona intro template."""
        persona = engine.registry.get("analyst")
        ordered = [("practical", {"test": "value"})]
        text = engine._compose_text(persona, dha_resonance.tone, ordered)
        assert "Let's break this down step-by-step:" in text
    
    def test_text_includes_headers(self, engine, renderer_output_trading, dha_resonance):
        """Text should include proper headers."""
        persona = engine.registry.get("analyst")
        ordered = [
            ("practical", {"test": "value"}),
            ("symbolic", {"test": "value"}),
            ("mirror", {"test": "value"})
        ]
        text = engine._compose_text(persona, dha_resonance.tone, ordered)
        assert "● Practical explanation:" in text
        assert "● Deeper symbolic insight:" in text
        assert "● Reflection:" in text


# =============================================================================
# TEST 5: LAYER INTEGRITY
# =============================================================================

class TestLayerIntegrity:
    """Test that layers are never modified."""
    
    def test_layers_not_mutated(self, engine, renderer_output_trading, dha_resonance, explain_log_trading):
        """Layers must not be modified by persona engine."""
        # Deep copy original
        original_symbolic = dict(renderer_output_trading.symbolic_layer)
        original_practical = dict(renderer_output_trading.practical_layer)
        original_mirror = dict(renderer_output_trading.mirror_truth_layer)
        
        # Apply persona engine
        response = engine.apply(renderer_output_trading, dha_resonance, explain_log_trading)
        
        # Verify no mutation
        assert response.layers["symbolic_layer"] == original_symbolic
        assert response.layers["practical_layer"] == original_practical
        assert response.layers["mirror_truth_layer"] == original_mirror


# =============================================================================
# TEST 6: METADATA PROPAGATION
# =============================================================================

class TestMetadataPropagation:
    """Test metadata preservation and propagation."""
    
    def test_metadata_includes_persona(self, engine, renderer_output_trading, dha_resonance, explain_log_trading):
        """Metadata should include persona information."""
        response = engine.apply(renderer_output_trading, dha_resonance, explain_log_trading)
        assert response.metadata.persona_id == "analyst"
        assert response.metadata.persona_name == "The Analyst"
        assert len(response.metadata.persona_description) > 0
    
    def test_metadata_includes_dha(self, engine, renderer_output_trading, dha_resonance, explain_log_trading):
        """Metadata should include DHA information."""
        response = engine.apply(renderer_output_trading, dha_resonance, explain_log_trading)
        assert response.metadata.dha_tone == "resonance"
        assert response.metadata.dha_confidence == 0.88
    
    def test_metadata_includes_original(self, engine, renderer_output_trading, dha_resonance, explain_log_trading):
        """Metadata should include original renderer metadata."""
        response = engine.apply(renderer_output_trading, dha_resonance, explain_log_trading)
        assert response.metadata.tier == "HYBRID"
        assert response.metadata.domain == "trading"
        assert response.metadata.intent == "how"


# =============================================================================
# TEST 7: EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_explain_log(self, engine, renderer_output_trading, dha_resonance):
        """Empty explain log should use fallback persona."""
        response = engine.apply(renderer_output_trading, dha_resonance, {})
        assert response.persona_id == "neutral"
    
    def test_empty_layers(self, engine, dha_resonance):
        """Empty layers should not break composition."""
        renderer_output = RendererOutputV3(
            symbolic_layer={},
            practical_layer={},
            mirror_truth_layer={},
            metadata={"tier": "UNKNOWN"}
        )
        response = engine.apply(renderer_output, dha_resonance, {})
        assert isinstance(response.text, str)
        assert len(response.text) > 0
    
    def test_invalid_persona_override(self, engine, renderer_output_trading, dha_resonance, explain_log_trading):
        """Invalid persona override should fallback to neutral."""
        response = engine.apply(
            renderer_output_trading,
            dha_resonance,
            explain_log_trading,
            user_persona_override="invalid_persona"
        )
        # Should fallback to neutral
        assert response.persona_id == "neutral"


# =============================================================================
# TEST 8: INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """End-to-end integration tests."""
    
    def test_complete_trading_pipeline(self, engine, renderer_output_trading, dha_resonance, explain_log_trading):
        """Complete pipeline for trading scenario."""
        response = engine.apply(renderer_output_trading, dha_resonance, explain_log_trading)
        
        assert response.persona_id == "analyst"
        assert "step-by-step" in response.text.lower()
        assert response.metadata.tier == "HYBRID"
        assert response.metadata.domain == "trading"
    
    def test_complete_emotional_pipeline(self, engine, renderer_output_emotional, dha_resonance, explain_log_emotional):
        """Complete pipeline for emotional scenario."""
        response = engine.apply(renderer_output_emotional, dha_resonance, explain_log_emotional)
        
        assert response.persona_id == "friendly"
        assert response.metadata.tier == "UPPER"
        assert response.metadata.domain == "emotional"


# =============================================================================
# TEST 9: REGISTRY OPERATIONS
# =============================================================================

class TestPersonaRegistry:
    """Test registry operations."""
    
    def test_registry_get(self, registry):
        """Registry should retrieve personas by ID."""
        persona = registry.get("analyst")
        assert persona.id == "analyst"
    
    def test_registry_list(self, registry):
        """Registry should list all personas."""
        ids = registry.list_ids()
        assert "sage" in ids
        assert "analyst" in ids
        assert len(ids) == 6
    
    def test_registry_register_new(self, registry):
        """Registry should allow registering new personas."""
        new_persona = PersonaProfile(
            id="custom",
            display_name="Custom",
            description="Test persona",
            formality=0.5,
            warmth=0.5,
            directness=0.5
        )
        registry.register(new_persona)
        assert registry.exists("custom")
        retrieved = registry.get("custom")
        assert retrieved.id == "custom"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
