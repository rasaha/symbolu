"""
P29 Expression Finalization Phase Integration
===============================================

Integration shim for running P29 Expression Finalization phase within
the Symbol-U pipeline orchestrator.

Integrates existing modules:
- VarnaHybridRenderer: Phoneme-based optimization
- StyleModifiers: Tone-based style application
- Resonance analysis: Bridge meanings and harmony

Usage in orchestrator:
    from .p29_expression import maybe_run_p29, get_p29_output

    # After P28 DHA
    p29_result = maybe_run_p29(ctx)
    if p29_result:
        ctx.p29_expression = p29_result
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .p29_expression_schema import (
    VERSION,
    P29Authority,
    PolishMode,
    RhythmQuality,
    P29InputSignals,
    P29PhonemeAnalysis,
    P29StyleModifications,
    P29Output,
)

if TYPE_CHECKING:
    from symbolu_core.mechanical.pipeline.models import PipelineContext


# =============================================================================
# OPTIONAL IMPORTS (graceful degradation)
# =============================================================================

# Try to import Varṇa modules
try:
    from symbolu_core.mechanical.renderer.varna_hybrid_renderer import (
        VarnaHybridRenderer,
        VarnaAnalysisResult,
    )
    HAS_VARNA = True
except ImportError:
    HAS_VARNA = False
    VarnaHybridRenderer = None
    VarnaAnalysisResult = None

# Try to import resonance modules
try:
    from symbolu_core.resonance import (
        analyze_phrase_varna,
        PhraseAnalysis,
    )
    HAS_RESONANCE = True
except ImportError:
    HAS_RESONANCE = False
    analyze_phrase_varna = None
    PhraseAnalysis = None

# Try to import style modifiers
try:
    from symbolu_core.mechanical.renderer.style_modifiers import StyleModifiers
    HAS_STYLE = True
except ImportError:
    HAS_STYLE = False
    StyleModifiers = None


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_varna_renderer: Optional[Any] = None
_style_modifiers: Optional[Any] = None


def get_varna_renderer() -> Optional[Any]:
    """Get or create singleton VarnaHybridRenderer instance."""
    global _varna_renderer
    if not HAS_VARNA:
        return None
    if _varna_renderer is None:
        _varna_renderer = VarnaHybridRenderer()
    return _varna_renderer


def get_style_modifiers() -> Optional[Any]:
    """Get or create singleton StyleModifiers instance."""
    global _style_modifiers
    if not HAS_STYLE:
        return None
    if _style_modifiers is None:
        _style_modifiers = StyleModifiers()
    return _style_modifiers


# =============================================================================
# SIGNAL EXTRACTION
# =============================================================================


def extract_p29_signals(ctx: "PipelineContext") -> Optional[P29InputSignals]:
    """
    Extract P29 input signals from pipeline context.

    Args:
        ctx: Pipeline context with P28 result.

    Returns:
        P29InputSignals if extraction succeeds, None otherwise.
    """
    try:
        # Get input text from P28 or DHA
        input_text = ""
        if hasattr(ctx, 'p28_dha') and ctx.p28_dha:
            input_text = ctx.p28_dha.guarded_text
        elif hasattr(ctx, 'dha') and ctx.dha:
            input_text = getattr(ctx.dha, 'guarded_text', "")

        if not input_text:
            return None

        # Get P27 persona context
        persona_id = "neutral"
        tone_warmth = 0.5
        formality_level = 0.5
        directness = 0.5

        if hasattr(ctx, 'p27_persona') and ctx.p27_persona:
            p27 = ctx.p27_persona
            persona_id = p27.persona_id
            directives = p27.directives
            tone_warmth = directives.tone_warmth
            formality_level = directives.formality_level
            directness = directives.directness
        elif hasattr(ctx, 'persona') and ctx.persona:
            persona_id = ctx.persona.active_persona_id
            config = ctx.persona.persona_config or {}
            tone_warmth = config.get("warmth", 0.5)
            formality_level = config.get("formality", 0.5)
            directness = config.get("directness", 0.5)

        # Get P28 delivery profile
        delivery_profile = "balanced"
        if hasattr(ctx, 'p28_dha') and ctx.p28_dha:
            delivery_profile = ctx.p28_dha.tone_profile.profile_type.value

        # Determine polish mode based on available modules
        if HAS_VARNA and HAS_STYLE:
            polish_mode = PolishMode.FULL
        elif HAS_VARNA:
            polish_mode = PolishMode.PHONEME_ONLY
        elif HAS_STYLE:
            polish_mode = PolishMode.STYLE_ONLY
        else:
            polish_mode = PolishMode.PASSTHROUGH

        return P29InputSignals(
            input_text=input_text,
            persona_id=persona_id,
            tone_warmth=tone_warmth,
            formality_level=formality_level,
            directness=directness,
            delivery_profile=delivery_profile,
            polish_mode=polish_mode,
        )

    except Exception:
        return None


# =============================================================================
# PHONEME ANALYSIS
# =============================================================================


def run_phoneme_analysis(text: str) -> Optional[P29PhonemeAnalysis]:
    """
    Run Varṇa-based phoneme analysis on text.

    Args:
        text: Text to analyze.

    Returns:
        P29PhonemeAnalysis if analysis succeeds, None otherwise.
    """
    if not HAS_VARNA and not HAS_RESONANCE:
        return None

    try:
        overall_harmony = 0.0
        dominant_layer = "unknown"
        bridge_meanings: List[str] = []
        words_analyzed = 0

        # Try VarnaHybridRenderer first
        renderer = get_varna_renderer()
        if renderer is not None:
            try:
                analysis = renderer.analyze_varna(text)
                if analysis:
                    overall_harmony = analysis.overall_harmony
                    dominant_layer = analysis.dominant_layer
                    bridge_meanings = list(analysis.bridge_meanings) if analysis.bridge_meanings else []
                    words_analyzed = len(text.split())
            except Exception:
                pass

        # Fallback to direct resonance analysis
        if overall_harmony == 0.0 and HAS_RESONANCE and analyze_phrase_varna:
            try:
                phrase_analysis = analyze_phrase_varna(text)
                if phrase_analysis:
                    overall_harmony = getattr(phrase_analysis, 'harmony', 0.0)
                    dominant_layer = getattr(phrase_analysis, 'dominant_layer', 'unknown')
                    words_analyzed = len(text.split())
            except Exception:
                pass

        # Determine rhythm quality based on harmony
        if overall_harmony >= 0.8:
            rhythm_quality = RhythmQuality.EXCELLENT
        elif overall_harmony >= 0.6:
            rhythm_quality = RhythmQuality.GOOD
        elif overall_harmony >= 0.4:
            rhythm_quality = RhythmQuality.FAIR
        else:
            rhythm_quality = RhythmQuality.POOR

        return P29PhonemeAnalysis(
            overall_harmony=overall_harmony,
            dominant_layer=dominant_layer,
            bridge_meanings=bridge_meanings,
            rhythm_quality=rhythm_quality,
            words_analyzed=words_analyzed,
        )

    except Exception:
        return None


# =============================================================================
# STYLE APPLICATION
# =============================================================================


def apply_style_modifications(
    text: str,
    signals: P29InputSignals,
) -> tuple[str, Optional[P29StyleModifications]]:
    """
    Apply style modifications based on persona and delivery profile.

    Args:
        text: Text to modify.
        signals: Input signals with style parameters.

    Returns:
        Tuple of (modified_text, P29StyleModifications).
    """
    if not HAS_STYLE:
        return text, None

    try:
        modifiers = get_style_modifiers()
        if modifiers is None:
            return text, None

        modifications: List[str] = []

        # Map delivery profile to tone
        tone_mapping = {
            "sweet_resonance": "SWEET_RESONANCE",
            "inverse_jolt": "FIRM_COMPASSION",
            "symbolic_metaphor": "GENTLE_MIRROR",
            "balanced": "SWEET_RESONANCE",
        }
        tone = tone_mapping.get(signals.delivery_profile, "SWEET_RESONANCE")

        # Apply style modifiers
        modified_text = modifiers.apply(text, tone)
        if modified_text != text:
            modifications.append(f"Applied {tone} style")

        # Record style parameters
        style_mods = P29StyleModifications(
            warmth_applied=signals.tone_warmth,
            directness_applied=signals.directness,
            formality_applied=signals.formality_level,
            modifications=modifications,
        )

        return modified_text, style_mods

    except Exception:
        return text, None


# =============================================================================
# MAIN INTEGRATION
# =============================================================================


def run_p29_finalization(signals: P29InputSignals) -> P29Output:
    """
    Run P29 expression finalization.

    Args:
        signals: P29InputSignals from context.

    Returns:
        P29Output with polished text and analysis.
    """
    trace: List[str] = []
    final_text = signals.input_text
    phoneme_analysis = None
    style_modifications = None
    polish_applied = False

    # Check for passthrough mode
    if signals.polish_mode == PolishMode.PASSTHROUGH:
        trace.append("Passthrough mode: no modifications")
        return P29Output(
            final_text=final_text,
            polish_applied=False,
            polish_mode=signals.polish_mode,
            authority=P29Authority.LOW,
            processing_trace=trace,
        )

    # Run phoneme analysis
    if signals.polish_mode in (PolishMode.PHONEME_ONLY, PolishMode.FULL):
        trace.append("Running phoneme analysis")
        phoneme_analysis = run_phoneme_analysis(final_text)
        if phoneme_analysis:
            trace.append(f"Phoneme harmony: {phoneme_analysis.overall_harmony:.2f}")
            trace.append(f"Rhythm quality: {phoneme_analysis.rhythm_quality.value}")
            polish_applied = True

    # Apply style modifications
    if signals.polish_mode in (PolishMode.STYLE_ONLY, PolishMode.FULL):
        trace.append("Applying style modifications")
        final_text, style_modifications = apply_style_modifications(
            final_text, signals
        )
        if style_modifications and style_modifications.modifications:
            trace.append(f"Style mods: {len(style_modifications.modifications)}")
            polish_applied = True

    return P29Output(
        final_text=final_text,
        polish_applied=polish_applied,
        polish_mode=signals.polish_mode,
        authority=P29Authority.LOW,
        phoneme_analysis=phoneme_analysis,
        style_modifications=style_modifications,
        processing_trace=trace,
    )


def maybe_run_p29(ctx: "PipelineContext") -> Optional[P29Output]:
    """
    Conditionally run P29 expression finalization phase.

    This is the main integration function to call from the pipeline orchestrator.

    Args:
        ctx: Pipeline context with P28 result.

    Returns:
        P29Output if phase executed, None otherwise.
    """
    # Extract signals from context
    signals = extract_p29_signals(ctx)
    if signals is None:
        return None

    # Run finalization
    return run_p29_finalization(signals)


def get_p29_output(ctx: "PipelineContext") -> Optional[P29Output]:
    """
    Get P29 output from context if available.

    Args:
        ctx: Pipeline context.

    Returns:
        P29Output if available, None otherwise.
    """
    if hasattr(ctx, 'p29_expression'):
        return ctx.p29_expression
    return None


def get_p29_final_text(ctx: "PipelineContext") -> str:
    """
    Get final text from P29 output.

    Args:
        ctx: Pipeline context.

    Returns:
        Final text string, falls back to P28 text.
    """
    output = get_p29_output(ctx)
    if output:
        return output.final_text

    # Fallback to P28
    if hasattr(ctx, 'p28_dha') and ctx.p28_dha:
        return ctx.p28_dha.guarded_text

    return ""


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "get_varna_renderer",
    "get_style_modifiers",
    "extract_p29_signals",
    "run_phoneme_analysis",
    "apply_style_modifications",
    "run_p29_finalization",
    "maybe_run_p29",
    "get_p29_output",
    "get_p29_final_text",
    "HAS_VARNA",
    "HAS_STYLE",
    "HAS_RESONANCE",
    "VERSION",
]
