"""
Tests for LLM renderer.

Verifies:
- NoLLM renderer (always available)
- Template renderer (no LLM, natural output)
- Fallback chain behavior
- LLM is ONLY used for rendering, NOT inference

IMPORTANT: LLM rendering is OPTIONAL - the system works without any LLM.
"""

import pytest
from symbolu.orchestration.llm_renderer import (
    LLMProvider,
    RenderContext,
    RenderedOutput,
    NoLLMRenderer,
    TemplateRenderer,
    OutputRenderer,
    render_output,
)


class TestRenderContext:
    """Tests for RenderContext dataclass."""

    def test_minimal_context(self):
        """Create context with just sequences."""
        ctx = RenderContext(sequences=(("ka", "a"),))
        assert ctx.sequences == (("ka", "a"),)
        assert ctx.semantic_vector is None
        assert ctx.user_intent is None

    def test_full_context(self):
        """Create context with all fields."""
        ctx = RenderContext(
            sequences=(("ka", "a"), ("ba", "i")),
            semantic_vector={"energy": -0.5},
            user_intent="calm",
            metadata={"key": "value"},
        )
        assert len(ctx.sequences) == 2
        assert ctx.semantic_vector["energy"] == -0.5
        assert ctx.user_intent == "calm"


class TestRenderedOutput:
    """Tests for RenderedOutput dataclass."""

    def test_output_structure(self):
        """Output contains required fields."""
        output = RenderedOutput(
            text="Generated sequences",
            sequences=(("ka", "a"),),
        )
        assert output.text == "Generated sequences"
        assert output.sequences == (("ka", "a"),)
        assert output.raw_available is True
        assert output.llm_used is False
        assert output.provider == LLMProvider.NONE


class TestNoLLMRenderer:
    """Tests for NoLLMRenderer (fallback)."""

    def test_always_available(self):
        """NoLLM renderer is always available."""
        renderer = NoLLMRenderer()
        assert renderer.is_available()

    def test_render_basic(self):
        """Render basic sequences."""
        renderer = NoLLMRenderer()
        ctx = RenderContext(sequences=(("ka", "a"), ("ba", "i")))
        output = renderer.render(ctx)

        assert output.llm_used is False
        assert output.provider == LLMProvider.NONE
        assert "2 sequences" in output.text
        assert output.raw_available is True

    def test_render_with_intent(self):
        """Render includes user intent."""
        renderer = NoLLMRenderer()
        ctx = RenderContext(
            sequences=(("ka", "a"),),
            user_intent="something calm",
        )
        output = renderer.render(ctx)
        assert "calm" in output.text

    def test_render_with_semantic_vector(self):
        """Render includes semantic profile."""
        renderer = NoLLMRenderer()
        ctx = RenderContext(
            sequences=(("ka", "a"),),
            semantic_vector={"energy": -0.8, "duration": 0.0},
        )
        output = renderer.render(ctx)
        # Should show non-zero values
        assert "energy" in output.text

    def test_render_limits_display(self):
        """Render limits sequences displayed."""
        renderer = NoLLMRenderer()
        sequences = tuple(("ka", str(i)) for i in range(20))
        ctx = RenderContext(sequences=sequences)
        output = renderer.render(ctx)
        # Should mention "more"
        assert "more" in output.text

    def test_render_formats_sequences(self):
        """Sequences are formatted with arrows."""
        renderer = NoLLMRenderer()
        ctx = RenderContext(sequences=(("ka", "a", "ga"),))
        output = renderer.render(ctx)
        assert "→" in output.text


class TestTemplateRenderer:
    """Tests for TemplateRenderer (no LLM)."""

    def test_always_available(self):
        """Template renderer is always available."""
        renderer = TemplateRenderer()
        assert renderer.is_available()

    def test_render_basic(self):
        """Template render produces natural output."""
        renderer = TemplateRenderer()
        ctx = RenderContext(sequences=(("ka", "a"),))
        output = renderer.render(ctx)

        assert output.llm_used is False
        assert output.provider == LLMProvider.LOCAL
        assert len(output.text) > 0

    def test_render_low_energy(self):
        """Low energy uses calm templates."""
        renderer = TemplateRenderer()
        ctx = RenderContext(
            sequences=(("ka", "a"),),
            semantic_vector={"energy": -0.8},
        )
        output = renderer.render(ctx)
        # Should use calm-themed template
        text_lower = output.text.lower()
        assert any(word in text_lower for word in ["gentle", "calm", "soft", "peaceful"])

    def test_render_high_energy(self):
        """High energy uses energetic templates."""
        renderer = TemplateRenderer()
        ctx = RenderContext(
            sequences=(("ka", "a"),),
            semantic_vector={"energy": 0.8},
        )
        output = renderer.render(ctx)
        # Should use energetic-themed template
        text_lower = output.text.lower()
        assert any(word in text_lower for word in ["energetic", "vibrant", "dynamic", "energy"])

    def test_render_rising_direction(self):
        """Rising direction uses ascending templates."""
        renderer = TemplateRenderer()
        ctx = RenderContext(
            sequences=(("ka", "a"),),
            semantic_vector={"direction": 0.8},
        )
        output = renderer.render(ctx)
        text_lower = output.text.lower()
        assert any(word in text_lower for word in ["rising", "ascending", "building"])

    def test_render_falling_direction(self):
        """Falling direction uses descending templates."""
        renderer = TemplateRenderer()
        ctx = RenderContext(
            sequences=(("ka", "a"),),
            semantic_vector={"direction": -0.8},
        )
        output = renderer.render(ctx)
        text_lower = output.text.lower()
        assert any(word in text_lower for word in ["settling", "descending", "down"])

    def test_render_formats_sequences(self):
        """Sequences are formatted in output."""
        renderer = TemplateRenderer()
        ctx = RenderContext(sequences=(("ka", "a", "ga"),))
        output = renderer.render(ctx)
        assert "→" in output.text

    def test_render_limits_sequences(self):
        """Template limits displayed sequences."""
        renderer = TemplateRenderer()
        sequences = tuple(("ka", str(i)) for i in range(20))
        ctx = RenderContext(sequences=sequences)
        output = renderer.render(ctx)
        assert "more" in output.text


class TestOutputRenderer:
    """Tests for main OutputRenderer."""

    def test_default_no_llm(self):
        """Default renderer uses no LLM."""
        renderer = OutputRenderer()
        output = renderer.render(sequences=(("ka", "a"),))
        assert output.llm_used is False

    def test_prefer_none_provider(self):
        """Prefer NONE provider uses NoLLMRenderer."""
        renderer = OutputRenderer(preferred_provider=LLMProvider.NONE)
        output = renderer.render(sequences=(("ka", "a"),))
        assert output.provider == LLMProvider.NONE

    def test_prefer_local_provider(self):
        """Prefer LOCAL provider uses TemplateRenderer."""
        renderer = OutputRenderer(preferred_provider=LLMProvider.LOCAL)
        output = renderer.render(sequences=(("ka", "a"),))
        assert output.provider == LLMProvider.LOCAL

    def test_get_available_providers(self):
        """List available providers."""
        renderer = OutputRenderer()
        providers = renderer.get_available_providers()
        # At minimum, NONE and LOCAL are always available
        assert LLMProvider.NONE in providers
        assert LLMProvider.LOCAL in providers

    def test_render_with_semantic_vector(self):
        """Render accepts semantic vector."""
        renderer = OutputRenderer(preferred_provider=LLMProvider.LOCAL)
        output = renderer.render(
            sequences=(("ka", "a"),),
            semantic_vector={"energy": -0.5},
        )
        assert output.text is not None

    def test_render_with_user_intent(self):
        """Render accepts user intent."""
        renderer = OutputRenderer()
        output = renderer.render(
            sequences=(("ka", "a"),),
            user_intent="something calm",
        )
        assert output.text is not None

    def test_fallback_chain(self):
        """Renderer falls back through chain."""
        # Even with preferred Anthropic (unavailable without API key),
        # should fall back to LOCAL or NONE
        renderer = OutputRenderer(preferred_provider=LLMProvider.ANTHROPIC)
        output = renderer.render(sequences=(("ka", "a"),))
        # Should succeed with fallback
        assert output.text is not None
        # Provider should be fallback (not Anthropic)
        assert output.provider in [LLMProvider.LOCAL, LLMProvider.NONE]


class TestRenderOutputFunction:
    """Tests for render_output() convenience function."""

    def test_basic_render(self):
        """Basic rendering returns text."""
        text = render_output(sequences=(("ka", "a"),))
        assert isinstance(text, str)
        assert len(text) > 0

    def test_render_with_intent(self):
        """Render with user intent."""
        text = render_output(
            sequences=(("ka", "a"),),
            user_intent="calm",
        )
        assert isinstance(text, str)

    def test_render_without_llm(self):
        """Render without LLM (default)."""
        text = render_output(
            sequences=(("ka", "a"),),
            use_llm=False,
        )
        assert isinstance(text, str)

    def test_render_with_llm_flag(self):
        """Render with LLM flag (falls back if unavailable)."""
        # Even with use_llm=True, should succeed via fallback
        text = render_output(
            sequences=(("ka", "a"),),
            use_llm=True,
        )
        assert isinstance(text, str)


class TestNoLLMForInference:
    """
    Tests verifying LLM is NOT used for inference.

    CRITICAL: The architecture uses keyword-based inference ONLY.
    LLM is optional and ONLY for output presentation.
    """

    def test_renderer_does_not_parse_intent(self):
        """Renderer does not parse user intent - just displays it."""
        renderer = NoLLMRenderer()
        ctx = RenderContext(
            sequences=(("ka", "a"),),
            user_intent="calm gentle peaceful",
        )
        output = renderer.render(ctx)
        # Intent is displayed as-is, not interpreted
        assert "calm gentle peaceful" in output.text

    def test_renderer_does_not_generate_constraints(self):
        """Renderer does not generate mechanical constraints."""
        renderer = TemplateRenderer()
        ctx = RenderContext(
            sequences=(("ka", "a"),),
            semantic_vector={"energy": -0.8},
        )
        output = renderer.render(ctx)
        # Output is text only, no constraint data
        assert isinstance(output.text, str)
        # Renderer only receives pre-computed semantic vector
        # It doesn't compute it from text

    def test_renderer_receives_precomputed_data(self):
        """Renderer receives pre-computed data, doesn't compute."""
        renderer = OutputRenderer()
        # All data is pre-computed by keyword parser
        output = renderer.render(
            sequences=(("ka", "a"), ("ba", "i")),  # Pre-generated
            semantic_vector={"energy": -0.5},      # Pre-computed by IntentParser
            user_intent="calm",                    # Original text only
        )
        # Renderer just formats this data
        assert output.sequences == (("ka", "a"), ("ba", "i"))  # Unchanged
        assert output.raw_available is True

    def test_llm_used_flag_accuracy(self):
        """llm_used flag accurately reflects LLM usage."""
        # Without LLM API configured, should always be False
        renderer = OutputRenderer(preferred_provider=LLMProvider.NONE)
        output = renderer.render(sequences=(("ka", "a"),))
        assert output.llm_used is False

        renderer = OutputRenderer(preferred_provider=LLMProvider.LOCAL)
        output = renderer.render(sequences=(("ka", "a"),))
        assert output.llm_used is False  # Template is not LLM
