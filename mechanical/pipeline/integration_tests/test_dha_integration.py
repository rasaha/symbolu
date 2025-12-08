import pytest

from .utils import run_pipeline_and_capture_context


READYNESS_LEVELS = {"HIGH", "MEDIUM", "LOW"}


def _assert_dha_fields(dha):
    """
    Common structural assertions for DHA engine outputs.
    """
    readiness = getattr(dha, "readiness_level", None)
    assert readiness in READYNESS_LEVELS, (
        f"readiness_level must be one of {READYNESS_LEVELS}, got {readiness!r}"
    )

    tone_profile = getattr(dha, "tone_profile", "")
    assert isinstance(tone_profile, str), "tone_profile must be a string"
    assert tone_profile.strip() != "", "tone_profile must not be empty"

    resistance_flags = getattr(dha, "resistance_flags", None)
    assert resistance_flags is not None, "resistance_flags must exist"


def test_dha_for_calming_text():
    """
    DHA should populate fields properly for a neutral or calm input.
    """
    _, ctx, _ = run_pipeline_and_capture_context(
        text="I am feeling okay and would like some guidance.",
        routing_mode="auto",
        render_mode="minimal",
    )

    assert hasattr(ctx, "dha"), "PipelineContext must have a 'dha' section"
    _assert_dha_fields(ctx.dha)


def test_dha_for_distressed_text():
    """
    DHA should populate fields even for a highly distressed input.
    We do NOT assert the specific readiness level — only structural correctness.
    """
    _, ctx, _ = run_pipeline_and_capture_context(
        text="I feel deeply afraid and overwhelmed about everything.",
        routing_mode="auto",
        render_mode="minimal",
    )

    assert hasattr(ctx, "dha"), "PipelineContext must have a 'dha' section"
    _assert_dha_fields(ctx.dha)
