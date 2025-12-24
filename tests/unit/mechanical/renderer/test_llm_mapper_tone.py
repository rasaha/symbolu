"""
Test Suite: LLM Renderer Mapper Tone Integration
==================================================

Tests the mapper tone integration in LLMRenderer.

Test Cases:
1. LCM produces short, clipped, actionable tone
2. HRM produces clearer transitions and deeper detail
3. LAM produces reflective, slow cadence tone
"""

import pytest
from symbolu.mechanical.renderer.llm_renderer import LLMRenderer
from symbolu.mechanical.pipeline.models import MapperProfile


@pytest.fixture
def llm_renderer():
    """Create an LLM renderer instance."""
    return LLMRenderer(provider="anthropic")


@pytest.fixture
def sample_text():
    """Create sample text for tone modulation testing."""
    return (
        "The analysis reveals multiple dimensions of complexity. "
        "First, we observe the structural patterns emerging from the data. "
        "Second, there are underlying behavioral tendencies that require attention. "
        "Finally, the synthesis of these elements suggests a coherent framework."
    )


def test_lcm_short_clipped_actionable_tone(llm_renderer, sample_text):
    """Test that LCM profile produces short, clipped, actionable tone."""
    # Create LCM profile
    lcm_profile = MapperProfile(
        resolution_level="low",
        arc_mode="none",
        detail_bias=0.2,
        practical_bias=0.9,
        reflective_bias=0.2
    )

    # Apply mapper tone
    modulated = llm_renderer.apply_mapper_tone(sample_text, lcm_profile)

    # Assertions
    assert modulated is not None
    assert len(modulated) < len(sample_text), \
        "Expected LCM to shorten text"

    # Check for simplified structure (fewer sentences)
    original_sentences = [s.strip() for s in sample_text.split('.') if s.strip()]
    modulated_sentences = [s.strip() for s in modulated.split('.') if s.strip()]

    assert len(modulated_sentences) <= 3, \
        f"Expected max 3 sentences for LCM, got {len(modulated_sentences)}"

    # Check for removal of subordinate clauses (fewer commas)
    original_commas = sample_text.count(',')
    modulated_commas = modulated.count(',')

    assert modulated_commas < original_commas or modulated_commas == 0, \
        "Expected fewer or no commas in LCM tone"


def test_hrm_transitions_and_detail(llm_renderer, sample_text):
    """Test that HRM profile adds clearer transitions and detail."""
    # Create HRM profile
    hrm_profile = MapperProfile(
        resolution_level="high",
        arc_mode="none",
        detail_bias=0.8,
        practical_bias=0.3,
        reflective_bias=0.6
    )

    # Apply mapper tone
    modulated = llm_renderer.apply_mapper_tone(sample_text, hrm_profile)

    # Assertions
    assert modulated is not None

    # Check for transitional phrases
    transition_words = ["furthermore", "moreover", "in addition", "specifically"]
    modulated_lower = modulated.lower()

    has_transitions = any(word in modulated_lower for word in transition_words)
    assert has_transitions, \
        f"Expected transitional phrases in HRM tone, got: {modulated}"


def test_lam_reflective_slow_cadence(llm_renderer, sample_text):
    """Test that LAM profile produces reflective, slow cadence tone."""
    # Create LAM profile with temporal arc
    lam_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="temporal",
        detail_bias=0.5,
        practical_bias=0.3,
        reflective_bias=0.8
    )

    # Apply mapper tone
    modulated = llm_renderer.apply_mapper_tone(sample_text, lam_profile)

    # Assertions
    assert modulated is not None

    # Check for temporal/arc markers
    arc_markers = [
        "over time", "as patterns emerge", "through this progression",
        "temporal", "pattern", "context"
    ]
    modulated_lower = modulated.lower()

    has_arc_markers = any(marker in modulated_lower for marker in arc_markers)
    assert has_arc_markers, \
        f"Expected arc markers in LAM tone, got: {modulated}"


def test_lam_identity_arc_markers(llm_renderer, sample_text):
    """Test that LAM profile with identity arc uses identity markers."""
    # Create LAM profile with identity arc
    lam_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="identity",
        detail_bias=0.5,
        practical_bias=0.3,
        reflective_bias=0.8
    )

    # Apply mapper tone
    modulated = llm_renderer.apply_mapper_tone(sample_text, lam_profile)

    # Check for identity-specific markers
    identity_markers = ["evolution", "self-development", "growth"]
    modulated_lower = modulated.lower()

    has_identity_markers = any(marker in modulated_lower for marker in identity_markers)
    assert has_identity_markers, \
        f"Expected identity markers in LAM tone, got: {modulated}"


def test_lam_deep_context_arc_markers(llm_renderer, sample_text):
    """Test that LAM profile with deep_context arc uses contextual markers."""
    # Create LAM profile with deep_context arc
    lam_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="deep_context",
        detail_bias=0.5,
        practical_bias=0.3,
        reflective_bias=0.8
    )

    # Apply mapper tone
    modulated = llm_renderer.apply_mapper_tone(sample_text, lam_profile)

    # Check for deep context markers
    context_markers = ["broader context", "patterns", "framework"]
    modulated_lower = modulated.lower()

    has_context_markers = any(marker in modulated_lower for marker in context_markers)
    assert has_context_markers, \
        f"Expected context markers in LAM tone, got: {modulated}"


def test_no_profile_returns_unchanged(llm_renderer, sample_text):
    """Test that None profile returns text unchanged."""
    modulated = llm_renderer.apply_mapper_tone(sample_text, None)

    assert modulated == sample_text


def test_neutral_profile_returns_unchanged(llm_renderer, sample_text):
    """Test that neutral profile returns text unchanged."""
    # Create neutral profile (doesn't match any conditions)
    neutral_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="none",
        detail_bias=0.5,
        practical_bias=0.5,
        reflective_bias=0.5
    )

    # Apply mapper tone
    modulated = llm_renderer.apply_mapper_tone(sample_text, neutral_profile)

    assert modulated == sample_text


def test_lcm_preserves_main_meaning(llm_renderer):
    """Test that LCM tone preserves main meaning despite shortening."""
    text = "The project requires immediate attention due to budget constraints."

    lcm_profile = MapperProfile(
        resolution_level="low",
        arc_mode="none",
        detail_bias=0.2,
        practical_bias=0.9,
        reflective_bias=0.2
    )

    modulated = llm_renderer.apply_mapper_tone(text, lcm_profile)

    # Should still contain key concepts
    assert "project" in modulated.lower() or "immediate" in modulated.lower()


def test_hrm_preserves_all_content(llm_renderer):
    """Test that HRM tone preserves all original content."""
    text = "Point one. Point two. Point three."

    hrm_profile = MapperProfile(
        resolution_level="high",
        arc_mode="none",
        detail_bias=0.8,
        practical_bias=0.3,
        reflective_bias=0.6
    )

    modulated = llm_renderer.apply_mapper_tone(text, hrm_profile)

    # All points should still be present
    # (transitions may be added, but content preserved)
    original_sentences = [s.strip() for s in text.split('.') if s.strip()]
    modulated_sentences = [s.strip() for s in modulated.split('.') if s.strip()]

    # Should have same or more sentences (due to transitions)
    assert len(modulated_sentences) >= len(original_sentences)


def test_lam_maintains_semantic_content(llm_renderer):
    """Test that LAM tone maintains semantic content while adding framing."""
    text = "The analysis reveals important patterns."

    lam_profile = MapperProfile(
        resolution_level="medium",
        arc_mode="temporal",
        detail_bias=0.5,
        practical_bias=0.3,
        reflective_bias=0.8
    )

    modulated = llm_renderer.apply_mapper_tone(text, lam_profile)

    # Core content should still be present
    assert "analysis" in modulated.lower() or "patterns" in modulated.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
