"""
OLM Pipeline Integration Module

Provides a thin shim for integrating OLM (Ontological Layer Mapper) into the
Symbol-U pipeline. Called when MLCR/TTOR sets use_olm=True (or legacy use_hrm=True).

The 5+5 ontological layer model replaces the previous HRM terminology:
- Lower 5 (O1-O5): Execution / Manifestation Layers
- Upper 5 (O6-O10): Governance / Coherence Layers

Key Architectural Principles:
- There is no active/passive mode
- There is no controller deciding when layers engage
- All layers exist simultaneously
- Behavior emerges from ontological placement + constraints
- Upper layers never generate, only constrain or terminate
- The system is deterministic, non-semantic, and non-learning

Usage in orchestrator:
    from .olm_integration import maybe_run_olm

    # After MLCR stage
    olm_map = maybe_run_olm(ctx)
    if olm_map:
        ctx.olm_map = olm_map
"""

from typing import Any, Dict, Optional

from symbolu.mechanical.olm import OLMEngine, OLMInput, OntologicalLayerMap
from symbolu.mechanical.olm.models import LEGACY_ASPECT_TO_LAYER

# Singleton OLM engine instance
_olm_engine: Optional[OLMEngine] = None


def get_olm_engine() -> OLMEngine:
    """Get or create the singleton OLM engine instance."""
    global _olm_engine
    if _olm_engine is None:
        _olm_engine = OLMEngine()
    return _olm_engine


def extract_olm_input(mlcr_result: Dict[str, Any], domain: str = "generic") -> Optional[OLMInput]:
    """
    Extract OLMInput from MLCR result.

    Supports both legacy aspect names (Execution, Identity, etc.)
    and new ontological layer names (O1_action, O2_tagging, etc.).

    Args:
        mlcr_result: The MLCR routing result dictionary.
        domain: Override domain if not in MLCR result.

    Returns:
        OLMInput if extraction succeeds, None otherwise.
    """
    try:
        explain_log = mlcr_result.get("explain_log", {})
        activation_plan = mlcr_result.get("activation_plan", {})
        meta = explain_log.get("meta", {})
        entropy = explain_log.get("entropy", {})

        # Support both legacy aspect_probs and new layer_weights
        layer_weights = explain_log.get("layer_weights", {})
        if not layer_weights:
            layer_weights = explain_log.get("aspect_probs", {})

        anchor_scores = explain_log.get("anchor_scores", {})

        # If layer_weights is empty, return None
        if not layer_weights:
            return None

        # Extract tier and flow_mode from meta
        tier = meta.get("tier", "hybrid").lower()
        flow_mode = meta.get("flow_mode", "outer_plus_inner")

        # Normalize flow_mode
        if flow_mode.upper() == "OUTER_ONLY":
            flow_mode = "outer_only"
        elif flow_mode.upper() == "INNER_PRIORITY":
            flow_mode = "inner_priority"
        else:
            flow_mode = "outer_plus_inner"

        return OLMInput(
            layer_weights=layer_weights,
            anchor_scores=anchor_scores if anchor_scores else {},
            H_D=entropy.get("H_D", 0.5),
            H_G=entropy.get("H_G", 0.5),
            H_K=entropy.get("H_K", 0.5),
            domain=meta.get("domain", domain),
            tier=tier,
            flow_mode=flow_mode,
        )
    except Exception:
        # If extraction fails, return None gracefully
        return None


def maybe_run_olm(ctx: Any) -> Optional[OntologicalLayerMap]:
    """
    Conditionally run OLM if use_olm (or legacy use_hrm) is enabled.

    Processing is constrained by ontological layer placement.
    Lower layers (O1-O5) execute symbol dynamics; upper layers (O6-O10)
    enforce coherence, alignment, and termination.

    This is the main integration function to call from the pipeline orchestrator.

    Args:
        ctx: Pipeline context with mlcr result.

    Returns:
        OntologicalLayerMap if OLM was run, None otherwise.
    """
    # Check if we have MLCR result
    if not hasattr(ctx, 'mlcr') or ctx.mlcr is None:
        return None

    # Get the MLCR entries (the raw result dict)
    mlcr_result = ctx.mlcr.entries if hasattr(ctx.mlcr, 'entries') else {}

    # Check if use_olm or legacy use_hrm is enabled
    activation_plan = mlcr_result.get("activation_plan", {})
    use_olm = activation_plan.get("use_olm", False) or activation_plan.get("use_hrm", False)
    if not use_olm:
        return None

    # Get domain from request metadata if available
    domain = "generic"
    if hasattr(ctx, 'request') and hasattr(ctx.request, 'metadata'):
        domain = ctx.request.metadata.get("domain", "generic")

    # Extract OLMInput
    olm_input = extract_olm_input(mlcr_result, domain)
    if olm_input is None:
        return None

    # Run OLM
    engine = get_olm_engine()
    return engine.build_map(olm_input)


def run_olm_directly(
    layer_weights: Dict[str, float],
    anchor_scores: Dict[str, float],
    H_D: float,
    H_G: float,
    H_K: float,
    domain: str,
    tier: str,
    flow_mode: str,
) -> OntologicalLayerMap:
    """
    Run OLM directly with explicit parameters.

    Useful for testing or when you have raw routing signals.
    Supports both legacy aspect names and O1-O10 layer names.

    Args:
        layer_weights: Layer weight dictionary (O1-O10 or legacy aspects).
        anchor_scores: Anchor score dictionary.
        H_D: Dimensional entropy.
        H_G: Guna entropy.
        H_K: Kosha entropy.
        domain: Domain classification.
        tier: Routing tier ("lower", "upper", "hybrid").
        flow_mode: Flow mode ("outer_only", "outer_plus_inner", "inner_priority").

    Returns:
        OntologicalLayerMap with ontological placement data.
    """
    olm_input = OLMInput(
        layer_weights=layer_weights,
        anchor_scores=anchor_scores,
        H_D=H_D,
        H_G=H_G,
        H_K=H_K,
        domain=domain,
        tier=tier,
        flow_mode=flow_mode,
    )

    engine = get_olm_engine()
    return engine.build_map(olm_input)


# =============================================================================
# BACKWARD COMPATIBILITY ALIASES
# =============================================================================
# These aliases maintain compatibility with code that references HRM.
# They are deprecated and will be removed in a future version.

# Alias for legacy HRM terminology
maybe_run_hrm = maybe_run_olm
get_hrm_engine = get_olm_engine
extract_hrm_input = extract_olm_input
run_hrm_directly = run_olm_directly


__all__ = [
    # Primary OLM functions
    "get_olm_engine",
    "maybe_run_olm",
    "run_olm_directly",
    "extract_olm_input",
    # Deprecated HRM aliases (backward compatibility)
    "get_hrm_engine",
    "maybe_run_hrm",
    "run_hrm_directly",
    "extract_hrm_input",
]
