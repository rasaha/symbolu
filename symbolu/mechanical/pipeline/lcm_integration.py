"""
LCM Pipeline Integration Module

Provides a thin shim for integrating LCM (Low-Context Mapper) into the
Symbol-U pipeline. Called when MLCR/TTOR sets use_lcm=True.

Usage in orchestrator:
    from .lcm_integration import maybe_run_lcm

    # After MLCR stage
    lcm_map = maybe_run_lcm(ctx)
    if lcm_map:
        ctx.lcm_map = lcm_map
"""

from typing import Any, Dict, Optional

from symbolu.mechanical.lcm import LCMEngine, LCMInput, LowContextMap

# Singleton LCM engine instance
_lcm_engine: Optional[LCMEngine] = None


def get_lcm_engine() -> LCMEngine:
    """Get or create the singleton LCM engine instance."""
    global _lcm_engine
    if _lcm_engine is None:
        _lcm_engine = LCMEngine()
    return _lcm_engine


def extract_lcm_input(
    text: str,
    mlcr_result: Dict[str, Any],
    domain: str = "generic",
) -> Optional[LCMInput]:
    """
    Extract LCMInput from MLCR result and query text.

    Args:
        text: The original query text.
        mlcr_result: The MLCR routing result dictionary.
        domain: Override domain if not in MLCR result.

    Returns:
        LCMInput if extraction succeeds, None otherwise.
    """
    try:
        explain_log = mlcr_result.get("explain_log", {})
        meta = explain_log.get("meta", {})
        entropy = explain_log.get("entropy", {})
        aspect_probs = explain_log.get("aspect_probs", {})
        anchor_scores = explain_log.get("anchor_scores", {})

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

        return LCMInput(
            text=text,
            domain=meta.get("domain", domain),
            aspect_probs=aspect_probs if aspect_probs else {},
            anchor_scores=anchor_scores if anchor_scores else {},
            H_D=entropy.get("H_D", 0.5),
            H_G=entropy.get("H_G", 0.5),
            H_K=entropy.get("H_K", 0.5),
            tier=tier,
            flow_mode=flow_mode,
        )
    except Exception:
        # If extraction fails, return None gracefully
        return None


def maybe_run_lcm(ctx: Any) -> Optional[LowContextMap]:
    """
    Conditionally run LCM if use_lcm is enabled in the activation plan.

    This is the main integration function to call from the pipeline orchestrator.

    Args:
        ctx: Pipeline context with mlcr result and request.

    Returns:
        LowContextMap if LCM was run, None otherwise.
    """
    # Check if we have MLCR result
    if not hasattr(ctx, 'mlcr') or ctx.mlcr is None:
        return None

    # Get the MLCR entries (the raw result dict)
    mlcr_result = ctx.mlcr.entries if hasattr(ctx.mlcr, 'entries') else {}

    # Check if use_lcm is enabled
    activation_plan = mlcr_result.get("activation_plan", {})
    if not activation_plan.get("use_lcm", False):
        return None

    # Get text from request
    if not hasattr(ctx, 'request') or not hasattr(ctx.request, 'text'):
        return None

    text = ctx.request.text

    # Get domain from request metadata if available
    domain = "generic"
    if hasattr(ctx.request, 'metadata'):
        domain = ctx.request.metadata.get("domain", "generic")

    # Extract LCMInput
    lcm_input = extract_lcm_input(text, mlcr_result, domain)
    if lcm_input is None:
        return None

    # Run LCM
    engine = get_lcm_engine()
    return engine.build_map(lcm_input)


def run_lcm_directly(
    text: str,
    domain: str,
    aspect_probs: Dict[str, float],
    anchor_scores: Dict[str, float],
    H_D: float,
    H_G: float,
    H_K: float,
    tier: str,
    flow_mode: str,
) -> LowContextMap:
    """
    Run LCM directly with explicit parameters.

    Useful for testing or when you have raw routing signals.

    Args:
        text: The query text.
        domain: Domain classification.
        aspect_probs: Aspect probability dictionary.
        anchor_scores: Anchor score dictionary.
        H_D: Dimensional entropy.
        H_G: Guna entropy.
        H_K: Kosha entropy.
        tier: Routing tier ("lower", "upper", "hybrid").
        flow_mode: Flow mode ("outer_only", "outer_plus_inner", "inner_priority").

    Returns:
        LowContextMap with structural summary data.
    """
    lcm_input = LCMInput(
        text=text,
        domain=domain,
        aspect_probs=aspect_probs,
        anchor_scores=anchor_scores,
        H_D=H_D,
        H_G=H_G,
        H_K=H_K,
        tier=tier,
        flow_mode=flow_mode,
    )

    engine = get_lcm_engine()
    return engine.build_map(lcm_input)


__all__ = [
    "get_lcm_engine",
    "maybe_run_lcm",
    "run_lcm_directly",
    "extract_lcm_input",
]
