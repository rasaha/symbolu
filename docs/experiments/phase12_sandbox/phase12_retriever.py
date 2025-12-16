"""
Phase-12: Template Retriever
============================

This module implements deterministic template retrieval for few-shot context.

Architecture:
    Query (family, signature, slot_plan)
           ↓
    Phase-11B.3 Registry
           ↓
    Template Selection (deterministic)
           ↓
    Similarity Scoring (deterministic)
           ↓
    FewShotContext

INVARIANT:
    Retrieval is deterministic.
    Same (family, signature, slot_plan) → identical templates.

INTEGRATION:
    Uses Phase-11B.3's lazy template registry for template lookup.
    Templates become few-shot examples, not direct output.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add phase11_sandbox to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "phase11_sandbox"))

from phase12_schema import (
    CANONICAL_SUBBANDS,
    FewShotContext,
    OntologicalFamily,
    RetrievedTemplate,
    TemplateRetriever,
)


# =============================================================================
# Similarity Calculation
# =============================================================================

def _signature_similarity(sig1: str, sig2: str) -> float:
    """
    Calculate similarity between two canonical signatures.

    Uses Hamming-like distance: count matching subbands.

    Returns:
        float: Similarity score in [0, 1]
    """
    parts1 = sig1.split("_")
    parts2 = sig2.split("_")

    if len(parts1) != len(parts2):
        return 0.0

    matches = sum(1 for p1, p2 in zip(parts1, parts2) if p1 == p2)
    return matches / len(parts1)


def _band_similarity(sig1: str, sig2: str) -> float:
    """
    Calculate coarse band similarity (L/M/H match, ignoring subband).

    Returns:
        float: Similarity score in [0, 1]
    """
    parts1 = sig1.split("_")
    parts2 = sig2.split("_")

    if len(parts1) != len(parts2):
        return 0.0

    matches = sum(
        1 for p1, p2 in zip(parts1, parts2)
        if p1[0] == p2[0]  # Compare first char (L, M, or H)
    )
    return matches / len(parts1)


def calculate_template_similarity(
    query_signature: str,
    query_slot_plan: str,
    template_signature: str,
    template_slot_plan: str,
) -> float:
    """
    Calculate overall similarity between query and template.

    Combines:
        - Signature similarity (subband match): 60% weight
        - Band similarity (coarse match): 20% weight
        - Slot plan match: 20% weight

    Returns:
        float: Combined similarity score in [0, 1]
    """
    sig_sim = _signature_similarity(query_signature, template_signature)
    band_sim = _band_similarity(query_signature, template_signature)
    slot_match = 1.0 if query_slot_plan == template_slot_plan else 0.0

    return sig_sim * 0.6 + band_sim * 0.2 + slot_match * 0.2


# =============================================================================
# Template Generation for Retrieval
# =============================================================================

def _generate_template_text(
    family: OntologicalFamily,
    signature: str,
    slot_plan: str,
) -> str:
    """
    Generate template text for a given family/signature/slot_plan.

    This is a simplified version - in production, would fetch from
    Phase-11B.3 registry or a more sophisticated template store.
    """
    # Determine energy level from signature
    parts = signature.split("_")
    low_count = sum(1 for p in parts if p.startswith("L"))
    mid_count = sum(1 for p in parts if p.startswith("M"))
    high_count = sum(1 for p in parts if p.startswith("H"))

    if high_count >= low_count and high_count >= mid_count:
        energy = "high"
        energy_words = "boldly, powerfully, intensely"
    elif low_count >= mid_count:
        energy = "low"
        energy_words = "quietly, gently, calmly"
    else:
        energy = "mid"
        energy_words = "steadily, reasonably, moderately"

    # Generate family-specific template
    templates = {
        OntologicalFamily.THINKING: (
            f"[{energy.upper()} energy thinking]\n"
            f"I {energy_words} consider and reflect on {{observation}}. "
            f"Perhaps we might think about this more deeply."
        ),
        OntologicalFamily.FORMING: (
            f"[{energy.upper()} energy forming]\n"
            f"Let us {energy_words} create and build from {{observation}}. "
            f"We can shape and design something meaningful."
        ),
        OntologicalFamily.ACTING: (
            f"[{energy.upper()} energy acting]\n"
            f"We {energy_words} act and perform on {{observation}}. "
            f"Let us execute and implement this vision."
        ),
        OntologicalFamily.TAGGING: (
            f"[{energy.upper()} energy tagging]\n"
            f"We {energy_words} label and identify {{observation}}. "
            f"This classifies and categorizes clearly."
        ),
        OntologicalFamily.DIRECTING: (
            f"[{energy.upper()} energy directing]\n"
            f"Let us {energy_words} guide and direct based on {{observation}}. "
            f"We navigate and orient toward our goal."
        ),
        OntologicalFamily.REASONING: (
            f"[{energy.upper()} energy reasoning]\n"
            f"Because of {{observation}}, we {energy_words} conclude. "
            f"Therefore, the logic leads us here."
        ),
        OntologicalFamily.PURPOSING: (
            f"[{energy.upper()} energy purposing]\n"
            f"Our purpose {energy_words} emerges from {{observation}}. "
            f"The goal and intention become clear."
        ),
        OntologicalFamily.META_OBSERVING: (
            f"[{energy.upper()} energy observing]\n"
            f"We {energy_words} observe and perceive {{observation}}. "
            f"Notice how this reveals itself."
        ),
        OntologicalFamily.UNIFYING: (
            f"[{energy.upper()} energy unifying]\n"
            f"Let us {energy_words} unite and integrate {{observation}}. "
            f"We synthesize and harmonize these elements."
        ),
        OntologicalFamily.ABSOLVING: (
            f"[{energy.upper()} energy absolving]\n"
            f"We {energy_words} release and accept {{observation}}. "
            f"Let go and allow this to be."
        ),
    }

    return templates.get(family, f"[Template for {family.value}]: {{observation}}")


def _generate_template_id(
    family: OntologicalFamily,
    signature: str,
    slot_plan: str,
) -> str:
    """Generate deterministic template ID."""
    content = f"{family.value}|{signature}|{slot_plan}"
    return f"tpl_{hashlib.sha256(content.encode()).hexdigest()[:12]}"


# =============================================================================
# Candidate Generation
# =============================================================================

def _generate_candidates(
    family: OntologicalFamily,
    target_signature: str,
    slot_plan: str,
    num_candidates: int = 20,
) -> List[Tuple[str, str]]:
    """
    Generate candidate (signature, slot_plan) tuples for retrieval.

    Strategy:
        1. Include exact match
        2. Include variations with single-subband changes
        3. Include variations with band-level changes
        4. Ensure deterministic ordering

    Returns:
        List of (signature, slot_plan) tuples
    """
    candidates = []

    # 1. Exact match first
    candidates.append((target_signature, slot_plan))

    # 2. Single subband variations
    parts = target_signature.split("_")
    for i in range(len(parts)):
        for subband in CANONICAL_SUBBANDS:
            if subband != parts[i]:
                new_parts = list(parts)
                new_parts[i] = subband
                new_sig = "_".join(new_parts)
                candidates.append((new_sig, slot_plan))

    # 3. Different slot plans (if applicable)
    slot_plans = ["basic_vc", "extended_vc", "minimal_vc"]
    for sp in slot_plans:
        if sp != slot_plan:
            candidates.append((target_signature, sp))

    # Deduplicate while preserving order
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    return unique_candidates[:num_candidates]


# =============================================================================
# Phase12 Template Retriever Implementation
# =============================================================================

@dataclass
class Phase12TemplateRetriever:
    """
    Deterministic template retriever for Phase-12.

    INVARIANT: Same inputs → same retrieved templates.

    Uses Phase-11B.3 template structure but generates templates
    dynamically for few-shot context.
    """

    # Default number of candidates to consider
    num_candidates: int = 20

    # Cache for retrieved templates (for efficiency, not correctness)
    _cache: Dict[Tuple, Tuple[RetrievedTemplate, ...]] = field(
        default_factory=dict
    )

    def retrieve(
        self,
        family: OntologicalFamily,
        canonical_signature: str,
        slot_plan: str,
        top_k: int = 5,
    ) -> Tuple[RetrievedTemplate, ...]:
        """
        Retrieve templates similar to the query.

        Args:
            family: Ontological family
            canonical_signature: Canonical PPV signature
            slot_plan: Slot plan identifier
            top_k: Maximum number of templates to return

        Returns:
            Tuple of RetrievedTemplate, ordered by similarity (descending)
        """
        # Check cache
        cache_key = (family, canonical_signature, slot_plan, top_k)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Generate candidates
        candidates = _generate_candidates(
            family,
            canonical_signature,
            slot_plan,
            self.num_candidates,
        )

        # Score and create templates
        scored_templates: List[Tuple[float, RetrievedTemplate]] = []

        for cand_sig, cand_slot in candidates:
            similarity = calculate_template_similarity(
                canonical_signature,
                slot_plan,
                cand_sig,
                cand_slot,
            )

            template = RetrievedTemplate(
                template_id=_generate_template_id(family, cand_sig, cand_slot),
                template_text=_generate_template_text(family, cand_sig, cand_slot),
                similarity_score=similarity,
                family=family.value,
                variant_id=cand_sig,
                slot_plan=cand_slot,
            )

            scored_templates.append((similarity, template))

        # Sort by similarity (descending) - use template_id as tiebreaker for determinism
        scored_templates.sort(
            key=lambda x: (-x[0], x[1].template_id)
        )

        # Take top-k
        result = tuple(t for _, t in scored_templates[:top_k])

        # Cache result
        self._cache[cache_key] = result

        return result

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._cache.clear()

    def retrieval_hash(
        self,
        family: OntologicalFamily,
        canonical_signature: str,
        slot_plan: str,
    ) -> str:
        """
        Compute deterministic hash of retrieval inputs.

        Used for audit trail and reproducibility verification.
        """
        canonical = f"family:{family.value}|sig:{canonical_signature}|slot:{slot_plan}"
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# =============================================================================
# Factory Functions
# =============================================================================

def create_default_retriever() -> Phase12TemplateRetriever:
    """Create retriever with default settings."""
    return Phase12TemplateRetriever()


def create_expanded_retriever(num_candidates: int = 50) -> Phase12TemplateRetriever:
    """Create retriever with more candidates for better coverage."""
    return Phase12TemplateRetriever(num_candidates=num_candidates)


# =============================================================================
# Helper: Build FewShotContext
# =============================================================================

def build_few_shot_context(
    retriever: Phase12TemplateRetriever,
    family: OntologicalFamily,
    canonical_signature: str,
    slot_plan: str,
    max_examples: int = 3,
) -> FewShotContext:
    """
    Build FewShotContext from retriever results.

    Convenience function that combines retrieval and context creation.
    """
    templates = retriever.retrieve(
        family=family,
        canonical_signature=canonical_signature,
        slot_plan=slot_plan,
        top_k=max_examples + 2,  # Retrieve a few extra for flexibility
    )

    return FewShotContext(
        templates=templates,
        max_examples=max_examples,
    )


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Similarity functions
    "calculate_template_similarity",
    # Retriever
    "Phase12TemplateRetriever",
    # Factory functions
    "create_default_retriever",
    "create_expanded_retriever",
    # Helper
    "build_few_shot_context",
]
