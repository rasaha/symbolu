"""
P27 Persona Selection Phase Integration
========================================

Integration shim for running P27 Persona Selection phase within
the Symbol-U pipeline orchestrator.

Usage in orchestrator:
    from .p27_persona import maybe_run_p27, get_p27_output

    # During persona stage
    p27_result = maybe_run_p27(ctx)
    if p27_result:
        ctx.p27_persona = p27_result
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from symbolu_core.mechanical.persona import (
    PersonaEngine,
    PersonaSelector,
    get_default_registry,
    PersonaProfile,
)

from .p27_persona_schema import (
    VERSION,
    P27Authority,
    PersonaSelectionMode,
    PersonaCategory,
    P27SelectionSignals,
    P27PersonaDirectives,
    P27Output,
)

if TYPE_CHECKING:
    from symbolu_core.mechanical.pipeline.models import PipelineContext


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_persona_engine: Optional[PersonaEngine] = None
_persona_selector: Optional[PersonaSelector] = None


def get_persona_engine() -> PersonaEngine:
    """Get or create singleton PersonaEngine instance."""
    global _persona_engine
    if _persona_engine is None:
        _persona_engine = PersonaEngine()
    return _persona_engine


def get_persona_selector() -> PersonaSelector:
    """Get or create singleton PersonaSelector instance."""
    global _persona_selector
    if _persona_selector is None:
        _persona_selector = PersonaSelector()
    return _persona_selector


# =============================================================================
# SIGNAL EXTRACTION
# =============================================================================


def extract_p27_signals(ctx: "PipelineContext") -> Optional[P27SelectionSignals]:
    """
    Extract P27 selection signals from pipeline context.

    Args:
        ctx: Pipeline context with MLCR and fusion results.

    Returns:
        P27SelectionSignals if extraction succeeds, None otherwise.
    """
    try:
        # Get query text
        query_text = ""
        if hasattr(ctx, 'request') and ctx.request:
            query_text = ctx.request.text or ""

        # Get response text from fusion or DHA
        response_text = ""
        if hasattr(ctx, 'dha') and ctx.dha:
            response_text = ctx.dha.guarded_text or ""
        elif hasattr(ctx, 'fusion') and ctx.fusion:
            response_text = ctx.fusion.merged_output or ""

        # Get MLCR signals
        tier = "hybrid"
        intent = "general"
        domain = "generic"
        emotional_entropy = 0.5
        cognitive_entropy = 0.5

        if hasattr(ctx, 'mlcr') and ctx.mlcr:
            explain_log = getattr(ctx.mlcr, 'explain_log', {})
            if isinstance(explain_log, dict):
                meta = explain_log.get("meta", {})
                tier = meta.get("tier", "hybrid")
                intent = meta.get("intent", "general")
                domain = meta.get("domain", "generic")

                entropy = explain_log.get("entropy", {})
                emotional_entropy = entropy.get("H_D", 0.5)
                cognitive_entropy = entropy.get("H_K", 0.5)

        # Get readiness/resistance from DHA if available
        readiness_score = 0.5
        resistance_score = 0.3

        if hasattr(ctx, 'dha') and ctx.dha:
            readiness_score = getattr(ctx.dha, 'readiness_level', 0.5)
            if isinstance(readiness_score, str):
                # Convert string levels to numeric
                level_map = {"low": 0.3, "medium": 0.5, "high": 0.7}
                readiness_score = level_map.get(readiness_score.lower(), 0.5)

            resistance_score = getattr(ctx.dha, 'resistance_level', 0.3)
            if isinstance(resistance_score, str):
                level_map = {"low": 0.2, "medium": 0.5, "high": 0.8}
                resistance_score = level_map.get(resistance_score.lower(), 0.3)

        # Check for persona hint in request
        mode = PersonaSelectionMode.AUTOMATIC
        persona_hint = None

        if hasattr(ctx, 'request') and ctx.request:
            metadata = getattr(ctx.request, 'metadata', {})
            if isinstance(metadata, dict):
                persona_hint = metadata.get("persona_hint")
                if persona_hint:
                    mode = PersonaSelectionMode.HINT_GUIDED

        return P27SelectionSignals(
            query_text=query_text,
            response_text=response_text,
            tier=tier,
            intent=intent,
            domain=domain,
            emotional_entropy=emotional_entropy,
            cognitive_entropy=cognitive_entropy,
            readiness_score=readiness_score,
            resistance_score=resistance_score,
            mode=mode,
            persona_hint=persona_hint,
        )

    except Exception:
        return None


# =============================================================================
# PERSONA CATEGORY MAPPING
# =============================================================================


def map_persona_to_category(persona_id: str) -> PersonaCategory:
    """Map persona ID to PersonaCategory enum."""
    persona_lower = persona_id.lower()
    mapping = {
        "sage": PersonaCategory.SAGE,
        "analyst": PersonaCategory.ANALYST,
        "coach": PersonaCategory.COACH,
        "friendly": PersonaCategory.FRIENDLY,
        "regulator": PersonaCategory.REGULATOR,
        "neutral": PersonaCategory.NEUTRAL,
    }
    return mapping.get(persona_lower, PersonaCategory.NEUTRAL)


def build_directives_from_profile(
    profile: PersonaProfile,
    signals: P27SelectionSignals,
) -> P27PersonaDirectives:
    """
    Build P27PersonaDirectives from persona profile.

    Args:
        profile: The selected PersonaProfile.
        signals: Input signals for context.

    Returns:
        P27PersonaDirectives with styling guidance.
    """
    # Extract profile characteristics
    tone_warmth = 0.5
    formality_level = 0.5
    directness = 0.5
    use_metaphors = False
    use_technical_terms = True

    # Map persona characteristics
    persona_id = profile.persona_id.lower() if hasattr(profile, 'persona_id') else "neutral"

    if persona_id == "sage":
        tone_warmth = 0.6
        formality_level = 0.6
        directness = 0.4
        use_metaphors = True
        use_technical_terms = False
    elif persona_id == "analyst":
        tone_warmth = 0.3
        formality_level = 0.7
        directness = 0.8
        use_metaphors = False
        use_technical_terms = True
    elif persona_id == "coach":
        tone_warmth = 0.7
        formality_level = 0.4
        directness = 0.6
        use_metaphors = True
        use_technical_terms = False
    elif persona_id == "friendly":
        tone_warmth = 0.9
        formality_level = 0.2
        directness = 0.5
        use_metaphors = False
        use_technical_terms = False
    elif persona_id == "regulator":
        tone_warmth = 0.2
        formality_level = 0.9
        directness = 0.9
        use_metaphors = False
        use_technical_terms = True

    # Adjust based on domain
    domain_vocabulary: set = set()
    if signals.domain == "finance":
        domain_vocabulary = {"market", "portfolio", "risk", "return"}
        use_technical_terms = True
    elif signals.domain == "medical":
        domain_vocabulary = {"treatment", "diagnosis", "symptoms"}
        use_technical_terms = True
    elif signals.domain == "psychology":
        domain_vocabulary = {"feelings", "patterns", "awareness"}
        use_metaphors = True

    return P27PersonaDirectives(
        tone_warmth=tone_warmth,
        formality_level=formality_level,
        directness=directness,
        use_metaphors=use_metaphors,
        use_technical_terms=use_technical_terms,
        preferred_pronouns="you",
        domain_vocabulary=domain_vocabulary,
    )


# =============================================================================
# MAIN INTEGRATION
# =============================================================================


def run_p27_selection(
    signals: P27SelectionSignals,
) -> P27Output:
    """
    Run P27 persona selection with extracted signals.

    Args:
        signals: P27SelectionSignals from context.

    Returns:
        P27Output with selected persona and directives.
    """
    selector = get_persona_selector()
    registry = get_default_registry()

    # Build selection context
    selection_context = {
        "tier": signals.tier,
        "intent": signals.intent,
        "domain": signals.domain,
        "emotional_entropy": signals.emotional_entropy,
        "readiness_score": signals.readiness_score,
        "resistance_score": signals.resistance_score,
    }

    # Select persona
    reasoning = []

    if signals.mode == PersonaSelectionMode.FORCED and signals.persona_hint:
        persona_id = signals.persona_hint
        confidence = 1.0
        reasoning.append(f"Forced persona selection: {persona_id}")
    elif signals.mode == PersonaSelectionMode.HINT_GUIDED and signals.persona_hint:
        persona_id = signals.persona_hint
        confidence = 0.9
        reasoning.append(f"Hint-guided persona: {persona_id}")
    else:
        # Automatic selection based on signals
        persona_id = "neutral"
        confidence = 0.7

        # Domain-based selection
        if signals.domain == "finance":
            persona_id = "analyst"
            reasoning.append("Domain=finance → analyst persona")
        elif signals.domain == "psychology":
            persona_id = "coach"
            reasoning.append("Domain=psychology → coach persona")
        elif signals.domain == "medical":
            persona_id = "sage"
            reasoning.append("Domain=medical → sage persona")

        # Tier-based adjustment
        if signals.tier == "lower":
            if signals.emotional_entropy > 0.7:
                persona_id = "friendly"
                reasoning.append("High emotional entropy → friendly persona")
        elif signals.tier == "upper":
            if signals.cognitive_entropy < 0.3:
                persona_id = "analyst"
                reasoning.append("Low cognitive entropy → analyst persona")

        # Readiness adjustment
        if signals.resistance_score > 0.6:
            persona_id = "coach"
            reasoning.append("High resistance → coach persona for support")
            confidence = 0.8

        if not reasoning:
            reasoning.append("Default persona selection: neutral")

    # Get persona profile
    try:
        profile = registry.get_safe(persona_id, default="neutral")
    except Exception:
        profile = registry.get_safe("neutral")
        persona_id = "neutral"
        reasoning.append("Fallback to neutral persona")

    # Build directives
    directives = build_directives_from_profile(profile, signals)

    # Determine authority
    authority = P27Authority.MEDIUM
    if signals.mode == PersonaSelectionMode.FORCED:
        authority = P27Authority.HIGH

    # Get alternatives
    alternatives = ["neutral", "sage", "analyst", "coach", "friendly", "regulator"]
    alternatives = [a for a in alternatives if a != persona_id][:3]

    return P27Output(
        persona_id=persona_id,
        persona_category=map_persona_to_category(persona_id),
        selection_mode=signals.mode,
        selection_confidence=confidence,
        authority=authority,
        directives=directives,
        selection_reasoning=reasoning,
        alternatives=alternatives,
    )


def maybe_run_p27(ctx: "PipelineContext") -> Optional[P27Output]:
    """
    Conditionally run P27 persona selection phase.

    This is the main integration function to call from the pipeline orchestrator.

    Args:
        ctx: Pipeline context with MLCR and fusion results.

    Returns:
        P27Output if phase executed, None otherwise.
    """
    # Extract signals from context
    signals = extract_p27_signals(ctx)
    if signals is None:
        return None

    # Run selection
    return run_p27_selection(signals)


def get_p27_output(ctx: "PipelineContext") -> Optional[P27Output]:
    """
    Get P27 output from context if available.

    Args:
        ctx: Pipeline context.

    Returns:
        P27Output if available, None otherwise.
    """
    if hasattr(ctx, 'p27_persona'):
        return ctx.p27_persona
    return None


def get_p27_persona_id(ctx: "PipelineContext") -> str:
    """
    Get selected persona ID from P27 output.

    Args:
        ctx: Pipeline context.

    Returns:
        Persona ID string, defaults to "neutral".
    """
    output = get_p27_output(ctx)
    if output:
        return output.persona_id
    return "neutral"


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "get_persona_engine",
    "get_persona_selector",
    "extract_p27_signals",
    "run_p27_selection",
    "maybe_run_p27",
    "get_p27_output",
    "get_p27_persona_id",
    "VERSION",
]
