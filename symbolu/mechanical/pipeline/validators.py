"""
Symbol-U Pipeline Validators (v3.0)

Lightweight validation utilities for pipeline stage outputs.

Each validator checks that a required stage output exists and is properly
populated in the PipelineContext. These are defensive checks to catch
integration issues early, not schema validation frameworks.

Usage:
    from mechanical.pipeline.validators import validate_request, ensure_persona

    validate_request(request)  # Raises ValueError if invalid
    ensure_persona(ctx)        # Raises ValueError if persona not resolved
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import PipelineContext, UserRequest


def validate_request(request: "UserRequest") -> None:
    """
    Validate that a UserRequest is well-formed for pipeline processing.

    Checks:
        - request is not None
        - request.text is a non-empty string
        - render_mode (if set) is a recognized value

    Args:
        request: The UserRequest to validate.

    Raises:
        ValueError: If the request is invalid.
    """
    if request is None:
        raise ValueError("UserRequest cannot be None")

    if not request.text or not isinstance(request.text, str):
        raise ValueError("UserRequest.text must be a non-empty string")

    if request.text.strip() == "":
        raise ValueError("UserRequest.text cannot be whitespace-only")

    # Validate render_mode if provided
    valid_render_modes = {"minimal", "standard", "enhanced", "regulated", None}
    if request.render_mode is not None and request.render_mode not in valid_render_modes:
        raise ValueError(
            f"UserRequest.render_mode must be one of {valid_render_modes - {None}}, "
            f"got '{request.render_mode}'"
        )


def ensure_persona(ctx: "PipelineContext") -> None:
    """
    Ensure that persona has been resolved in the pipeline context.

    Checks:
        - ctx.persona is not None
        - ctx.persona.active_persona_id is a non-empty string

    Args:
        ctx: The PipelineContext to check.

    Raises:
        ValueError: If persona has not been resolved.
    """
    if ctx.persona is None:
        raise ValueError(
            "Pipeline stage 'persona' has not been executed. "
            "ctx.persona is None."
        )

    if not ctx.persona.active_persona_id:
        raise ValueError(
            "Pipeline stage 'persona' incomplete. "
            "ctx.persona.active_persona_id is empty."
        )


def ensure_mlcr(ctx: "PipelineContext") -> None:
    """
    Ensure that MLCR routing has been executed.

    Checks:
        - ctx.mlcr is not None
        - ctx.mlcr.entries contains data

    Args:
        ctx: The PipelineContext to check.

    Raises:
        ValueError: If MLCR has not been executed.
    """
    if ctx.mlcr is None:
        raise ValueError(
            "Pipeline stage 'mlcr' has not been executed. "
            "ctx.mlcr is None."
        )

    if ctx.mlcr.entries is None:
        raise ValueError(
            "Pipeline stage 'mlcr' incomplete. "
            "ctx.mlcr.entries is None."
        )


def ensure_fusion(ctx: "PipelineContext") -> None:
    """
    Ensure that Fusion has been executed.

    Checks:
        - ctx.fusion is not None
        - ctx.fusion.fused_candidates contains data

    Args:
        ctx: The PipelineContext to check.

    Raises:
        ValueError: If Fusion has not been executed.
    """
    if ctx.fusion is None:
        raise ValueError(
            "Pipeline stage 'fusion' has not been executed. "
            "ctx.fusion is None."
        )

    if ctx.fusion.fused_candidates is None:
        raise ValueError(
            "Pipeline stage 'fusion' incomplete. "
            "ctx.fusion.fused_candidates is None."
        )


def ensure_dha(ctx: "PipelineContext") -> None:
    """
    Ensure that DHA has been executed.

    Checks:
        - ctx.dha is not None
        - ctx.dha.guarded_text is populated
        - ctx.dha.tone_profile is set
        - ctx.dha.readiness_level is set

    Args:
        ctx: The PipelineContext to check.

    Raises:
        ValueError: If DHA has not been executed.
    """
    if ctx.dha is None:
        raise ValueError(
            "Pipeline stage 'dha' has not been executed. "
            "ctx.dha is None."
        )

    if not ctx.dha.tone_profile:
        raise ValueError(
            "Pipeline stage 'dha' incomplete. "
            "ctx.dha.tone_profile is empty."
        )

    if not ctx.dha.readiness_level:
        raise ValueError(
            "Pipeline stage 'dha' incomplete. "
            "ctx.dha.readiness_level is empty."
        )


def ensure_rendered(ctx: "PipelineContext") -> None:
    """
    Ensure that rendering has been executed.

    Checks:
        - ctx.rendered is not None
        - ctx.rendered.raw_text is populated
        - ctx.rendered.mode is set

    Args:
        ctx: The PipelineContext to check.

    Raises:
        ValueError: If rendering has not been executed.
    """
    if ctx.rendered is None:
        raise ValueError(
            "Pipeline stage 'rendered' has not been executed. "
            "ctx.rendered is None."
        )

    if ctx.rendered.raw_text is None:
        raise ValueError(
            "Pipeline stage 'rendered' incomplete. "
            "ctx.rendered.raw_text is None."
        )

    if not ctx.rendered.mode:
        raise ValueError(
            "Pipeline stage 'rendered' incomplete. "
            "ctx.rendered.mode is empty."
        )


def validate_stage_sequence(ctx: "PipelineContext", required_stage: str) -> None:
    """
    Validate that all prerequisite stages have been executed before a given stage.

    Stage sequence: persona -> mlcr -> fusion -> dha -> rendered

    Args:
        ctx: The PipelineContext to check.
        required_stage: The stage that needs its prerequisites validated.

    Raises:
        ValueError: If any prerequisite stage is missing.
    """
    stage_order = ["persona", "mlcr", "fusion", "dha", "rendered"]
    validators = {
        "persona": ensure_persona,
        "mlcr": ensure_mlcr,
        "fusion": ensure_fusion,
        "dha": ensure_dha,
        "rendered": ensure_rendered,
    }

    if required_stage not in stage_order:
        raise ValueError(f"Unknown stage: {required_stage}")

    stage_idx = stage_order.index(required_stage)

    # Check all stages before the required one
    for i in range(stage_idx):
        stage_name = stage_order[i]
        try:
            validators[stage_name](ctx)
        except ValueError as e:
            raise ValueError(
                f"Stage '{required_stage}' requires '{stage_name}' to be completed first. "
                f"Error: {e}"
            ) from e


# Public exports
__all__ = [
    "validate_request",
    "ensure_persona",
    "ensure_mlcr",
    "ensure_fusion",
    "ensure_dha",
    "ensure_rendered",
    "validate_stage_sequence",
]
