"""
HRM Pipeline Integration Module

Provides a thin shim for integrating HRM (High-Resolution Mapper) into the
Symbol-U pipeline. Called when MLCR/TTOR sets use_hrm=True.

Usage in orchestrator:
    from .hrm_integration import maybe_run_hrm

    # After MLCR stage
    hrm_map = maybe_run_hrm(ctx)
    if hrm_map:
        ctx.hrm_map = hrm_map
"""

from typing import Any, Dict, Optional

from symbolu.mechanical.hrm import HRMEngine, HRMInput, HighResolutionMap

# Singleton HRM engine instance
_hrm_engine: Optional[HRMEngine] = None


def get_hrm_engine() -> HRMEngine:
    """Get or create the singleton HRM engine instance."""
    global _hrm_engine
    if _hrm_engine is None:
        _hrm_engine = HRMEngine()
    return _hrm_engine


def extract_hrm_input(mlcr_result: Dict[str, Any], domain: str = "generic") -> Optional[HRMInput]:
    """
    Extract HRMInput from MLCR result.

    Args:
        mlcr_result: The MLCR routing result dictionary.
        domain: Override domain if not in MLCR result.

    Returns:
        HRMInput if extraction succeeds, None otherwise.
    """
    try:
        explain_log = mlcr_result.get("explain_log", {})
        activation_plan = mlcr_result.get("activation_plan", {})
        meta = explain_log.get("meta", {})
        entropy = explain_log.get("entropy", {})
        aspect_probs = explain_log.get("aspect_probs", {})
        anchor_scores = explain_log.get("anchor_scores", {})

        # If aspect_probs or anchor_scores are empty, return None
        if not aspect_probs:
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

        return HRMInput(
            aspect_probs=aspect_probs,
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


def maybe_run_hrm(ctx: Any) -> Optional[HighResolutionMap]:
    """
    Conditionally run HRM if use_hrm is enabled in the activation plan.

    This is the main integration function to call from the pipeline orchestrator.

    Args:
        ctx: Pipeline context with mlcr result.

    Returns:
        HighResolutionMap if HRM was run, None otherwise.
    """
    # Check if we have MLCR result
    if not hasattr(ctx, 'mlcr') or ctx.mlcr is None:
        return None

    # Get the MLCR entries (the raw result dict)
    mlcr_result = ctx.mlcr.entries if hasattr(ctx.mlcr, 'entries') else {}

    # Check if use_hrm is enabled
    activation_plan = mlcr_result.get("activation_plan", {})
    if not activation_plan.get("use_hrm", False):
        return None

    # Get domain from request metadata if available
    domain = "generic"
    if hasattr(ctx, 'request') and hasattr(ctx.request, 'metadata'):
        domain = ctx.request.metadata.get("domain", "generic")

    # Extract HRMInput
    hrm_input = extract_hrm_input(mlcr_result, domain)
    if hrm_input is None:
        return None

    # Run HRM
    engine = get_hrm_engine()
    return engine.build_map(hrm_input)


def run_hrm_directly(
    aspect_probs: Dict[str, float],
    anchor_scores: Dict[str, float],
    H_D: float,
    H_G: float,
    H_K: float,
    domain: str,
    tier: str,
    flow_mode: str,
) -> HighResolutionMap:
    """
    Run HRM directly with explicit parameters.

    Useful for testing or when you have raw routing signals.

    Args:
        aspect_probs: Aspect probability dictionary.
        anchor_scores: Anchor score dictionary.
        H_D: Dimensional entropy.
        H_G: Guna entropy.
        H_K: Kosha entropy.
        domain: Domain classification.
        tier: Routing tier ("lower", "upper", "hybrid").
        flow_mode: Flow mode ("outer_only", "outer_plus_inner", "inner_priority").

    Returns:
        HighResolutionMap with cognitive mapping data.
    """
    hrm_input = HRMInput(
        aspect_probs=aspect_probs,
        anchor_scores=anchor_scores,
        H_D=H_D,
        H_G=H_G,
        H_K=H_K,
        domain=domain,
        tier=tier,
        flow_mode=flow_mode,
    )

    engine = get_hrm_engine()
    return engine.build_map(hrm_input)


__all__ = [
    "get_hrm_engine",
    "maybe_run_hrm",
    "run_hrm_directly",
    "extract_hrm_input",
]
