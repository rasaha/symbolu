"""
P31 Output Envelope Phase Integration
=======================================

Integration shim for running P31 Output Envelope phase within
the Symbol-U pipeline orchestrator.

Integrates existing modules:
- DeliveryModulator: Profile-based message wrapping
- FusionRenderer: 3-layer structure formatting
- SafetyFilters: Final safety gating

Usage in orchestrator:
    from .p31_envelope import maybe_run_p31, get_p31_output

    # After P30 Verification
    p31_result = maybe_run_p31(ctx)
    if p31_result:
        ctx.p31_envelope = p31_result
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .p31_envelope_schema import (
    VERSION,
    P31Authority,
    EnvelopeFormat,
    DeliveryChannel,
    P31Metadata,
    P31Output,
)

if TYPE_CHECKING:
    from symbolu.mechanical.pipeline.models import PipelineContext


# =============================================================================
# OPTIONAL IMPORTS (graceful degradation)
# =============================================================================

# Try to import delivery modulator
try:
    from symbolu.mechanical.dha.delivery_modulator import DeliveryModulator
    HAS_DELIVERY_MODULATOR = True
except ImportError:
    HAS_DELIVERY_MODULATOR = False
    DeliveryModulator = None

# Try to import fusion renderer
try:
    from symbolu.mechanical.renderer.fusion_renderer import FusionRenderer
    HAS_FUSION_RENDERER = True
except ImportError:
    HAS_FUSION_RENDERER = False
    FusionRenderer = None

# Try to import safety filters
try:
    from symbolu.mechanical.dha.safety_filters import SafetyFilters
    HAS_SAFETY_FILTERS = True
except ImportError:
    HAS_SAFETY_FILTERS = False
    SafetyFilters = None


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_delivery_modulator: Optional[Any] = None
_safety_filters: Optional[Any] = None


def get_delivery_modulator() -> Optional[Any]:
    """Get or create singleton DeliveryModulator instance."""
    global _delivery_modulator
    if not HAS_DELIVERY_MODULATOR:
        return None
    if _delivery_modulator is None:
        _delivery_modulator = DeliveryModulator()
    return _delivery_modulator


def get_safety_filters() -> Optional[Any]:
    """Get or create singleton SafetyFilters instance."""
    global _safety_filters
    if not HAS_SAFETY_FILTERS:
        return None
    if _safety_filters is None:
        _safety_filters = SafetyFilters()
    return _safety_filters


# =============================================================================
# METADATA EXTRACTION
# =============================================================================


def extract_metadata(ctx: "PipelineContext") -> P31Metadata:
    """
    Extract metadata from pipeline context.

    Args:
        ctx: Pipeline context with phase outputs.

    Returns:
        P31Metadata with pipeline trace.
    """
    phases_executed: List[str] = []
    persona_id = None
    delivery_profile = None
    verification_passed = True
    custom: Dict[str, Any] = {}

    # Track executed phases
    if hasattr(ctx, 'mlcr') and ctx.mlcr:
        phases_executed.append("MLCR")
    if hasattr(ctx, 'hrm_map') and ctx.hrm_map:
        phases_executed.append("HRM")
    if hasattr(ctx, 'lam_map') and ctx.lam_map:
        phases_executed.append("LAM")
    if hasattr(ctx, 'lcm_map') and ctx.lcm_map:
        phases_executed.append("LCM")
    if hasattr(ctx, 'fusion') and ctx.fusion:
        phases_executed.append("Fusion")
    if hasattr(ctx, 'p27_persona') and ctx.p27_persona:
        phases_executed.append("P27")
        persona_id = ctx.p27_persona.persona_id
    if hasattr(ctx, 'p28_dha') and ctx.p28_dha:
        phases_executed.append("P28")
        delivery_profile = ctx.p28_dha.tone_profile.profile_type.value
    if hasattr(ctx, 'p29_expression') and ctx.p29_expression:
        phases_executed.append("P29")
    if hasattr(ctx, 'p30_verification') and ctx.p30_verification:
        phases_executed.append("P30")
        from symbolu.mechanical.pipeline.p30_verification import VerificationStatus
        verification_passed = ctx.p30_verification.verification_status in (
            VerificationStatus.PASSED,
            VerificationStatus.PASSED_WITH_WARNINGS,
        )

    # Add MLCR metadata if available
    if hasattr(ctx, 'mlcr') and ctx.mlcr:
        explain_log = getattr(ctx.mlcr, 'explain_log', {})
        if isinstance(explain_log, dict):
            meta = explain_log.get("meta", {})
            custom["tier"] = meta.get("tier")
            custom["intent"] = meta.get("intent")
            custom["domain"] = meta.get("domain")

    return P31Metadata(
        pipeline_version="3.1",
        phases_executed=phases_executed,
        persona_id=persona_id,
        delivery_profile=delivery_profile,
        verification_passed=verification_passed,
        render_timestamp=datetime.now().timestamp(),
        custom=custom,
    )


# =============================================================================
# FORMAT DETECTION
# =============================================================================


def detect_format(ctx: "PipelineContext") -> EnvelopeFormat:
    """
    Detect appropriate output format from context.

    Args:
        ctx: Pipeline context.

    Returns:
        EnvelopeFormat based on request or defaults.
    """
    # Check request metadata for format preference
    if hasattr(ctx, 'request') and ctx.request:
        metadata = getattr(ctx.request, 'metadata', {})
        if isinstance(metadata, dict):
            format_pref = metadata.get("output_format", "plain")
            format_map = {
                "plain": EnvelopeFormat.PLAIN,
                "markdown": EnvelopeFormat.MARKDOWN,
                "json": EnvelopeFormat.JSON,
                "html": EnvelopeFormat.HTML,
                "ssml": EnvelopeFormat.SSML,
            }
            return format_map.get(format_pref, EnvelopeFormat.PLAIN)

    return EnvelopeFormat.PLAIN


def detect_channel(ctx: "PipelineContext") -> DeliveryChannel:
    """
    Detect delivery channel from context.

    Args:
        ctx: Pipeline context.

    Returns:
        DeliveryChannel based on request or defaults.
    """
    # Check request metadata for channel preference
    if hasattr(ctx, 'request') and ctx.request:
        metadata = getattr(ctx.request, 'metadata', {})
        if isinstance(metadata, dict):
            channel_pref = metadata.get("delivery_channel", "chat")
            channel_map = {
                "chat": DeliveryChannel.CHAT,
                "api": DeliveryChannel.API,
                "voice": DeliveryChannel.VOICE,
                "email": DeliveryChannel.EMAIL,
                "report": DeliveryChannel.REPORT,
            }
            return channel_map.get(channel_pref, DeliveryChannel.CHAT)

    return DeliveryChannel.CHAT


# =============================================================================
# ENVELOPE FORMATTING
# =============================================================================


def format_envelope(
    text: str,
    envelope_format: EnvelopeFormat,
    metadata: P31Metadata,
) -> str:
    """
    Format text according to envelope format.

    Args:
        text: Text to format.
        envelope_format: Target format.
        metadata: Metadata to include.

    Returns:
        Formatted text.
    """
    if envelope_format == EnvelopeFormat.PLAIN:
        return text

    elif envelope_format == EnvelopeFormat.MARKDOWN:
        # Add metadata as markdown header comment
        return text  # Keep plain for now

    elif envelope_format == EnvelopeFormat.JSON:
        import json
        return json.dumps({
            "text": text,
            "metadata": metadata.to_dict(),
        }, indent=2)

    elif envelope_format == EnvelopeFormat.HTML:
        return f"<div class='symbolu-response'><p>{text}</p></div>"

    elif envelope_format == EnvelopeFormat.SSML:
        # Basic SSML wrapping
        return f"<speak>{text}</speak>"

    return text


# =============================================================================
# FINAL SAFETY CHECK
# =============================================================================


def apply_final_safety(text: str) -> tuple[str, bool]:
    """
    Apply final safety filters.

    Args:
        text: Text to filter.

    Returns:
        Tuple of (filtered_text, was_modified).
    """
    if not HAS_SAFETY_FILTERS:
        return text, False

    try:
        filters = get_safety_filters()
        if filters:
            result = filters.filter_text(text)
            filtered = getattr(result, 'filtered_text', text)
            return filtered, (filtered != text)
    except Exception:
        pass

    return text, False


# =============================================================================
# MAIN INTEGRATION
# =============================================================================


def run_p31_envelope(
    text: str,
    ctx: "PipelineContext",
) -> P31Output:
    """
    Run P31 output envelope phase.

    Args:
        text: Text to envelope.
        ctx: Pipeline context.

    Returns:
        P31Output with enveloped text.
    """
    trace: List[str] = []

    # Extract metadata
    trace.append("Extracting pipeline metadata")
    metadata = extract_metadata(ctx)
    trace.append(f"Phases executed: {len(metadata.phases_executed)}")

    # Detect format and channel
    envelope_format = detect_format(ctx)
    delivery_channel = detect_channel(ctx)
    trace.append(f"Format: {envelope_format.value}, Channel: {delivery_channel.value}")

    # Apply final safety check
    envelope_text = text
    if HAS_SAFETY_FILTERS:
        trace.append("Applying final safety filter")
        envelope_text, was_modified = apply_final_safety(text)
        if was_modified:
            trace.append("Safety filter applied modifications")

    # Format envelope
    trace.append(f"Formatting as {envelope_format.value}")
    envelope_text = format_envelope(envelope_text, envelope_format, metadata)

    return P31Output(
        envelope_text=envelope_text,
        envelope_format=envelope_format,
        delivery_channel=delivery_channel,
        authority=P31Authority.LOW,
        metadata=metadata,
        processing_trace=trace,
    )


def maybe_run_p31(ctx: "PipelineContext") -> Optional[P31Output]:
    """
    Conditionally run P31 output envelope phase.

    This is the main integration function to call from the pipeline orchestrator.

    Args:
        ctx: Pipeline context with P30 result.

    Returns:
        P31Output if phase executed, None otherwise.
    """
    # Get input text from P30 or fallback
    text = ""
    if hasattr(ctx, 'p30_verification') and ctx.p30_verification:
        text = ctx.p30_verification.verified_text
    elif hasattr(ctx, 'p29_expression') and ctx.p29_expression:
        text = ctx.p29_expression.final_text
    elif hasattr(ctx, 'p28_dha') and ctx.p28_dha:
        text = ctx.p28_dha.guarded_text
    elif hasattr(ctx, 'dha') and ctx.dha:
        text = getattr(ctx.dha, 'guarded_text', "")

    if not text:
        return None

    # Run envelope
    return run_p31_envelope(text, ctx)


def get_p31_output(ctx: "PipelineContext") -> Optional[P31Output]:
    """
    Get P31 output from context if available.

    Args:
        ctx: Pipeline context.

    Returns:
        P31Output if available, None otherwise.
    """
    if hasattr(ctx, 'p31_envelope'):
        return ctx.p31_envelope
    return None


def get_final_output(ctx: "PipelineContext") -> str:
    """
    Get final output text from P31 or fallback.

    Args:
        ctx: Pipeline context.

    Returns:
        Final output text.
    """
    output = get_p31_output(ctx)
    if output:
        return output.envelope_text

    # Fallback chain
    if hasattr(ctx, 'p30_verification') and ctx.p30_verification:
        return ctx.p30_verification.verified_text
    if hasattr(ctx, 'p29_expression') and ctx.p29_expression:
        return ctx.p29_expression.final_text
    if hasattr(ctx, 'p28_dha') and ctx.p28_dha:
        return ctx.p28_dha.guarded_text

    return ""


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
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
    "HAS_DELIVERY_MODULATOR",
    "HAS_FUSION_RENDERER",
    "HAS_SAFETY_FILTERS",
    "VERSION",
]
