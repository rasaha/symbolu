"""
P31 Output Envelope Phase
============================

Wrap final output in appropriate envelope format for delivery.
Integrates existing modules:

- DeliveryModulator: Profile-based message wrapping
- SafetyFilters: Final safety gating
- FusionRenderer: 3-layer structure formatting

Phase Authority: LOW
Band Position: P31 (Final in Delivery Adaptation Band)

Purpose:
    - Output structure formatting (plain/markdown/JSON/HTML/SSML)
    - Metadata attachment with pipeline trace
    - Delivery channel adaptation (chat/API/voice/email)
    - Final safety filtering

Usage:
    from symbolu.mechanical.pipeline.p31_envelope import (
        maybe_run_p31,
        get_p31_output,
        get_final_output,
    )

    # In orchestrator (after P30)
    p31_result = maybe_run_p31(ctx)
    if p31_result:
        ctx.p31_envelope = p31_result
"""

from .p31_envelope_schema import (
    VERSION,
    P31Authority,
    EnvelopeFormat,
    DeliveryChannel,
    P31Metadata,
    P31Output,
)

from .p31_integration import (
    get_delivery_modulator,
    get_safety_filters,
    extract_metadata,
    detect_format,
    detect_channel,
    format_envelope,
    apply_final_safety,
    run_p31_envelope,
    maybe_run_p31,
    get_p31_output,
    get_final_output,
    HAS_DELIVERY_MODULATOR,
    HAS_FUSION_RENDERER,
    HAS_SAFETY_FILTERS,
)

PHASE_STATUS = "implemented"

__version__ = VERSION
__all__ = [
    # Schema
    "VERSION",
    "P31Authority",
    "EnvelopeFormat",
    "DeliveryChannel",
    "P31Metadata",
    "P31Output",
    # Integration
    "get_delivery_modulator",
    "get_safety_filters",
    "extract_metadata",
    "detect_format",
    "detect_channel",
    "format_envelope",
    "apply_final_safety",
    "run_p31_envelope",
    "maybe_run_p31",
    "get_p31_output",
    "get_final_output",
    # Feature flags
    "HAS_DELIVERY_MODULATOR",
    "HAS_FUSION_RENDERER",
    "HAS_SAFETY_FILTERS",
    "PHASE_STATUS",
]
