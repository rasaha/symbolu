import pytest

from .utils import run_pipeline_and_capture_context, MockLLMRenderer


class ExplodingLLMRenderer(MockLLMRenderer):
    """
    A mock renderer that MUST NOT be called.
    If any render() call occurs, the test should fail immediately.
    Used to verify that minimal render mode bypasses LLM entirely.
    """

    def render(self, *args, **kwargs):  # type: ignore[override]
        raise AssertionError(
            "LLM renderer should NOT be invoked in render_mode='minimal'"
        )


def test_renderer_minimal_mode_bypasses_llm():
    """
    In render_mode='minimal', the pipeline should not call the LLM renderer.
    """
    exploding = ExplodingLLMRenderer()

    rendered, ctx, _ = run_pipeline_and_capture_context(
        text="Renderer minimal-mode integration test.",
        routing_mode="auto",
        render_mode="minimal",
        llm_renderer=exploding,
    )

    # Should reach here with no errors
    assert rendered.text.strip() != ""
    assert ctx.renderer is not None


def test_renderer_standard_mode_uses_mock_llm():
    """
    In standard mode, the pipeline is allowed to call the renderer,
    so MockLLMRenderer.calls should be >= 1.
    This verifies:
    - No external LLM call
    - Renderer pipeline path is active
    """
    mock_llm = MockLLMRenderer()

    rendered, ctx, _ = run_pipeline_and_capture_context(
        text="Renderer standard-mode integration test.",
        routing_mode="auto",
        render_mode="standard",
        llm_renderer=mock_llm,
    )

    assert rendered.text.strip() != ""
    assert len(mock_llm.calls) >= 1, "Expected the mock LLM renderer to be called at least once"
