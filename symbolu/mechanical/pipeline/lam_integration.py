"""
LAM Pipeline Integration Module

Provides a thin shim for integrating LAM (Long-Arc Mapper) into the
Symbol-U pipeline. Called when MLCR/TTOR sets use_lam=True or when
long_arc_tension exceeds threshold.

Usage in orchestrator:
    from .lam_integration import maybe_run_lam, get_temporal_tracker, get_cdi

    # After MLCR stage
    lam_map = maybe_run_lam(ctx)
    if lam_map:
        ctx.lam_map = lam_map
"""

from typing import Any, Dict, Optional

from symbolu.mechanical.lam import LAMEngine, LAMInput, LongArcMap
from symbolu.temporal.temporal_bhava_tracker import TemporalBhavaTracker
from symbolu.temporal.cross_domain_intelligence import CrossDomainIntelligence

# Default long-arc tension threshold for LAM activation
DEFAULT_LAM_TENSION_THRESHOLD = 0.4

# Singleton instances
_lam_engine: Optional[LAMEngine] = None
_temporal_tracker: Optional[TemporalBhavaTracker] = None
_cdi: Optional[CrossDomainIntelligence] = None


def get_lam_engine() -> LAMEngine:
    """Get or create the singleton LAM engine instance."""
    global _lam_engine
    if _lam_engine is None:
        _lam_engine = LAMEngine()
    return _lam_engine


def get_temporal_tracker(window_size: int = 10) -> TemporalBhavaTracker:
    """
    Get or create the singleton TemporalBhavaTracker instance.

    Args:
        window_size: Size of the sliding window (used only for creation).

    Returns:
        Shared TemporalBhavaTracker instance.
    """
    global _temporal_tracker
    if _temporal_tracker is None:
        _temporal_tracker = TemporalBhavaTracker(window_size=window_size)
    return _temporal_tracker


def get_cdi() -> CrossDomainIntelligence:
    """Get or create the singleton CrossDomainIntelligence instance."""
    global _cdi
    if _cdi is None:
        _cdi = CrossDomainIntelligence()
    return _cdi


def reset_temporal_state() -> None:
    """
    Reset the temporal state for a new conversation.

    Call this at the start of a new session/conversation.
    """
    global _temporal_tracker, _cdi
    _temporal_tracker = None
    _cdi = None


def extract_lam_input(
    text: str,
    mlcr_result: Dict[str, Any],
    domain: str = "generic",
    temporal_tracker: Optional[TemporalBhavaTracker] = None,
    cdi: Optional[CrossDomainIntelligence] = None,
) -> Optional[LAMInput]:
    """
    Extract LAMInput from MLCR result and query text.

    Args:
        text: The original query text.
        mlcr_result: The MLCR routing result dictionary.
        domain: Override domain if not in MLCR result.
        temporal_tracker: Optional external tracker (uses singleton if None).
        cdi: Optional external CDI (uses singleton if None).

    Returns:
        LAMInput if extraction succeeds, None otherwise.
    """
    try:
        explain_log = mlcr_result.get("explain_log", {})
        activation_plan = mlcr_result.get("activation_plan", {})
        meta = explain_log.get("meta", {})

        # Extract core analysis results
        analysis = explain_log.get("analysis", {})

        # Get SMI (semantic mismatch index)
        smi = float(analysis.get("smi", 0.5))

        # Get bhava information
        bhava_id = int(analysis.get("bhava_id", 5))
        bhava_direction = analysis.get("bhava_direction", "neutral")

        # Normalize bhava_direction
        if bhava_direction not in ["upward", "downward", "stable"]:
            if bhava_direction == "neutral":
                bhava_direction = "stable"
            else:
                bhava_direction = "stable"

        # Get kosha and ontology IDs
        kosha_id = int(analysis.get("kosha_id", 3))
        ontology_id = int(analysis.get("ontology_id", 5))

        # Get long_arc_tension from activation plan or meta
        long_arc_tension = float(activation_plan.get("long_arc_tension", 0.0))
        if long_arc_tension == 0.0:
            long_arc_tension = float(meta.get("long_arc_tension", 0.0))

        # Get domain
        result_domain = meta.get("domain", domain)

        # Use provided instances or get singletons
        tracker = temporal_tracker or get_temporal_tracker()
        cdi_instance = cdi or get_cdi()

        return LAMInput(
            text=text,
            smi=smi,
            bhava_id=bhava_id,
            bhava_direction=bhava_direction,
            kosha_id=kosha_id,
            ontology_id=ontology_id,
            domain=result_domain,
            long_arc_tension=long_arc_tension,
            temporal_tracker=tracker,
            cdi=cdi_instance,
        )
    except Exception:
        # If extraction fails, return None gracefully
        return None


def should_run_lam(
    mlcr_result: Dict[str, Any],
    tension_threshold: float = DEFAULT_LAM_TENSION_THRESHOLD,
) -> bool:
    """
    Determine if LAM should run based on activation plan and tension.

    LAM runs when:
    - activation_plan.use_lam = True
    - OR long_arc_tension > tension_threshold

    Args:
        mlcr_result: The MLCR routing result dictionary.
        tension_threshold: Threshold for tension-based activation.

    Returns:
        True if LAM should run, False otherwise.
    """
    activation_plan = mlcr_result.get("activation_plan", {})

    # Check explicit use_lam flag
    if activation_plan.get("use_lam", False):
        return True

    # Check long_arc_tension threshold
    explain_log = mlcr_result.get("explain_log", {})
    long_arc_tension = float(activation_plan.get("long_arc_tension", 0.0))
    if long_arc_tension == 0.0:
        meta = explain_log.get("meta", {})
        long_arc_tension = float(meta.get("long_arc_tension", 0.0))

    if long_arc_tension > tension_threshold:
        return True

    return False


def maybe_run_lam(
    ctx: Any,
    tension_threshold: float = DEFAULT_LAM_TENSION_THRESHOLD,
) -> Optional[LongArcMap]:
    """
    Conditionally run LAM if use_lam is enabled or tension exceeds threshold.

    This is the main integration function to call from the pipeline orchestrator.

    Args:
        ctx: Pipeline context with mlcr result and request.
        tension_threshold: Threshold for tension-based activation.

    Returns:
        LongArcMap if LAM was run, None otherwise.
    """
    # Check if we have MLCR result
    if not hasattr(ctx, 'mlcr') or ctx.mlcr is None:
        return None

    # Get the MLCR entries (the raw result dict)
    mlcr_result = ctx.mlcr.entries if hasattr(ctx.mlcr, 'entries') else {}

    # Check if LAM should run
    if not should_run_lam(mlcr_result, tension_threshold):
        return None

    # Get text from request
    if not hasattr(ctx, 'request') or not hasattr(ctx.request, 'text'):
        return None

    text = ctx.request.text

    # Get domain from request metadata if available
    domain = "generic"
    if hasattr(ctx.request, 'metadata'):
        domain = ctx.request.metadata.get("domain", "generic")

    # Extract LAMInput
    lam_input = extract_lam_input(text, mlcr_result, domain)
    if lam_input is None:
        return None

    # Run LAM
    engine = get_lam_engine()
    return engine.build_map(lam_input)


def run_lam_directly(
    text: str,
    smi: float,
    bhava_id: int,
    bhava_direction: str,
    kosha_id: int,
    ontology_id: int,
    domain: str,
    long_arc_tension: float,
    temporal_tracker: Optional[TemporalBhavaTracker] = None,
    cdi: Optional[CrossDomainIntelligence] = None,
) -> LongArcMap:
    """
    Run LAM directly with explicit parameters.

    Useful for testing or when you have raw analysis signals.

    Args:
        text: The query text.
        smi: Semantic Mismatch Index value.
        bhava_id: Bhava state identifier.
        bhava_direction: Direction of bhava.
        kosha_id: Kosha layer identifier.
        ontology_id: Ontology state identifier.
        domain: Domain classification.
        long_arc_tension: TTOR long-arc tension signal.
        temporal_tracker: Optional external tracker (uses singleton if None).
        cdi: Optional external CDI (uses singleton if None).

    Returns:
        LongArcMap with temporal-longitudinal cognitive mapping data.
    """
    tracker = temporal_tracker or get_temporal_tracker()
    cdi_instance = cdi or get_cdi()

    lam_input = LAMInput(
        text=text,
        smi=smi,
        bhava_id=bhava_id,
        bhava_direction=bhava_direction,
        kosha_id=kosha_id,
        ontology_id=ontology_id,
        domain=domain,
        long_arc_tension=long_arc_tension,
        temporal_tracker=tracker,
        cdi=cdi_instance,
    )

    engine = get_lam_engine()
    return engine.build_map(lam_input)


__all__ = [
    "get_lam_engine",
    "get_temporal_tracker",
    "get_cdi",
    "reset_temporal_state",
    "maybe_run_lam",
    "run_lam_directly",
    "extract_lam_input",
    "should_run_lam",
    "DEFAULT_LAM_TENSION_THRESHOLD",
]
