"""
Mapper-Fusion Adapter Module

Bridges the gap between HRM/LAM/LCM mapper outputs and the Fusion engine.
This module converts structured mapper outputs into fusion-compatible candidates
with proper channel scores derived from actual mapper analysis.

Integration Points:
    - HRM → hrm channel scores (from resolution_hints, conflict_zones, entropy_profile)
    - LAM → temporal weighting (from long_arc_signal, trajectory, arc_state)
    - LCM → lcm channel scores (from complexity_score, task_type, recommended_engine)

Usage:
    from .mapper_fusion_adapter import create_candidates_from_mappers

    # In orchestrator._generate_candidates()
    candidates = create_candidates_from_mappers(
        ctx=ctx,
        hrm_map=ctx.hrm_map,
        lam_map=ctx.lam_map,
        lcm_map=ctx.lcm_map,
    )
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

from symbolu_core.mechanical.fusion.schemas.candidate import Candidate, CandidateSource
from symbolu_core.mechanical.hrm import HighResolutionMap
from symbolu_core.mechanical.lam import LongArcMap
from symbolu_core.mechanical.lcm import LowContextMap


# =============================================================================
# CHANNEL SCORE COMPUTATION FROM MAPPER OUTPUTS
# =============================================================================


def compute_hrm_channel_score(hrm_map: Optional[HighResolutionMap]) -> float:
    """
    Compute HRM channel score from HighResolutionMap.

    The HRM channel score is derived from:
    - Resolution hints count and types (symbolic depth indicators)
    - Conflict zone presence (meaning-seeking signals)
    - Entropy regime (high entropy → higher HRM relevance)
    - Tier (upper tier → higher HRM relevance)

    Args:
        hrm_map: HighResolutionMap from HRM engine, or None.

    Returns:
        HRM channel score in [0.0, 1.0].
    """
    if hrm_map is None:
        return 0.5  # Default middle score when HRM wasn't run

    score = 0.5  # Base score

    # Resolution hints boost (symbolic depth)
    if hrm_map.resolution_hints:
        # Upper-tier hints boost HRM
        upper_hints = [
            h for h in hrm_map.resolution_hints
            if any(kw in h for kw in [
                "meaning", "purpose", "deep", "symbolic",
                "reflective", "introspective", "philosophical"
            ])
        ]
        score += len(upper_hints) * 0.05
        score = min(score, 1.0)

    # Conflict zones boost (active meaning-seeking)
    if hrm_map.conflict_zones:
        # More conflicts → more need for HRM-style resolution
        score += min(len(hrm_map.conflict_zones) * 0.08, 0.25)

    # Entropy regime modulation
    entropy_profile = hrm_map.entropy_profile
    regime = entropy_profile.get("regime", "medium")
    if regime == "high":
        score += 0.15  # High entropy → need deeper reasoning
    elif regime == "low":
        score -= 0.1   # Low entropy → less need for abstraction

    # Tier modulation
    if hrm_map.tier == "upper":
        score += 0.15
    elif hrm_map.tier == "lower":
        score -= 0.1

    return max(0.0, min(1.0, score))


def compute_lcm_channel_score(lcm_map: Optional[LowContextMap]) -> float:
    """
    Compute LCM channel score from LowContextMap.

    The LCM channel score is derived from:
    - Task type (code/math/lookup → higher LCM)
    - Complexity score (lower complexity → higher LCM)
    - Recommended engine (renderer_only/fusion → higher LCM)

    Args:
        lcm_map: LowContextMap from LCM engine, or None.

    Returns:
        LCM channel score in [0.0, 1.0].
    """
    if lcm_map is None:
        return 0.5  # Default middle score when LCM wasn't run

    score = 0.5  # Base score

    # Task type modulation
    task_type = lcm_map.task_type
    if task_type in ("code", "math", "lookup", "action"):
        score += 0.2  # Concrete tasks favor LCM
    elif task_type == "generic":
        score += 0.05

    # Complexity modulation (lower complexity → clearer semantic task)
    complexity = lcm_map.complexity_score
    if complexity < 0.3:
        score += 0.15  # Simple query → LCM handles well
    elif complexity > 0.7:
        score -= 0.1   # Complex query → might need HRM

    # Recommended engine modulation
    engine = lcm_map.recommended_engine
    if engine == "renderer_only":
        score += 0.2  # Direct rendering → strong LCM
    elif engine == "fusion":
        score += 0.1
    elif engine == "persona":
        score -= 0.05  # Conversational → less structural

    return max(0.0, min(1.0, score))


def compute_temporal_weight(lam_map: Optional[LongArcMap]) -> float:
    """
    Compute temporal weighting factor from LongArcMap.

    The temporal weight modulates fusion behavior based on:
    - Long arc signal (overall temporal dynamics strength)
    - Arc state (tension/recovery/turning_point → higher weight)
    - Trajectory confidence (stronger trajectory → more temporal influence)

    Args:
        lam_map: LongArcMap from LAM engine, or None.

    Returns:
        Temporal weight in [0.0, 1.0].
    """
    if lam_map is None:
        return 0.0  # No temporal influence when LAM wasn't run

    weight = 0.0

    # Base from long_arc_signal (primary temporal indicator)
    weight = lam_map.long_arc_signal * 0.5

    # Arc state modulation
    arc_state = lam_map.arc_state
    if arc_state == "tension":
        weight += 0.25  # High tension → temporal dynamics matter more
    elif arc_state == "recovery":
        weight += 0.2   # Recovery → trajectory matters
    elif arc_state == "turning_point":
        weight += 0.3   # Breakthrough potential → pay attention
    # "steady" adds nothing

    # Trajectory confidence boost
    trajectory = lam_map.trajectory_summary
    confidence = trajectory.get("confidence", 0.0)
    if confidence > 0.5:
        weight += confidence * 0.2

    return max(0.0, min(1.0, weight))


def compute_moe_channel_score(
    hrm_map: Optional[HighResolutionMap],
    lcm_map: Optional[LowContextMap],
    domain: str,
) -> float:
    """
    Compute MoE (Mixture of Experts) channel score.

    MoE score is high when:
    - Domain is specialized (medical, legal, financial, code, math)
    - LCM detected a domain-specific task type
    - HRM has domain-specific resolution hints

    Args:
        hrm_map: HighResolutionMap from HRM engine, or None.
        lcm_map: LowContextMap from LCM engine, or None.
        domain: Domain classification from MLCR.

    Returns:
        MoE channel score in [0.0, 1.0].
    """
    score = 0.4  # Base score

    # Domain specialization boost
    specialized_domains = {
        "medical": 0.3,
        "legal": 0.3,
        "financial": 0.3,
        "trading": 0.25,
        "therapy": 0.2,
        "code": 0.25,
        "math": 0.25,
        "philosophy": 0.15,
        "spiritual": 0.15,
    }

    domain_boost = specialized_domains.get(domain.lower(), 0.0)
    score += domain_boost

    # LCM task type specialization
    if lcm_map and lcm_map.task_type in ("code", "math"):
        score += 0.1

    # HRM domain hints
    if hrm_map and hrm_map.domain in specialized_domains:
        score += 0.1

    return max(0.0, min(1.0, score))


# =============================================================================
# CANDIDATE GENERATION FROM MAPPER OUTPUTS
# =============================================================================


def create_hrm_candidate(
    text: str,
    hrm_map: HighResolutionMap,
    hrm_score: float,
    lcm_score: float,
    moe_score: float,
    domain: str,
) -> Candidate:
    """
    Create a candidate from HRM mapper output.

    The candidate text is enriched with HRM resolution hints
    and conflict zone awareness.

    Args:
        text: Original query text.
        hrm_map: HighResolutionMap from HRM engine.
        hrm_score: Computed HRM channel score.
        lcm_score: Computed LCM channel score.
        moe_score: Computed MoE channel score.
        domain: Domain classification.

    Returns:
        Candidate with HRM-derived channel scores.
    """
    # Build enriched text from HRM analysis
    dominant = hrm_map.dominant_aspects[:3] if hrm_map.dominant_aspects else []
    conflicts = hrm_map.conflict_zones[:2] if hrm_map.conflict_zones else []

    enrichment = []
    if dominant:
        enrichment.append(f"[Focus: {', '.join(dominant)}]")
    if conflicts:
        enrichment.append(f"[Tension: {', '.join(conflicts)}]")

    enriched_text = f"{' '.join(enrichment)} {text}".strip()

    # Compute confidence from entropy profile
    entropy_mix = hrm_map.entropy_profile.get("entropy_mix", 0.5)
    confidence = 1.0 - entropy_mix  # Lower entropy → higher confidence

    return Candidate(
        id=f"hrm_{uuid.uuid4().hex[:8]}",
        text=enriched_text,
        source=CandidateSource.HRM,
        channel_scores={
            "hrm": hrm_score,
            "lcm": lcm_score * 0.6,  # HRM candidate has reduced LCM affinity
            "moe": moe_score,
        },
        domain=domain,
        relevance_score=0.8,
        confidence=confidence,
    )


def create_lcm_candidate(
    text: str,
    lcm_map: LowContextMap,
    hrm_score: float,
    lcm_score: float,
    moe_score: float,
    domain: str,
) -> Candidate:
    """
    Create a candidate from LCM mapper output.

    The candidate text is focused on clarity and concrete task handling.

    Args:
        text: Original query text.
        lcm_map: LowContextMap from LCM engine.
        hrm_score: Computed HRM channel score.
        lcm_score: Computed LCM channel score.
        moe_score: Computed MoE channel score.
        domain: Domain classification.

    Returns:
        Candidate with LCM-derived channel scores.
    """
    # Build task-focused text
    task_type = lcm_map.task_type
    key_terms = lcm_map.key_terms[:5] if lcm_map.key_terms else []

    prefix = {
        "code": "[Code Task]",
        "math": "[Math Task]",
        "lookup": "[Lookup]",
        "action": "[Action]",
        "generic": "",
    }.get(task_type, "")

    enriched_text = f"{prefix} {text}".strip()

    # Confidence based on complexity (simpler → more confident)
    confidence = 1.0 - lcm_map.complexity_score * 0.5

    return Candidate(
        id=f"lcm_{uuid.uuid4().hex[:8]}",
        text=enriched_text,
        source=CandidateSource.LCM,
        channel_scores={
            "hrm": hrm_score * 0.5,  # LCM candidate has reduced HRM affinity
            "lcm": lcm_score,
            "moe": moe_score,
        },
        domain=domain,
        relevance_score=0.75,
        confidence=confidence,
    )


def create_lam_candidate(
    text: str,
    lam_map: LongArcMap,
    temporal_weight: float,
    hrm_score: float,
    lcm_score: float,
    moe_score: float,
    domain: str,
) -> Candidate:
    """
    Create a candidate from LAM mapper output.

    The candidate incorporates temporal context and trajectory awareness.

    Args:
        text: Original query text.
        lam_map: LongArcMap from LAM engine.
        temporal_weight: Computed temporal weighting factor.
        hrm_score: Computed HRM channel score.
        lcm_score: Computed LCM channel score.
        moe_score: Computed MoE channel score.
        domain: Domain classification.

    Returns:
        Candidate with temporal-aware channel scores.
    """
    # Build trajectory-aware text
    arc_state = lam_map.arc_state
    trajectory = lam_map.trajectory_summary
    trend = trajectory.get("trend", "stable")

    arc_prefix = {
        "tension": "[Tension Phase]",
        "recovery": "[Recovery Phase]",
        "turning_point": "[Turning Point]",
        "steady": "",
    }.get(arc_state, "")

    trend_suffix = {
        "rising": "(momentum ↑)",
        "falling": "(momentum ↓)",
        "stable": "",
    }.get(trend, "")

    enriched_text = f"{arc_prefix} {text} {trend_suffix}".strip()

    # Compute confidence from long_arc_signal
    confidence = 0.5 + lam_map.long_arc_signal * 0.4

    # LAM modulates all channel scores by temporal weight
    return Candidate(
        id=f"lam_{uuid.uuid4().hex[:8]}",
        text=enriched_text,
        source=CandidateSource.RAG,  # Using RAG as temporal source marker
        channel_scores={
            "hrm": hrm_score * (1.0 + temporal_weight * 0.2),
            "lcm": lcm_score * (1.0 - temporal_weight * 0.1),
            "moe": moe_score,
        },
        domain=domain,
        relevance_score=0.7 + temporal_weight * 0.2,
        confidence=confidence,
    )


def create_moe_candidate(
    text: str,
    hrm_score: float,
    lcm_score: float,
    moe_score: float,
    domain: str,
) -> Candidate:
    """
    Create a domain-expert (MoE) candidate.

    Args:
        text: Original query text.
        hrm_score: Computed HRM channel score.
        lcm_score: Computed LCM channel score.
        moe_score: Computed MoE channel score.
        domain: Domain classification.

    Returns:
        Candidate with domain-expert channel scores.
    """
    domain_prefix = {
        "medical": "[Medical Context]",
        "legal": "[Legal Context]",
        "financial": "[Financial Context]",
        "trading": "[Trading Context]",
        "therapy": "[Therapeutic Context]",
        "code": "[Technical Context]",
        "math": "[Mathematical Context]",
        "philosophy": "[Philosophical Context]",
        "spiritual": "[Spiritual Context]",
    }.get(domain.lower(), "[Domain Expert]")

    enriched_text = f"{domain_prefix} {text}"

    return Candidate(
        id=f"moe_{uuid.uuid4().hex[:8]}",
        text=enriched_text,
        source=CandidateSource.MOE,
        channel_scores={
            "hrm": hrm_score,
            "lcm": lcm_score,
            "moe": moe_score,
        },
        domain=domain,
        relevance_score=0.7,
        confidence=0.75,
    )


# =============================================================================
# MAIN INTEGRATION FUNCTION
# =============================================================================


def create_candidates_from_mappers(
    text: str,
    domain: str,
    hrm_map: Optional[HighResolutionMap] = None,
    lam_map: Optional[LongArcMap] = None,
    lcm_map: Optional[LowContextMap] = None,
) -> List[Candidate]:
    """
    Create fusion candidates from mapper outputs.

    This is the main integration function that bridges HRM/LAM/LCM
    outputs to the Fusion engine's candidate system.

    When mappers weren't run (None), default scores are used.
    When mappers were run, their outputs drive the channel scores.

    Args:
        text: Original query text.
        domain: Domain classification from MLCR.
        hrm_map: HighResolutionMap from HRM engine, or None.
        lam_map: LongArcMap from LAM engine, or None.
        lcm_map: LowContextMap from LCM engine, or None.

    Returns:
        List of Candidates with mapper-derived channel scores.
    """
    candidates: List[Candidate] = []

    # Compute channel scores from mapper outputs
    hrm_score = compute_hrm_channel_score(hrm_map)
    lcm_score = compute_lcm_channel_score(lcm_map)
    moe_score = compute_moe_channel_score(hrm_map, lcm_map, domain)
    temporal_weight = compute_temporal_weight(lam_map)

    # Create candidates based on which mappers were run
    if hrm_map is not None:
        hrm_candidate = create_hrm_candidate(
            text, hrm_map, hrm_score, lcm_score, moe_score, domain
        )
        candidates.append(hrm_candidate)

    if lcm_map is not None:
        lcm_candidate = create_lcm_candidate(
            text, lcm_map, hrm_score, lcm_score, moe_score, domain
        )
        candidates.append(lcm_candidate)

    if lam_map is not None:
        lam_candidate = create_lam_candidate(
            text, lam_map, temporal_weight, hrm_score, lcm_score, moe_score, domain
        )
        candidates.append(lam_candidate)

    # Always add MoE candidate for domain expertise
    moe_candidate = create_moe_candidate(
        text, hrm_score, lcm_score, moe_score, domain
    )
    candidates.append(moe_candidate)

    # If no mappers were run, add default synthetic candidates
    if not candidates or (hrm_map is None and lcm_map is None and lam_map is None):
        # Add fallback HRM-style candidate
        candidates.append(Candidate(
            id=f"hrm_fallback_{uuid.uuid4().hex[:8]}",
            text=f"From a deeper perspective: {text}",
            source=CandidateSource.HRM,
            channel_scores={"hrm": 0.8, "lcm": 0.4, "moe": 0.3},
            domain=domain,
            relevance_score=0.7,
            confidence=0.8,
        ))

        # Add fallback LCM-style candidate
        candidates.append(Candidate(
            id=f"lcm_fallback_{uuid.uuid4().hex[:8]}",
            text=f"To clarify: {text}",
            source=CandidateSource.LCM,
            channel_scores={"hrm": 0.3, "lcm": 0.9, "moe": 0.4},
            domain=domain,
            relevance_score=0.75,
            confidence=0.85,
        ))

    return candidates


# =============================================================================
# MAPPER STATUS SUMMARY
# =============================================================================


def get_mapper_summary(
    hrm_map: Optional[HighResolutionMap] = None,
    lam_map: Optional[LongArcMap] = None,
    lcm_map: Optional[LowContextMap] = None,
) -> Dict[str, Any]:
    """
    Get a summary of mapper status and key outputs for tracing.

    Args:
        hrm_map: HighResolutionMap from HRM engine, or None.
        lam_map: LongArcMap from LAM engine, or None.
        lcm_map: LowContextMap from LCM engine, or None.

    Returns:
        Dictionary with mapper status and key metrics.
    """
    summary: Dict[str, Any] = {
        "hrm_active": hrm_map is not None,
        "lam_active": lam_map is not None,
        "lcm_active": lcm_map is not None,
    }

    if hrm_map:
        summary["hrm"] = {
            "dominant_aspects": hrm_map.dominant_aspects[:3],
            "conflict_zones": hrm_map.conflict_zones,
            "entropy_regime": hrm_map.entropy_profile.get("regime"),
            "tier": hrm_map.tier,
            "resolution_hint_count": len(hrm_map.resolution_hints),
        }

    if lam_map:
        summary["lam"] = {
            "arc_state": lam_map.arc_state,
            "long_arc_signal": lam_map.long_arc_signal,
            "trajectory_trend": lam_map.trajectory_summary.get("trend"),
            "active_patterns": lam_map.active_patterns,
        }

    if lcm_map:
        summary["lcm"] = {
            "task_type": lcm_map.task_type,
            "complexity_score": lcm_map.complexity_score,
            "recommended_engine": lcm_map.recommended_engine,
            "entropy_regime": lcm_map.entropy_regime,
        }

    # Compute derived scores
    summary["channel_scores"] = {
        "hrm": compute_hrm_channel_score(hrm_map),
        "lcm": compute_lcm_channel_score(lcm_map),
        "moe": compute_moe_channel_score(hrm_map, lcm_map, "generic"),
        "temporal_weight": compute_temporal_weight(lam_map),
    }

    return summary


__all__ = [
    "create_candidates_from_mappers",
    "get_mapper_summary",
    "compute_hrm_channel_score",
    "compute_lcm_channel_score",
    "compute_moe_channel_score",
    "compute_temporal_weight",
]
