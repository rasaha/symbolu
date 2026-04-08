import pytest

from .utils import run_pipeline_and_capture_context


READYNESS_LEVELS = {"HIGH", "MEDIUM", "LOW"}


def test_full_flow_linear_routing_and_dha_fields():
    """
    Full-flow integration test focusing on:

    - routing_mode = "linear"
    - DHA fields: readiness_level, tone_profile, resistance_flags
    - FusionEngine: fused_candidates must not be empty
    - Final output text must be non-empty
    """
    rendered, ctx, _ = run_pipeline_and_capture_context(
        text="I am overwhelmed and need gentle guidance.",
        routing_mode="linear",
        render_mode="minimal",
    )

    # Rendered output must contain text
    assert hasattr(rendered, "text")
    assert isinstance(rendered.text, str)
    assert rendered.text.strip() != ""

    # ========== DHA CHECKS ==========
    assert hasattr(ctx, "dha"), "PipelineContext must contain a 'dha' section"
    dha_ctx = ctx.dha

    readiness = getattr(dha_ctx, "readiness_level", None)
    assert readiness in READYNESS_LEVELS, (
        f"readiness_level should be one of {READYNESS_LEVELS}, got {readiness!r}"
    )

    tone_profile = getattr(dha_ctx, "tone_profile", "")
    assert isinstance(tone_profile, str)
    assert tone_profile.strip() != "", "DHA.tone_profile must be non-empty"

    resistance_flags = getattr(dha_ctx, "resistance_flags", None)
    assert resistance_flags is not None, "DHA.resistance_flags must exist"

    # ========== FUSION CHECKS ==========
    assert hasattr(ctx, "fusion"), "PipelineContext must contain 'fusion'"
    fusion_ctx = ctx.fusion

    fused_candidates = getattr(fusion_ctx, "fused_candidates", None)
    assert fused_candidates is not None, "fusion.fused_candidates must exist"
    assert len(fused_candidates) > 0, "fusion.fused_candidates must not be empty"


def test_full_flow_multiple_runs_share_no_state_leak():
    """
    Test that two consecutive pipeline runs do not leak state.

    We only check:
    - both runs succeed
    - they produce non-empty rendered text
    - contexts are distinct instances
    """
    rendered1, ctx1, _ = run_pipeline_and_capture_context(
        text="First request: I feel stuck.",
        routing_mode="linear",
        render_mode="minimal",
    )

    rendered2, ctx2, _ = run_pipeline_and_capture_context(
        text="Second request: I feel more hopeful now.",
        routing_mode="linear",
        render_mode="minimal",
    )

    assert rendered1.text.strip() != ""
    assert rendered2.text.strip() != ""

    # Contexts must not be the same object
    assert ctx1 is not ctx2
