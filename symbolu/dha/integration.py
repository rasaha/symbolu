"""
DHA (Delivery Harmonization Algorithm) Pipeline Integration
============================================================

Pipeline stage wrapper for integrating DHA into the Symbol-U pipeline.

Pipeline Position:
    Fusion → DHA → Renderer

This module provides:
    - DHAStage: Pipeline stage wrapper
    - Signal extraction from PipelineContext (via signal_extraction module)
    - Result attachment to EngineResult/PipelineContext metadata

EXPLICIT CONSTRAINTS (Signal Extraction):
    - No new inference engines
    - No psychology inference
    - No invented semantics
    - Direct signal reuse + normalization only
    - Deterministic defaults for missing signals

Version: 1.1
Date: 2025-12-22
"""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING, Union

from .config import DHAConfig, EntropySource
from .engine import DHAEngine
from .types import DHAInputs, DHAResult, DHANoOpResult, DeliveryProfile, Tier
from .signal_extraction import (
    extract_dha_inputs,
    extract_signals_from_context_v2,
    SignalExtractionAudit,
)

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

    Uses the canonical signal extraction module (signal_extraction.py)
    which implements deterministic mapping formulas.

    SIGNAL MAPPING TABLE:

    | DHA Input | Source Module | Field Name | Formula | Default |
    |-----------|---------------|------------|---------|---------|
    | H_G | MLCR/Observables | explain_log['entropy']['H_G'] | H = H_G / ln(3) | 0.0 |
    | M | P18/Metadata | delta_entropy | M = abs(delta) | 0.0 |
    | C_s | CoherenceState | coherence_score | C_s = clip(score, 0, 1) | 1.0 |
    | C_contr | MLCR | explain_log['contradiction'] | C_contr = clip(raw, 0, 1) | 0.0 |
    | s, r, t | MLCR/Observables | explain_log['guna'] | normalize(s+r+t=1) | balanced |

    EXPLICIT CONSTRAINTS:
        - No new inference engines
        - No psychology inference
        - No invented semantics
        - Direct signal reuse + normalization only
        - Deterministic defaults for missing signals

    Missing signals use deterministic defaults and are logged in audit.

    Args:
        ctx: PipelineContext with upstream stage results
        config: DHA configuration (for entropy source selection)

    Returns:
        DHAInputs with extracted or default signals
    """
    # Use the canonical extraction with full audit
    inputs, audit = extract_dha_inputs(ctx, config)

    # Attach audit to request metadata for observability
    if hasattr(ctx, 'request') and ctx.request and hasattr(ctx.request, 'metadata'):
        ctx.request.metadata['dha_signal_extraction_audit'] = audit.to_dict()

    return inputs


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
