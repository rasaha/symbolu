"""
Candidate Generation Helpers for Pipeline Orchestrator

Extracted from orchestrator.py to reduce complexity.
Handles candidate generation for fusion stage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from .models import PipelineContext

# Fusion schemas
from symbolu.mechanical.fusion.schemas.candidate import Candidate, CandidateSource
from symbolu.mechanical.fusion.schemas.fusion_result import FusionContext

# Mapper-Fusion Adapter
from .mapper_fusion_adapter import create_candidates_from_mappers, get_mapper_summary

# RAG Integration
try:
    from .rag_hybrid_integration import get_fusion_candidates, HAS_RAG
    RAG_AVAILABLE = HAS_RAG
except ImportError:
    RAG_AVAILABLE = False
    get_fusion_candidates = None


def generate_candidates(
    ctx: "PipelineContext",
    explain_log: Dict[str, Any],
    fusion_engine: Any,
) -> List[Candidate]:
    """
    Generate candidates for fusion.

    Integrates RAG retrieval with mapper outputs (HRM/LAM/LCM) to create
    candidates with properly derived channel scores.

    Args:
        ctx: Pipeline context.
        explain_log: MLCR explain log.
        fusion_engine: Fusion engine instance.

    Returns:
        List of Candidate objects for fusion.
    """
    query_text = ctx.request.text
    domain = explain_log.get("meta", {}).get("domain", "general")

    # Get mapper outputs from context
    hrm_map = getattr(ctx, 'hrm_map', None)
    lam_map = getattr(ctx, 'lam_map', None)
    lcm_map = getattr(ctx, 'lcm_map', None)

    # Create candidates from mapper outputs
    candidates = create_candidates_from_mappers(
        text=query_text,
        domain=domain,
        hrm_map=hrm_map,
        lam_map=lam_map,
        lcm_map=lcm_map,
    )

    # Integrate RAG candidates if available
    rag_candidates = _get_rag_candidates(ctx, query_text, domain)
    if rag_candidates:
        candidates.extend(rag_candidates)
        ctx.rag_stats = {"enabled": True, "candidate_count": len(rag_candidates)}
    else:
        ctx.rag_stats = {"enabled": False, "candidate_count": 0}

    # Store mapper summary for observability
    ctx.mapper_summary = get_mapper_summary(hrm_map, lam_map, lcm_map)

    return candidates


def _get_rag_candidates(
    ctx: "PipelineContext",
    query_text: str,
    domain: str,
) -> List[Candidate]:
    """Get candidates from RAG retrieval."""
    if not RAG_AVAILABLE or get_fusion_candidates is None:
        return []

    request_metadata = getattr(ctx.request, 'metadata', {}) or {}
    rag_enabled = request_metadata.get('use_rag', True)
    corpus_ids = request_metadata.get('corpus_ids', None)

    if not rag_enabled:
        return []

    try:
        rag_candidates = get_fusion_candidates(
            query=query_text,
            corpus_ids=corpus_ids,
            domain=domain,
            top_k=5,
        )
        return list(rag_candidates)
    except Exception as e:
        ctx.rag_stats = {"enabled": True, "error": str(e)}
        return []


def create_fallback_fusion(ctx: "PipelineContext", fusion_engine: Any) -> Any:
    """Create minimal fusion result when no candidates available."""
    fallback_candidate = Candidate(
        id="fallback_001",
        text=ctx.request.text,
        source=CandidateSource.TEMPLATE,
        channel_scores={"hrm": 0.33, "lcm": 0.34, "moe": 0.33},
    )

    fallback_ctx = FusionContext(
        tier="HYBRID",
        intent="WHAT",
        domain="general",
        entropy={"H_D": 0.5, "H_G": 0.5, "H_K": 0.5},
        ontology_mass={"lower": 0.5, "upper": 0.5},
    )

    return fusion_engine.fuse([fallback_candidate], fallback_ctx)


def extract_text_for_dha(ctx: "PipelineContext") -> str:
    """Extract text to be adapted by DHA."""
    if ctx.fusion and ctx.fusion.selected_text:
        return ctx.fusion.selected_text
    return ctx.request.text
