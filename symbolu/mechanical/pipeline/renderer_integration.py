"""
Renderer Integration Module

Integrates FusionRenderer and VarnaHybridRenderer into the pipeline orchestrator.
Bridges the gap between pipeline context and both rendering systems.

Architecture:
    Pipeline Context
           │
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                    RENDERER INTEGRATION                       │
    ├──────────────────────────────────────────────────────────────┤
    │                                                              │
    │  1. Build FusionOutput from mapper outputs + fusion result   │
    │       │                                                      │
    │       ▼                                                      │
    │  2. FusionRenderer → Structured Layers                       │
    │       │              (Symbolic / Practical / Mirror-Truth)   │
    │       ▼                                                      │
    │  3. VarnaHybridRenderer → Phoneme Enhancement                │
    │       │                   (Routing / Attention / Harmony)    │
    │       ▼                                                      │
    │  4. Combine into IntegratedRenderedOutput                    │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘

Usage in orchestrator:
    from .renderer_integration import run_integrated_renderer

    # In _run_renderer()
    ctx.rendered = run_integrated_renderer(ctx)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from symbolu.mechanical.renderer.fusion_renderer import (
    FusionRenderer,
    FusionOutput,
    RenderMode,
    Domain,
    SymbolicLayer,
    PracticalLayer,
    MirrorTruthLayer,
    RenderedOutput as FusionRenderedOutput,
)

from symbolu.mechanical.renderer.varna_hybrid_renderer import (
    VarnaHybridRenderer,
    HybridRenderMode,
    VarnaAnalysisResult,
    HybridRenderResult,
)

if TYPE_CHECKING:
    from symbolu.mechanical.pipeline.models import PipelineContext
    from symbolu.mechanical.hrm import HighResolutionMap
    from symbolu.mechanical.lam import LongArcMap
    from symbolu.mechanical.lcm import LowContextMap


# =============================================================================
# INTEGRATED OUTPUT STRUCTURE
# =============================================================================


@dataclass
class IntegratedRenderedOutput:
    """
    Integrated output from both FusionRenderer and VarnaHybridRenderer.

    Combines:
    - Structured layers from FusionRenderer (Symbolic/Practical/Mirror-Truth)
    - Phoneme analysis from VarnaHybridRenderer (Varṇa vectors, routing, attention)
    """

    # Core text output
    raw_text: str
    mode: str

    # FusionRenderer layers
    symbolic_layer: Optional[SymbolicLayer] = None
    practical_layer: Optional[PracticalLayer] = None
    mirror_truth_layer: Optional[MirrorTruthLayer] = None

    # VarnaHybridRenderer analysis
    varna_analysis: Optional[VarnaAnalysisResult] = None
    phoneme_routing: Optional[Dict[str, Any]] = None
    phoneme_harmony: float = 0.0

    # Mapper integration data
    mapper_summary: Optional[Dict[str, Any]] = None

    # Metadata and trace
    meta: Dict[str, Any] = field(default_factory=dict)
    render_timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API output."""
        return {
            "raw_text": self.raw_text,
            "mode": self.mode,
            "symbolic_layer": self.symbolic_layer.to_dict() if self.symbolic_layer else None,
            "practical_layer": self.practical_layer.to_dict() if self.practical_layer else None,
            "mirror_truth_layer": self.mirror_truth_layer.to_dict() if self.mirror_truth_layer else None,
            "varna_analysis": {
                "dominant_layer": self.varna_analysis.dominant_layer,
                "overall_harmony": self.varna_analysis.overall_harmony,
                "bridge_meanings": list(self.varna_analysis.bridge_meanings),
            } if self.varna_analysis else None,
            "phoneme_routing": self.phoneme_routing,
            "phoneme_harmony": self.phoneme_harmony,
            "mapper_summary": self.mapper_summary,
            "meta": self.meta,
            "render_timestamp": self.render_timestamp,
        }


# =============================================================================
# FUSION OUTPUT BUILDER
# =============================================================================


def build_fusion_output_from_context(
    ctx: "PipelineContext",
) -> FusionOutput:
    """
    Build FusionOutput from pipeline context.

    Extracts data from:
    - ctx.request (query)
    - ctx.fusion (fusion result)
    - ctx.dha (adapted text)
    - ctx.hrm_map, ctx.lam_map, ctx.lcm_map (mapper outputs)
    - ctx.mapper_summary (derived channel scores)

    Args:
        ctx: Pipeline context with populated stages.

    Returns:
        FusionOutput for FusionRenderer.
    """
    # Get query text
    query = ctx.request.text if hasattr(ctx, 'request') else ""

    # Get merged response from DHA
    merged_response = ""
    if hasattr(ctx, 'dha') and ctx.dha:
        merged_response = ctx.dha.guarded_text or ""

    # Build HRM content from hrm_map
    hrm_content: Dict[str, Any] = {}
    if hasattr(ctx, 'hrm_map') and ctx.hrm_map is not None:
        hrm_map = ctx.hrm_map
        hrm_content = {
            "dominant_aspects": hrm_map.dominant_aspects,
            "suppressed_aspects": hrm_map.suppressed_aspects,
            "conflict_zones": hrm_map.conflict_zones,
            "resolution_hints": hrm_map.resolution_hints,
            "entropy_profile": hrm_map.entropy_profile,
            "tier": hrm_map.tier,
            "domain": hrm_map.domain,
        }

    # Build LCM content from lcm_map
    lcm_content: Dict[str, Any] = {}
    if hasattr(ctx, 'lcm_map') and ctx.lcm_map is not None:
        lcm_map = ctx.lcm_map
        lcm_content = {
            "task_type": lcm_map.task_type,
            "key_terms": lcm_map.key_terms,
            "numeric_features": lcm_map.numeric_features,
            "complexity_score": lcm_map.complexity_score,
            "entropy_regime": lcm_map.entropy_regime,
            "recommended_engine": lcm_map.recommended_engine,
        }

    # Build MoE content from fusion and LAM
    moe_content: Dict[str, Any] = {}
    if hasattr(ctx, 'lam_map') and ctx.lam_map is not None:
        lam_map = ctx.lam_map
        moe_content = {
            "trajectory_summary": lam_map.trajectory_summary,
            "arc_state": lam_map.arc_state,
            "long_arc_signal": lam_map.long_arc_signal,
            "active_patterns": lam_map.active_patterns,
            "domain_transfers": lam_map.domain_transfers,
        }

    # Get channel weights from mapper_summary
    channel_weights = {"hrm": 0.4, "lcm": 0.3, "moe": 0.3}
    if hasattr(ctx, 'mapper_summary') and ctx.mapper_summary:
        scores = ctx.mapper_summary.get("channel_scores", {})
        if scores:
            channel_weights = {
                "hrm": scores.get("hrm", 0.4),
                "lcm": scores.get("lcm", 0.3),
                "moe": scores.get("moe", 0.3),
            }

    # Get conflict resolution from fusion
    conflict_resolution: List[Dict[str, Any]] = []
    if hasattr(ctx, 'fusion') and ctx.fusion:
        trace = ctx.fusion.trace if hasattr(ctx.fusion, 'trace') else {}
        if isinstance(trace, dict):
            conflict_resolution = trace.get("conflicts_resolved", [])

    # Build metadata
    metadata: Dict[str, Any] = {
        "pipeline_version": "3.1",
        "mapper_active": {
            "hrm": hasattr(ctx, 'hrm_map') and ctx.hrm_map is not None,
            "lam": hasattr(ctx, 'lam_map') and ctx.lam_map is not None,
            "lcm": hasattr(ctx, 'lcm_map') and ctx.lcm_map is not None,
        },
    }

    # Add MLCR metadata
    if hasattr(ctx, 'mlcr') and ctx.mlcr:
        explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
        meta = explain_log.get("meta", {})
        metadata["mlcr"] = {
            "tier": meta.get("tier"),
            "intent": meta.get("intent"),
            "domain": meta.get("domain"),
        }

    return FusionOutput(
        query=query,
        merged_response=merged_response,
        hrm_content=hrm_content,
        lcm_content=lcm_content,
        moe_content=moe_content,
        channel_weights=channel_weights,
        conflict_resolution=conflict_resolution,
        metadata=metadata,
    )


# =============================================================================
# RENDER MODE MAPPING
# =============================================================================


def get_render_mode(mode_str: str) -> RenderMode:
    """Map mode string to RenderMode enum."""
    mapping = {
        "minimal": RenderMode.MINIMAL,
        "standard": RenderMode.STANDARD,
        "enhanced": RenderMode.SYMBOLIC,
        "symbolic": RenderMode.SYMBOLIC,
        "regulated": RenderMode.REGULATED,
    }
    return mapping.get(mode_str, RenderMode.STANDARD)


def get_domain(domain_str: str) -> Domain:
    """Map domain string to Domain enum."""
    mapping = {
        "general": Domain.GENERAL,
        "generic": Domain.GENERAL,
        "finance": Domain.FINANCE,
        "financial": Domain.FINANCE,
        "trading": Domain.FINANCE,
        "medical": Domain.MEDICAL,
        "legal": Domain.LEGAL,
        "education": Domain.EDUCATION,
        "psychology": Domain.PSYCHOLOGY,
        "therapy": Domain.PSYCHOLOGY,
    }
    return mapping.get(domain_str.lower(), Domain.GENERAL)


def get_hybrid_mode(mode_str: str) -> HybridRenderMode:
    """Map mode string to HybridRenderMode."""
    mapping = {
        "minimal": HybridRenderMode.PHONEME_ONLY,
        "standard": HybridRenderMode.HYBRID_FAST,
        "enhanced": HybridRenderMode.HYBRID_FULL,
        "symbolic": HybridRenderMode.HYBRID_FULL,
        "regulated": HybridRenderMode.HYBRID_FAST,
    }
    return mapping.get(mode_str, HybridRenderMode.HYBRID_FAST)


# =============================================================================
# MAIN INTEGRATION FUNCTION
# =============================================================================


def run_integrated_renderer(
    ctx: "PipelineContext",
) -> IntegratedRenderedOutput:
    """
    Run the integrated rendering pipeline.

    Combines:
    1. FusionRenderer for structured layer output
    2. VarnaHybridRenderer for phoneme analysis and optimization

    Args:
        ctx: Pipeline context with all stages populated.

    Returns:
        IntegratedRenderedOutput with both structured layers and phoneme analysis.
    """
    # Get render configuration
    render_mode_str = ctx.request.render_mode if hasattr(ctx.request, 'render_mode') else "standard"
    render_mode_str = render_mode_str or "standard"

    # Get domain
    domain_str = "general"
    if hasattr(ctx, 'mlcr') and ctx.mlcr:
        explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
        domain_str = explain_log.get("meta", {}).get("domain", "general")

    # Build FusionOutput from context
    fusion_output = build_fusion_output_from_context(ctx)

    # Get the text to render
    text = fusion_output.merged_response or fusion_output.query

    # ==========================================================================
    # STAGE 1: FusionRenderer - Structured Layers
    # ==========================================================================
    fusion_renderer = FusionRenderer(
        mode=get_render_mode(render_mode_str),
        domain=get_domain(domain_str),
    )

    try:
        fusion_result = fusion_renderer.render(fusion_output)
        symbolic_layer = fusion_result.symbolic_layer
        practical_layer = fusion_result.practical_layer
        mirror_truth_layer = fusion_result.mirror_truth_layer
    except Exception:
        # Fallback if FusionRenderer fails
        symbolic_layer = None
        practical_layer = None
        mirror_truth_layer = None

    # ==========================================================================
    # STAGE 2: VarnaHybridRenderer - Phoneme Analysis
    # ==========================================================================
    varna_renderer = VarnaHybridRenderer()

    try:
        # Analyze with Varṇa
        varna_analysis = varna_renderer.analyze_varna(text)

        # Get routing decision
        routing_decision = varna_renderer.route_query(text)

        phoneme_routing = {
            "model_type": routing_decision.model_type.value,
            "confidence": routing_decision.confidence,
            "dominant_layer": routing_decision.dominant_layer,
            "explanation": routing_decision.explanation,
        }

        phoneme_harmony = varna_analysis.overall_harmony

    except Exception:
        # Fallback if VarnaHybridRenderer fails
        varna_analysis = None
        phoneme_routing = None
        phoneme_harmony = 0.0

    # ==========================================================================
    # STAGE 3: Build Integrated Output
    # ==========================================================================

    # Build output metadata
    output_meta: Dict[str, Any] = {
        "persona_id": ctx.persona.active_persona_id if hasattr(ctx, 'persona') and ctx.persona else None,
        "tone_profile": ctx.dha.tone_profile if hasattr(ctx, 'dha') and ctx.dha else None,
        "readiness_level": ctx.dha.readiness_level if hasattr(ctx, 'dha') and ctx.dha else None,
        "router_mode": ctx.router_mode if hasattr(ctx, 'router_mode') else None,
        "pipeline_version": "3.1",
        "renderers_used": {
            "fusion_renderer": symbolic_layer is not None or practical_layer is not None,
            "varna_hybrid_renderer": varna_analysis is not None,
        },
    }

    # Add MLCR trace
    if hasattr(ctx, 'mlcr') and ctx.mlcr:
        explain_log = ctx.mlcr.explain_log if hasattr(ctx.mlcr, 'explain_log') else {}
        output_meta["mlcr_tier"] = explain_log.get("meta", {}).get("tier")
        output_meta["mlcr_intent"] = explain_log.get("meta", {}).get("intent")

    # Get mapper summary
    mapper_summary = None
    if hasattr(ctx, 'mapper_summary'):
        mapper_summary = ctx.mapper_summary

    return IntegratedRenderedOutput(
        raw_text=text,
        mode=render_mode_str,
        symbolic_layer=symbolic_layer,
        practical_layer=practical_layer,
        mirror_truth_layer=mirror_truth_layer,
        varna_analysis=varna_analysis,
        phoneme_routing=phoneme_routing,
        phoneme_harmony=phoneme_harmony,
        mapper_summary=mapper_summary,
        meta=output_meta,
    )


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================


def create_legacy_rendered_output(
    integrated: IntegratedRenderedOutput,
) -> Dict[str, Any]:
    """
    Convert IntegratedRenderedOutput to legacy RenderedOutput format.

    For backward compatibility with existing code that expects
    the simpler RenderedOutput structure.

    Args:
        integrated: IntegratedRenderedOutput from run_integrated_renderer.

    Returns:
        Dictionary compatible with legacy RenderedOutput.
    """
    return {
        "raw_text": integrated.raw_text,
        "mode": integrated.mode,
        "meta": integrated.meta,
    }


__all__ = [
    "IntegratedRenderedOutput",
    "run_integrated_renderer",
    "build_fusion_output_from_context",
    "create_legacy_rendered_output",
]
