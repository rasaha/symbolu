"""
DHA (Delivery Harmonization Algorithm) Pipeline Integration
============================================================

Pipeline stage wrapper for integrating DHA into the Symbol-U pipeline.

Pipeline Position:
    Fusion → DHA → Renderer

This module provides:
    - DHAStage: Pipeline stage wrapper
    - Signal extraction from PipelineContext
    - Result attachment to EngineResult/PipelineContext metadata

Version: 1.0
Date: 2025-12-22
"""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING, Union

from .config import DHAConfig, EntropySource
from .engine import DHAEngine
from .types import DHAInputs, DHAResult, DHANoOpResult, DeliveryProfile, Tier

if TYPE_CHECKING:
    from symbolu.mechanical.pipeline.models import PipelineContext, FusionResult

logger = logging.getLogger(__name__)


# =============================================================================
# Signal Extraction
# =============================================================================

def extract_signals_from_context(
    ctx: "PipelineContext",
    config: DHAConfig,
) -> DHAInputs:
    """
    Extract DHA input signals from PipelineContext.

    Reads signals from various pipeline stages:
        - Coherence score from coherence_state or coherence_report
        - Motion from semantic deltas or p18 temporal entropy
        - Entropy from guna_modulation observables or entropy module
        - Contradiction from observables or MLCR
        - Guna distribution from guna_modulation or persona

    Missing signals use deterministic defaults.

    Args:
        ctx: PipelineContext with upstream stage results
        config: DHA configuration (for entropy source selection)

    Returns:
        DHAInputs with extracted or default signals
    """
    missing = []

    # =========================================================================
    # Coherence Score (C_s)
    # =========================================================================
    C_s = None

    # Try coherence_state first
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        if hasattr(ctx.coherence_state, 'coherence_score'):
            C_s = ctx.coherence_state.coherence_score
        elif hasattr(ctx.coherence_state, 'coherence_score_v2'):
            C_s = ctx.coherence_state.coherence_score_v2

    # Try coherence_report
    if C_s is None and hasattr(ctx, 'coherence_report') and ctx.coherence_report:
        C_s = ctx.coherence_report.get('coherence_score')

    # Try p17 semantic integrity
    if C_s is None and hasattr(ctx, 'p17') and ctx.p17 is not None:
        if hasattr(ctx.p17, 'integrity_score'):
            C_s = ctx.p17.integrity_score

    if C_s is None:
        C_s = 0.5
        missing.append("C_s")

    # =========================================================================
    # Motion Magnitude (M)
    # =========================================================================
    M = None

    # Try p18 temporal entropy
    if hasattr(ctx, 'p18') and ctx.p18 is not None:
        if hasattr(ctx.p18, 'delta_entropy'):
            # Convert delta entropy to motion magnitude
            M = abs(ctx.p18.delta_entropy) if ctx.p18.delta_entropy else 0.0

    # Try request metadata
    if M is None and hasattr(ctx, 'request') and ctx.request.metadata:
        M = ctx.request.metadata.get('motion_magnitude')
        if M is None:
            M = ctx.request.metadata.get('delta_sem')

    if M is None:
        M = 0.0
        missing.append("M")

    # =========================================================================
    # Entropy Signals (H_G, H_D, H_K)
    # =========================================================================
    H_G = None
    H_D = None
    H_K = None

    # Try MLCR entropy
    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
        entropy = explain_log.get('entropy', {})
        H_G = entropy.get('H_G')
        H_D = entropy.get('H_D')
        H_K = entropy.get('H_K')

    # Try p18 temporal entropy for H_D
    if H_D is None and hasattr(ctx, 'p18') and ctx.p18 is not None:
        if hasattr(ctx.p18, 'entropy_now'):
            H_D = ctx.p18.entropy_now

    # Try request metadata
    if hasattr(ctx, 'request') and ctx.request.metadata:
        if H_G is None:
            H_G = ctx.request.metadata.get('guna_entropy')
        if H_K is None:
            H_K = ctx.request.metadata.get('kosha_entropy')

    if H_G is None and H_D is None and H_K is None:
        missing.append("H")

    # =========================================================================
    # Contradiction Metric (C_contr)
    # =========================================================================
    C_contr = None

    # Try MLCR
    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
        C_contr = explain_log.get('contradiction')

    # Try request metadata
    if C_contr is None and hasattr(ctx, 'request') and ctx.request.metadata:
        C_contr = ctx.request.metadata.get('C_contr')
        if C_contr is None:
            C_contr = ctx.request.metadata.get('contradiction')

    if C_contr is None:
        C_contr = 0.0
        missing.append("C_contr")

    # =========================================================================
    # Guna Distribution (s, r, t)
    # =========================================================================
    s, r, t = None, None, None

    # Try MLCR guna
    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
        guna = explain_log.get('guna', {})
        s = guna.get('sattva') or guna.get('s')
        r = guna.get('rajas') or guna.get('r')
        t = guna.get('tamas') or guna.get('t')

    # Try request metadata
    if (s is None or r is None or t is None) and hasattr(ctx, 'request') and ctx.request.metadata:
        s = s or ctx.request.metadata.get('sattva')
        r = r or ctx.request.metadata.get('rajas')
        t = t or ctx.request.metadata.get('tamas')

    if s is None or r is None or t is None:
        s = 0.333333
        r = 0.333333
        t = 0.333334
        missing.append("guna_distribution")

    # =========================================================================
    # Tier
    # =========================================================================
    tier = "consumer"

    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
        meta = explain_log.get('meta', {})
        tier_str = meta.get('tier', 'consumer')
        if tier_str in ('UPPER', 'enterprise_tier_1'):
            tier = "enterprise_tier_1"
        elif tier_str in ('LOWER', 'enterprise_tier_2'):
            tier = "enterprise_tier_2"
        else:
            tier = "consumer"

    if hasattr(ctx, 'request') and ctx.request.metadata:
        tier_override = ctx.request.metadata.get('tier')
        if tier_override:
            tier = tier_override

    # =========================================================================
    # Base Text Reference
    # =========================================================================
    base_text_ref = None
    if hasattr(ctx, 'fusion') and ctx.fusion is not None:
        if hasattr(ctx.fusion, 'trace'):
            base_text_ref = str(ctx.fusion.trace.get('candidate_count', 'fusion'))

    # =========================================================================
    # Build DHAInputs
    # =========================================================================
    tier_map = {
        "enterprise_tier_1": Tier.ENTERPRISE_TIER_1,
        "enterprise_tier_2": Tier.ENTERPRISE_TIER_2,
        "consumer": Tier.CONSUMER,
    }

    return DHAInputs(
        C_s=C_s,
        M=M,
        H_G=H_G,
        H_D=H_D,
        H_K=H_K,
        C_contr=C_contr,
        s=s,
        r=r,
        t=t,
        tier=tier_map.get(tier, Tier.CONSUMER),
        base_text_ref=base_text_ref,
        missing_signals=tuple(missing),
    )


def extract_base_output(ctx: "PipelineContext") -> Optional[str]:
    """
    Extract base output text from PipelineContext.

    Tries:
        1. fusion.selected_text
        2. fusion.fused_candidates.selected_candidate.text
        3. request.text (fallback)

    Args:
        ctx: PipelineContext

    Returns:
        Base output text or None
    """
    # Try fusion selected text
    if hasattr(ctx, 'fusion') and ctx.fusion is not None:
        if hasattr(ctx.fusion, 'selected_text') and ctx.fusion.selected_text:
            return ctx.fusion.selected_text

        # Try nested candidates
        if hasattr(ctx.fusion, 'fused_candidates'):
            candidates = ctx.fusion.fused_candidates
            if hasattr(candidates, 'selected_candidate'):
                cand = candidates.selected_candidate
                if hasattr(cand, 'text'):
                    return cand.text

    # Fallback to request text
    if hasattr(ctx, 'request') and ctx.request:
        return ctx.request.text

    return None


# =============================================================================
# DHA Stage
# =============================================================================

class DHAStage:
    """
    Pipeline stage wrapper for DHA.

    Integrates DHA into the Symbol-U pipeline between Fusion and Renderer.

    Usage:
        stage = DHAStage(config)
        ctx = stage.run(ctx)
        # ctx.metadata["dha"] now contains DHAResult

    Example in pipeline:
        # In orchestrator
        dha_stage = DHAStage(dha_config)
        ctx = dha_stage.run(ctx)
        # Continue to renderer
    """

    def __init__(
        self,
        config: Optional[DHAConfig] = None,
        engine: Optional[DHAEngine] = None,
    ):
        """
        Initialize DHA stage.

        Args:
            config: DHA configuration (default: disabled)
            engine: Optional pre-configured engine
        """
        self.config = config or DHAConfig()
        self.engine = engine or DHAEngine(self.config)

    @classmethod
    def for_tier(cls, tier: str) -> "DHAStage":
        """
        Create stage with tier-specific configuration.

        Args:
            tier: One of "enterprise_tier_1", "enterprise_tier_2", "consumer"

        Returns:
            DHAStage configured for the tier
        """
        config = DHAConfig.for_tier(tier)
        return cls(config)

    def run(self, ctx: "PipelineContext") -> "PipelineContext":
        """
        Run DHA stage on pipeline context.

        This method:
            1. Extracts signals from context
            2. Extracts base output from Fusion
            3. Applies DHA computation
            4. Attaches result to context metadata

        Args:
            ctx: PipelineContext from previous stage (Fusion)

        Returns:
            PipelineContext with DHA metadata attached
        """
        # Check if DHA is enabled
        if not self.config.enabled:
            logger.debug("DHA stage: disabled via config, skipping")
            self._attach_noop_result(ctx)
            return ctx

        try:
            # Extract signals
            signals = extract_signals_from_context(ctx, self.config)
            logger.debug(
                f"DHA stage: extracted signals - C_s={signals.C_s:.3f}, "
                f"M={signals.M:.3f}, missing={signals.missing_signals}"
            )

            # Extract base output
            base_output = extract_base_output(ctx)

            # Apply DHA
            _, result = self.engine.apply(base_output, signals)

            # Attach result to context
            self._attach_result(ctx, result)

            if isinstance(result, DHAResult):
                logger.info(
                    f"DHA stage: D={result.D:.4f}, tone={result.dominant_tone}"
                )
            else:
                logger.debug("DHA stage: returned no-op result")

        except Exception as e:
            logger.error(f"DHA stage error: {e}")
            self._attach_error_result(ctx, str(e))

        return ctx

    def _attach_result(
        self,
        ctx: "PipelineContext",
        result: Union[DHAResult, DHANoOpResult],
    ) -> None:
        """Attach DHA result to pipeline context."""
        # Ensure metadata dict exists
        if not hasattr(ctx, 'request') or not ctx.request:
            return

        if not hasattr(ctx.request, 'metadata'):
            return

        # Store in request metadata for downstream access
        if isinstance(result, DHAResult):
            ctx.request.metadata["dha"] = result.to_dict()
            ctx.request.metadata["dha_delivery_profile"] = self.engine.get_delivery_profile(result).to_dict()
        else:
            ctx.request.metadata["dha"] = result.to_dict()

    def _attach_noop_result(self, ctx: "PipelineContext") -> None:
        """Attach no-op result to context."""
        noop = DHANoOpResult(enabled=False, reason="DHA disabled via config")
        self._attach_result(ctx, noop)

    def _attach_error_result(self, ctx: "PipelineContext", error: str) -> None:
        """Attach error result to context."""
        noop = DHANoOpResult(enabled=True, reason=f"DHA error: {error}")
        self._attach_result(ctx, noop)


# =============================================================================
# Pipeline Helper Functions
# =============================================================================

def maybe_run_dha(
    ctx: "PipelineContext",
    config: Optional[DHAConfig] = None,
) -> Optional[Dict[str, Any]]:
    """
    Conditionally run DHA on pipeline context.

    This is the main integration point for the pipeline orchestrator.

    Args:
        ctx: PipelineContext
        config: Optional DHA configuration

    Returns:
        DHA result dict or None if disabled
    """
    cfg = config or DHAConfig()

    if not cfg.enabled:
        logger.debug("DHA: disabled, skipping")
        return None

    stage = DHAStage(cfg)
    ctx = stage.run(ctx)

    # Return the attached result
    if hasattr(ctx, 'request') and ctx.request and hasattr(ctx.request, 'metadata'):
        return ctx.request.metadata.get("dha")

    return None


def get_dha_delivery_profile(ctx: "PipelineContext") -> Optional[Dict[str, Any]]:
    """
    Get DHA delivery profile from pipeline context.

    Args:
        ctx: PipelineContext after DHA stage

    Returns:
        Delivery profile dict or None
    """
    if hasattr(ctx, 'request') and ctx.request and hasattr(ctx.request, 'metadata'):
        return ctx.request.metadata.get("dha_delivery_profile")
    return None


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    "DHAStage",
    "extract_signals_from_context",
    "extract_base_output",
    "maybe_run_dha",
    "get_dha_delivery_profile",
]
