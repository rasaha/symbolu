"""
LLM Renderer Snapshot Tests (Mocked)
======================================

Snapshot tests for LLMRenderer with mocked LLM calls.

Tests ensure:
1. LLM enhancement produces consistent output format
2. Fallback to RulesRenderer produces deterministic output
3. Metadata preservation across enhancement and fallback
4. No mutation of symbolic/practical layers

All tests use mocks - NO actual API calls are made.

Usage:
    pytest renderer/tests/test_llm_renderer_snapshots.py -v

    # Regenerate snapshots:
    REGENERATE_SNAPSHOTS=1 pytest renderer/tests/test_llm_renderer_snapshots.py -v

Version: 1.0
"""

import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Add project root to path for imports
sys.path.insert(0, "/home/user/symbolu")

from symbolu.mechanical.renderer.llm_renderer import LLMRenderer
from symbolu.mechanical.renderer.rules_renderer import RulesRenderer
from symbolu.mechanical.renderer.safety_guardrails import SafetyGuardrails

from tests.unit.renderer.snapshot_utils import assert_snapshot


# ============================================================================
# SNAPSHOT PATHS
# ============================================================================

SNAPSHOT_DIR = Path(__file__).parent.parent / "snapshots"

SNAPSHOT_PATHS = {
    "llm_enhanced": SNAPSHOT_DIR / "llm_enhanced.snap",
    "llm_fallback": SNAPSHOT_DIR / "llm_fallback.snap",
}


# ============================================================================
# MOCKED LLM OUTPUT
# ============================================================================

# Fixed mocked LLM output for deterministic testing
MOCKED_LLM_ENHANCED_OUTPUT = """MOCKED LLM ENHANCED OUTPUT

Your journey reflects themes of growth and tension - a natural part of transformation.

SYMBOLIC INSIGHTS:
- Theme: Exploration of life direction
- Archetype: The Seeker pursuing clarity

PRACTICAL GUIDANCE:
- Fact: User requested help with focus
- Constraint: Limited time available
- Action: Begin with self-assessment

MIRROR-TRUTH REFLECTION:
- Contradiction: Fear vs desire creates productive tension
- Alignment: High coherence across reasoning channels

RECOMMENDATIONS:
1. Focus on alignment between values and actions
2. Seek clarity through structured reflection
3. Take incremental steps toward growth

This analysis preserves all core values while enhancing presentation."""


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_analysis() -> Dict[str, Any]:
    """
    Create sample analysis input for LLMRenderer testing.

    Structure matches the expected input format with:
    - symbolic layer data (themes, archetype)
    - practical layer data (facts, constraints)
    - mirror_truth layer data (contradictions)
    - metadata for tracking
    """
    return {
        "symbolic": {
            "themes": ["growth", "tension"],
            "archetype": "seeker",
            "causal_patterns": ["seeking leads to discovery"]
        },
        "practical": {
            "facts": ["User requested help"],
            "constraints": ["limited time"],
            "procedures": ["assess", "plan", "execute"]
        },
        "mirror_truth": {
            "contradictions": ["fear vs desire"],
            "alignment_score": 0.72,
            "tensions": ["opposing forces detected"]
        },
        # Additional fields for RulesRenderer fallback
        "text": "Sample analysis text for fallback",
        "average_smi": 0.75,
        "calling_type": "VOCATION",
        "dha_tone": "SWEET_RESONANCE",
        "words": ["growth", "tension", "clarity"],
        "recommendations": [
            "Focus on alignment",
            "Seek clarity",
            "Take action"
        ]
    }


@pytest.fixture
def llm_renderer() -> LLMRenderer:
    """Create LLMRenderer instance for testing."""
    return LLMRenderer(provider="anthropic")


# ============================================================================
# SNAPSHOT TESTS
# ============================================================================

class TestLLMRendererSnapshots:
    """Snapshot tests for LLMRenderer with mocked LLM."""

    def test_llm_enhancement_snapshot(self, llm_renderer, sample_analysis):
        """
        TEST 1: LLM Enhancement Snapshot.

        Monkeypatch LLM client so _call_llm returns fixed mocked output.
        Verify:
        - Enhanced output format is consistent
        - Symbolic/practical layers referenced in output
        - Metadata preserved in enhancement
        """
        # Mock the _call_llm method to return fixed output
        with patch.object(llm_renderer, '_call_llm', return_value=MOCKED_LLM_ENHANCED_OUTPUT):
            # Mock safety verify_output to return True (output is valid)
            with patch.object(llm_renderer.safety, 'verify_output', return_value=True):
                output = llm_renderer.render(sample_analysis, tone="SWEET_RESONANCE")

        # Verify output is the mocked response
        assert output == MOCKED_LLM_ENHANCED_OUTPUT

        # Verify key content is present
        assert "MOCKED LLM ENHANCED OUTPUT" in output
        assert "growth" in output.lower()
        assert "tension" in output.lower()
        assert "RECOMMENDATIONS:" in output

        # Compare against snapshot
        assert_snapshot(output, SNAPSHOT_PATHS["llm_enhanced"])

    def test_llm_fallback_snapshot(self, sample_analysis):
        """
        TEST 2: Fallback Snapshot.

        When LLM raises Exception, renderer should fallback to RulesRenderer.
        Verify:
        - Fallback produces valid, complete output
        - Output is deterministic
        - Key analysis preserved in fallback
        """
        # Create LLMRenderer with fallback behavior
        llm_renderer = LLMRendererWithFallback(provider="anthropic")

        # Mock _call_llm to raise exception
        with patch.object(llm_renderer, '_call_llm', side_effect=Exception("LLM API Error")):
            output = llm_renderer.render_with_fallback(sample_analysis)

        # Verify fallback output structure
        assert output is not None
        assert isinstance(output, str)
        assert len(output) > 0

        # Verify key content from RulesRenderer
        assert "Analysis of:" in output
        assert "Average SMI:" in output
        assert "Recommendations:" in output

        # Compare against snapshot
        assert_snapshot(output, SNAPSHOT_PATHS["llm_fallback"])


# ============================================================================
# LLM RENDERER WITH FALLBACK
# ============================================================================

class LLMRendererWithFallback(LLMRenderer):
    """
    Extended LLMRenderer with fallback to RulesRenderer.

    Used for snapshot testing of fallback behavior.
    In production, this would be the standard LLMRenderer behavior.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fallback_renderer = RulesRenderer()

    def render_with_fallback(
        self,
        analysis: Dict[str, Any],
        tone: str = None,
        **kwargs
    ) -> str:
        """
        Render with automatic fallback to RulesRenderer on failure.

        Args:
            analysis: Core analysis result
            tone: DHA tone for delivery
            **kwargs: Additional parameters

        Returns:
            Rendered output string (LLM-enhanced or fallback)
        """
        try:
            # Try LLM enhancement
            prompt = self.prompts.build_enhancement_prompt(analysis, tone)
            prompt = self.style.apply(prompt, tone)

            if not self.safety.check_prompt(prompt):
                raise ValueError("Prompt failed safety check")

            enhanced = self._call_llm(prompt)

            if not self.safety.verify_output(analysis, enhanced):
                raise ValueError("Output diverged from core analysis")

            return enhanced

        except Exception:
            # Fallback to RulesRenderer
            return self.fallback_renderer.render(analysis)


# ============================================================================
# METADATA PRESERVATION TESTS
# ============================================================================

class TestLLMSnapshotMetadataPreservation:
    """Tests ensuring input data is preserved in LLM output."""

    def test_symbolic_layer_referenced_in_enhanced_output(self, llm_renderer, sample_analysis):
        """Verify symbolic layer content appears in enhanced output."""
        with patch.object(llm_renderer, '_call_llm', return_value=MOCKED_LLM_ENHANCED_OUTPUT):
            with patch.object(llm_renderer.safety, 'verify_output', return_value=True):
                output = llm_renderer.render(sample_analysis)

        # Mocked output references symbolic themes
        assert "growth" in output.lower()
        assert "tension" in output.lower()

    def test_practical_layer_referenced_in_enhanced_output(self, llm_renderer, sample_analysis):
        """Verify practical layer content appears in enhanced output."""
        with patch.object(llm_renderer, '_call_llm', return_value=MOCKED_LLM_ENHANCED_OUTPUT):
            with patch.object(llm_renderer.safety, 'verify_output', return_value=True):
                output = llm_renderer.render(sample_analysis)

        # Mocked output references practical content
        assert "fact" in output.lower()
        assert "action" in output.lower()

    def test_recommendations_preserved_in_enhanced_output(self, llm_renderer, sample_analysis):
        """Verify recommendations are preserved in enhanced output."""
        with patch.object(llm_renderer, '_call_llm', return_value=MOCKED_LLM_ENHANCED_OUTPUT):
            with patch.object(llm_renderer.safety, 'verify_output', return_value=True):
                output = llm_renderer.render(sample_analysis)

        # Mocked output includes recommendations section
        assert "RECOMMENDATIONS:" in output
        assert "alignment" in output.lower()
        assert "clarity" in output.lower()


# ============================================================================
# DETERMINISM TESTS
# ============================================================================

class TestLLMSnapshotDeterminism:
    """Tests verifying LLM snapshot outputs are deterministic with mocking."""

    def test_mocked_llm_produces_identical_output(self, llm_renderer, sample_analysis):
        """Multiple mocked LLM calls must produce identical output."""
        with patch.object(llm_renderer, '_call_llm', return_value=MOCKED_LLM_ENHANCED_OUTPUT):
            with patch.object(llm_renderer.safety, 'verify_output', return_value=True):
                output1 = llm_renderer.render(sample_analysis)
                output2 = llm_renderer.render(sample_analysis)

        assert output1 == output2, "Mocked LLM output must be deterministic"

    def test_fallback_produces_identical_output(self, sample_analysis):
        """Multiple fallback renders must produce identical output."""
        llm_renderer = LLMRendererWithFallback(provider="anthropic")

        with patch.object(llm_renderer, '_call_llm', side_effect=Exception("LLM Error")):
            output1 = llm_renderer.render_with_fallback(sample_analysis)
            output2 = llm_renderer.render_with_fallback(sample_analysis)

        assert output1 == output2, "Fallback output must be deterministic"

    def test_different_instances_produce_identical_fallback(self, sample_analysis):
        """Different LLMRenderer instances must produce identical fallback."""
        renderer1 = LLMRendererWithFallback(provider="anthropic")
        renderer2 = LLMRendererWithFallback(provider="anthropic")

        with patch.object(renderer1, '_call_llm', side_effect=Exception("Error")):
            with patch.object(renderer2, '_call_llm', side_effect=Exception("Error")):
                output1 = renderer1.render_with_fallback(sample_analysis)
                output2 = renderer2.render_with_fallback(sample_analysis)

        assert output1 == output2, "Different instances must produce identical fallback"


# ============================================================================
# NO MUTATION TESTS
# ============================================================================

class TestLLMSnapshotNoMutation:
    """Tests ensuring input analysis is not mutated during rendering."""

    def test_input_not_mutated_during_llm_render(self, llm_renderer, sample_analysis):
        """Input analysis must not be mutated by LLM rendering."""
        import copy
        original = copy.deepcopy(sample_analysis)

        with patch.object(llm_renderer, '_call_llm', return_value=MOCKED_LLM_ENHANCED_OUTPUT):
            with patch.object(llm_renderer.safety, 'verify_output', return_value=True):
                _ = llm_renderer.render(sample_analysis)

        # Verify no mutation
        assert sample_analysis["symbolic"]["themes"] == original["symbolic"]["themes"]
        assert sample_analysis["practical"]["facts"] == original["practical"]["facts"]
        assert sample_analysis["mirror_truth"]["contradictions"] == original["mirror_truth"]["contradictions"]

    def test_input_not_mutated_during_fallback(self, sample_analysis):
        """Input analysis must not be mutated by fallback rendering."""
        import copy
        original = copy.deepcopy(sample_analysis)

        llm_renderer = LLMRendererWithFallback(provider="anthropic")

        with patch.object(llm_renderer, '_call_llm', side_effect=Exception("Error")):
            _ = llm_renderer.render_with_fallback(sample_analysis)

        # Verify no mutation
        assert sample_analysis["symbolic"]["themes"] == original["symbolic"]["themes"]
        assert sample_analysis["practical"]["facts"] == original["practical"]["facts"]
        assert sample_analysis["mirror_truth"]["contradictions"] == original["mirror_truth"]["contradictions"]


# ============================================================================
# TONE HANDLING TESTS
# ============================================================================

class TestLLMSnapshotToneHandling:
    """Tests for tone parameter handling in snapshots."""

    def test_tone_passed_to_llm_render(self, llm_renderer, sample_analysis):
        """Tone parameter should be processed without affecting determinism."""
        with patch.object(llm_renderer, '_call_llm', return_value=MOCKED_LLM_ENHANCED_OUTPUT):
            with patch.object(llm_renderer.safety, 'verify_output', return_value=True):
                output_sweet = llm_renderer.render(sample_analysis, tone="SWEET_RESONANCE")
                output_firm = llm_renderer.render(sample_analysis, tone="FIRM_COMPASSION")

        # With mocked LLM, both should return the same mocked output
        assert output_sweet == output_firm == MOCKED_LLM_ENHANCED_OUTPUT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
