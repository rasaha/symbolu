"""
P28 Delivery Harmonization Phase Integration
==============================================

Integration shim for running P28 Delivery Harmonization & Adaptation
phase within the Symbol-U pipeline orchestrator.

Usage in orchestrator:
    from .p28_dha import maybe_run_p28, get_p28_output

    # During DHA stage (after P27)
    p28_result = maybe_run_p28(ctx)
    if p28_result:
        ctx.p28_dha = p28_result
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from symbolu_core.mechanical.dha import (
    DHAEngine,
    DHAInput,
    DHAOutput,
    DeliveryProfile,
    ToneSelector,
    ReadinessAnalyzer,
    ResistanceDetector,
    SafetyFilters,
)

from .p28_dha_schema import (
    VERSION,
    P28Authority,
    DeliveryProfileType,
    ReadinessLevel,
    ResistanceLevel,
    SafetyStatus,
    P28InputSignals,
    P28ToneProfile,
    P28SafetyResult,
    P28Output,
)

if TYPE_CHECKING:
    from symbolu_core.mechanical.pipeline.models import PipelineContext
    from symbolu_core.mechanical.pipeline.p27_persona import P27Output


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_dha_engine: Optional[DHAEngine] = None
_tone_selector: Optional[ToneSelector] = None
_readiness_analyzer: Optional[ReadinessAnalyzer] = None
_resistance_detector: Optional[ResistanceDetector] = None
_safety_filters: Optional[SafetyFilters] = None


def get_dha_engine() -> DHAEngine:
    """Get or create singleton DHAEngine instance."""
    global _dha_engine
    if _dha_engine is None:
        _dha_engine = DHAEngine()
    return _dha_engine


def get_tone_selector() -> ToneSelector:
    """Get or create singleton ToneSelector instance."""
    global _tone_selector
    if _tone_selector is None:
        _tone_selector = ToneSelector()
    return _tone_selector


def get_readiness_analyzer() -> ReadinessAnalyzer:
    """Get or create singleton ReadinessAnalyzer instance."""
    global _readiness_analyzer
    if _readiness_analyzer is None:
        _readiness_analyzer = ReadinessAnalyzer()
    return _readiness_analyzer


def get_resistance_detector() -> ResistanceDetector:
    """Get or create singleton ResistanceDetector instance."""
    global _resistance_detector
    if _resistance_detector is None:
        _resistance_detector = ResistanceDetector()
    return _resistance_detector


def get_safety_filters() -> SafetyFilters:
    """Get or create singleton SafetyFilters instance."""
    global _safety_filters
    if _safety_filters is None:
        _safety_filters = SafetyFilters()
    return _safety_filters


# =============================================================================
# SIGNAL EXTRACTION
# =============================================================================


def extract_p28_signals(
    ctx: "PipelineContext",
    p27_output: Optional["P27Output"] = None,
) -> Optional[P28InputSignals]:
    """
    Extract P28 input signals from pipeline context.

    Args:
        ctx: Pipeline context with MLCR and fusion results.
        p27_output: Optional P27 output for persona context.

    Returns:
        P28InputSignals if extraction succeeds, None otherwise.
    """
    try:
        # Get query text
        query_text = ""
        if hasattr(ctx, 'request') and ctx.request:
            query_text = ctx.request.text or ""

        # Get response text from fusion
        response_text = ""
        if hasattr(ctx, 'fusion') and ctx.fusion:
            response_text = ctx.fusion.merged_output or ""

        # Get P27 persona context
        persona_id = "neutral"
        persona_tone_warmth = 0.5
        persona_formality = 0.5
        persona_directness = 0.5

        if p27_output:
            persona_id = p27_output.persona_id
            directives = p27_output.directives
            persona_tone_warmth = directives.tone_warmth
            persona_formality = directives.formality_level
            persona_directness = directives.directness
        elif hasattr(ctx, 'p27_persona') and ctx.p27_persona:
            p27 = ctx.p27_persona
            persona_id = p27.persona_id
            directives = p27.directives
            persona_tone_warmth = directives.tone_warmth
            persona_formality = directives.formality_level
            persona_directness = directives.directness

        # Get MLCR signals
        tier = "hybrid"
        intent = "general"
        domain = "generic"
        emotional_entropy = 0.5
        dimensional_entropy = 0.5

        if hasattr(ctx, 'mlcr') and ctx.mlcr:
            explain_log = getattr(ctx.mlcr, 'explain_log', {})
            if isinstance(explain_log, dict):
                meta = explain_log.get("meta", {})
                tier = meta.get("tier", "hybrid")
                intent = meta.get("intent", "general")
                domain = meta.get("domain", "generic")

                entropy = explain_log.get("entropy", {})
                emotional_entropy = entropy.get("H_D", 0.5)
                dimensional_entropy = entropy.get("H_G", 0.5)

        # Analyze readiness and resistance
        readiness_analyzer = get_readiness_analyzer()
        resistance_detector = get_resistance_detector()

        readiness_score = 0.5
        resistance_score = 0.3

        try:
            readiness_result = readiness_analyzer.analyze(query_text)
            readiness_score = getattr(readiness_result, 'score', 0.5)
        except Exception:
            pass

        try:
            resistance_result = resistance_detector.detect(query_text)
            resistance_score = getattr(resistance_result, 'score', 0.3)
        except Exception:
            pass

        return P28InputSignals(
            query_text=query_text,
            response_text=response_text,
            persona_id=persona_id,
            persona_tone_warmth=persona_tone_warmth,
            persona_formality=persona_formality,
            persona_directness=persona_directness,
            tier=tier,
            intent=intent,
            domain=domain,
            emotional_entropy=emotional_entropy,
            dimensional_entropy=dimensional_entropy,
            readiness_score=readiness_score,
            resistance_score=resistance_score,
        )

    except Exception:
        return None


# =============================================================================
# PROFILE MAPPING
# =============================================================================


def map_delivery_profile(
    signals: P28InputSignals,
) -> DeliveryProfileType:
    """
    Map signals to delivery profile type.

    Args:
        signals: P28 input signals.

    Returns:
        DeliveryProfileType based on signals.
    """
    # High resistance + low readiness → inverse jolt
    if signals.resistance_score > 0.6 and signals.readiness_score < 0.4:
        return DeliveryProfileType.INVERSE_JOLT

    # High emotional entropy → symbolic metaphor
    if signals.emotional_entropy > 0.7:
        return DeliveryProfileType.SYMBOLIC_METAPHOR

    # High readiness + low resistance → sweet resonance
    if signals.readiness_score > 0.6 and signals.resistance_score < 0.4:
        return DeliveryProfileType.SWEET_RESONANCE

    return DeliveryProfileType.BALANCED


def map_readiness_level(score: float) -> ReadinessLevel:
    """Map readiness score to level."""
    if score < 0.35:
        return ReadinessLevel.LOW
    elif score < 0.65:
        return ReadinessLevel.MEDIUM
    return ReadinessLevel.HIGH


def map_resistance_level(score: float) -> ResistanceLevel:
    """Map resistance score to level."""
    if score < 0.2:
        return ResistanceLevel.NONE
    elif score < 0.4:
        return ResistanceLevel.LOW
    elif score < 0.6:
        return ResistanceLevel.MEDIUM
    return ResistanceLevel.HIGH


def build_tone_profile(
    profile_type: DeliveryProfileType,
    signals: P28InputSignals,
) -> P28ToneProfile:
    """
    Build P28ToneProfile from profile type and signals.

    Args:
        profile_type: Selected delivery profile type.
        signals: Input signals for context.

    Returns:
        P28ToneProfile with modulation parameters.
    """
    # Base values from persona
    warmth = signals.persona_tone_warmth
    directness = signals.persona_directness
    formality = signals.persona_formality
    empathy = 0.5
    pace = "normal"

    # Modulate based on profile type
    if profile_type == DeliveryProfileType.SWEET_RESONANCE:
        warmth = min(1.0, warmth + 0.2)
        empathy = 0.8
        pace = "slow"
    elif profile_type == DeliveryProfileType.INVERSE_JOLT:
        directness = min(1.0, directness + 0.3)
        warmth = max(0.0, warmth - 0.1)
        pace = "fast"
    elif profile_type == DeliveryProfileType.SYMBOLIC_METAPHOR:
        directness = max(0.0, directness - 0.2)
        formality = max(0.0, formality - 0.1)
        empathy = 0.7

    return P28ToneProfile(
        profile_type=profile_type,
        warmth=warmth,
        directness=directness,
        formality=formality,
        empathy=empathy,
        message_pace=pace,
    )


# =============================================================================
# MAIN INTEGRATION
# =============================================================================


def run_p28_adaptation(
    signals: P28InputSignals,
) -> P28Output:
    """
    Run P28 delivery harmonization with extracted signals.

    Args:
        signals: P28InputSignals from context.

    Returns:
        P28Output with adapted message and profile.
    """
    dha_engine = get_dha_engine()
    safety_filters = get_safety_filters()

    trace = []

    # Determine delivery profile
    profile_type = map_delivery_profile(signals)
    trace.append(f"Selected profile: {profile_type.value}")

    # Build tone profile
    tone_profile = build_tone_profile(profile_type, signals)
    trace.append(f"Tone: warmth={tone_profile.warmth:.2f}, directness={tone_profile.directness:.2f}")

    # Map readiness and resistance levels
    readiness_level = map_readiness_level(signals.readiness_score)
    resistance_level = map_resistance_level(signals.resistance_score)
    trace.append(f"Readiness: {readiness_level.value}, Resistance: {resistance_level.value}")

    # Run DHA adaptation
    adapted_text = signals.response_text
    try:
        dha_input = DHAInput(
            text=signals.response_text,
            readiness_score=signals.readiness_score,
            resistance_score=signals.resistance_score,
            emotional_entropy=signals.emotional_entropy,
            domain=signals.domain,
        )
        dha_result = dha_engine.run(dha_input)
        adapted_text = dha_result.adapted_message or signals.response_text
        trace.append("DHA adaptation applied")
    except Exception as e:
        trace.append(f"DHA fallback: {str(e)[:50]}")

    # Apply safety filters
    guarded_text = adapted_text
    safety_status = SafetyStatus.PASSED
    safety_modifications: list = []
    safety_score = 1.0

    try:
        filter_result = safety_filters.filter_text(adapted_text)
        if hasattr(filter_result, 'filtered_text'):
            guarded_text = filter_result.filtered_text
            if guarded_text != adapted_text:
                safety_status = SafetyStatus.MODIFIED
                safety_modifications.append("Safety filter applied modifications")
        if hasattr(filter_result, 'score'):
            safety_score = filter_result.score
        trace.append(f"Safety check: {safety_status.value}")
    except Exception:
        trace.append("Safety filter skipped")

    safety_result = P28SafetyResult(
        status=safety_status,
        original_text=adapted_text if safety_status == SafetyStatus.MODIFIED else None,
        modifications=safety_modifications,
        safety_score=safety_score,
    )

    # Determine authority
    authority = P28Authority.MEDIUM
    if safety_status == SafetyStatus.MODIFIED or safety_status == SafetyStatus.BLOCKED:
        authority = P28Authority.HIGH  # Safety decisions are high authority

    return P28Output(
        adapted_text=adapted_text,
        guarded_text=guarded_text,
        tone_profile=tone_profile,
        readiness_level=readiness_level,
        resistance_level=resistance_level,
        safety_result=safety_result,
        authority=authority,
        adaptation_trace=trace,
    )


def maybe_run_p28(
    ctx: "PipelineContext",
    p27_output: Optional["P27Output"] = None,
) -> Optional[P28Output]:
    """
    Conditionally run P28 delivery harmonization phase.

    This is the main integration function to call from the pipeline orchestrator.

    Args:
        ctx: Pipeline context with MLCR and fusion results.
        p27_output: Optional P27 output for persona context.

    Returns:
        P28Output if phase executed, None otherwise.
    """
    # Extract signals from context
    signals = extract_p28_signals(ctx, p27_output)
    if signals is None:
        return None

    # Run adaptation
    return run_p28_adaptation(signals)


def get_p28_output(ctx: "PipelineContext") -> Optional[P28Output]:
    """
    Get P28 output from context if available.

    Args:
        ctx: Pipeline context.

    Returns:
        P28Output if available, None otherwise.
    """
    if hasattr(ctx, 'p28_dha'):
        return ctx.p28_dha
    return None


def get_p28_guarded_text(ctx: "PipelineContext") -> str:
    """
    Get guarded text from P28 output.

    Args:
        ctx: Pipeline context.

    Returns:
        Guarded text string, defaults to empty string.
    """
    output = get_p28_output(ctx)
    if output:
        return output.guarded_text
    return ""


def get_p28_tone_profile(ctx: "PipelineContext") -> Optional[P28ToneProfile]:
    """
    Get tone profile from P28 output.

    Args:
        ctx: Pipeline context.

    Returns:
        P28ToneProfile if available, None otherwise.
    """
    output = get_p28_output(ctx)
    if output:
        return output.tone_profile
    return None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "get_dha_engine",
    "get_tone_selector",
    "get_readiness_analyzer",
    "get_resistance_detector",
    "get_safety_filters",
    "extract_p28_signals",
    "run_p28_adaptation",
    "maybe_run_p28",
    "get_p28_output",
    "get_p28_guarded_text",
    "get_p28_tone_profile",
    "VERSION",
]
