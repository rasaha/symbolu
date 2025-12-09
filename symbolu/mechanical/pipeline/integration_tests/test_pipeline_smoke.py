import pytest

from .utils import run_pipeline_and_capture_context


def test_pipeline_smoke_minimal_mode():
    """
    Basic smoke test:

    - Pipeline executes end-to-end without exceptions.
    - PipelineContext exists and contains persona, mlcr, fusion, dha, renderer.
    - RenderedOutput.text is non-empty.
    """
    rendered, ctx, _ = run_pipeline_and_capture_context(
        text="sample text for smoke test",
        routing_mode="auto",
        render_mode="minimal",
    )

    # Final output must contain text
    assert hasattr(rendered, "text")
    assert isinstance(rendered.text, str)
    assert rendered.text.strip() != ""

    # Validate context structure
    for field in ("persona", "mlcr", "fusion", "dha", "renderer"):
        assert hasattr(ctx, field), f"Missing context field: {field}"
        value = getattr(ctx, field)
        assert value is not None, f"Context field {field} should not be None"


def test_pipeline_smoke_handles_varied_inputs():
    """
    Stability test with a different input to ensure no hardcoding.
    """
    rendered, ctx, _ = run_pipeline_and_capture_context(
        text="I feel a bit stuck but hopeful.",
        routing_mode="auto",
        render_mode="minimal",
    )

    assert rendered.text.strip() != ""
    assert ctx.dha is not None
    assert ctx.fusion is not None
