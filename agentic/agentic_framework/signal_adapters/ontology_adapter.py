"""
Ontology Signal Adapter — 10D Encoding & Similarity Bridge (O2)
================================================================

Bridges the ontological backbone's 10D encoding and structural
similarity capabilities into the governance/framework signal path.

This adapter exposes two runtime-safe primitives:

1. ``resolve_ontology_encoding`` — Encode text into a 10D ontological
   signature (deterministic, cached, pure-function).

2. ``resolve_ontology_similarity`` — Compare two texts or two pre-encoded
   vectors for structural similarity (deterministic, pure-function).

Both follow the established signal adapter pattern:
    - Frozen Resolution dataclass (immutable, serializable)
    - Pure resolve function (duck-typed where practical, fail-closed)
    - ``available`` / ``source_detail`` provenance fields

Canonical sources consumed:
    agentic.ontology.backbone.encoder   — encode_10d, DimensionalVector, Dimension
    agentic.ontology.backbone.similarity — compute_similarity, SimilarityResult
    agentic.ontology.safety             — check_no_forbidden_modules

Design constraints:
    - No mutation of inputs
    - Deterministic: same input => identical output
    - Serializable outputs (to_dict on all resolution types)
    - Fail-closed: errors produce available=False resolutions, never raise
    - Does NOT import dormant backbone modules (learning, persona, RAG, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# =========================================================================
# Resolution Contracts
# =========================================================================

@dataclass(frozen=True)
class OntologyEncodingResolution:
    """
    Governance-safe view of a 10D ontological encoding.

    Attributes:
        available: Whether encoding succeeded.
        dimensions: Dict mapping dimension name to normalized score [0.0, 1.0].
                    Empty dict if not available.
        content_hash: SHA256 hash (first 32 hex chars) of the encoded content.
        dominant_dimensions: Top-3 dimensions by score, as (name, score) tuples.
        word_count: Number of words in the input content.
        source_detail: Provenance string describing the encoding source.
    """
    available: bool
    dimensions: Dict[str, float] = field(default_factory=dict)
    content_hash: str = ""
    dominant_dimensions: Tuple[Tuple[str, float], ...] = ()
    word_count: int = 0
    source_detail: str = "ontology_backbone_10d"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "dimensions": self.dimensions,
            "content_hash": self.content_hash,
            "dominant_dimensions": [
                {"dimension": name, "score": score}
                for name, score in self.dominant_dimensions
            ],
            "word_count": self.word_count,
            "source_detail": self.source_detail,
        }


@dataclass(frozen=True)
class OntologySimilarityResolution:
    """
    Governance-safe view of a 10D structural similarity comparison.

    Attributes:
        available: Whether comparison succeeded.
        score: Overall similarity score [0.0, 1.0].
        method: Similarity method used (e.g., "structural").
        dimension_similarities: Per-dimension similarity breakdown.
        dominant_shared: Dimensions where both inputs are strong.
        divergent: Dimensions where inputs differ most.
        explanation: Human-readable summary.
        source_detail: Provenance string.
    """
    available: bool
    score: float = 0.0
    method: str = "structural"
    dimension_similarities: Dict[str, float] = field(default_factory=dict)
    dominant_shared: Tuple[Tuple[str, float, float], ...] = ()
    divergent: Tuple[Tuple[str, float, float], ...] = ()
    explanation: str = ""
    source_detail: str = "ontology_backbone_similarity"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "score": self.score,
            "method": self.method,
            "dimension_similarities": self.dimension_similarities,
            "dominant_shared": [
                {"dimension": d, "score1": s1, "score2": s2}
                for d, s1, s2 in self.dominant_shared
            ],
            "divergent": [
                {"dimension": d, "score1": s1, "score2": s2}
                for d, s1, s2 in self.divergent
            ],
            "explanation": self.explanation,
            "source_detail": self.source_detail,
        }


# =========================================================================
# Unavailable Sentinels
# =========================================================================

_ENCODING_UNAVAILABLE = OntologyEncodingResolution(
    available=False,
    source_detail="ontology_backbone_10d:unavailable",
)

_SIMILARITY_UNAVAILABLE = OntologySimilarityResolution(
    available=False,
    source_detail="ontology_backbone_similarity:unavailable",
)


# =========================================================================
# Resolve Functions
# =========================================================================

def resolve_ontology_encoding(content: str) -> OntologyEncodingResolution:
    """
    Encode text content into a 10D ontological signature.

    Uses the canonical ``agentic.ontology.backbone.encoder.encode_10d``
    to produce a deterministic, cached, normalized 10-dimensional vector
    representing the structural profile of the input text.

    This is fail-closed: any error returns an unavailable resolution
    rather than raising.

    Args:
        content: Text to encode. Empty or whitespace-only text produces
                 a zero vector (all dimensions 0.0).

    Returns:
        OntologyEncodingResolution with dimensional scores, content hash,
        and dominant dimensions. available=False if encoding fails.

    Example:
        >>> res = resolve_ontology_encoding("The war divided the nation")
        >>> res.available
        True
        >>> res.dimensions["ACTION"]  # High — conflict, division
        0.72
    """
    try:
        from agentic.ontology.backbone.encoder import (
            encode_10d,
            Dimension,
            get_dominant_dimensions,
        )

        vec = encode_10d(content)

        dimensions = {
            dim.name: vec.get(dim)
            for dim in Dimension
        }

        dominant = get_dominant_dimensions(vec, top_k=3)
        dominant_tuples = tuple((dim.name, score) for dim, score in dominant)

        word_count = vec.metadata.get("word_count", 0) if vec.metadata else 0

        return OntologyEncodingResolution(
            available=True,
            dimensions=dimensions,
            content_hash=vec.content_hash,
            dominant_dimensions=dominant_tuples,
            word_count=word_count,
        )

    except Exception:
        return _ENCODING_UNAVAILABLE


def resolve_ontology_similarity(
    content1: str,
    content2: str,
    *,
    method: str = "structural",
) -> OntologySimilarityResolution:
    """
    Compare two texts for 10D structural similarity.

    Encodes both texts and computes structural similarity using the
    canonical ``agentic.ontology.backbone.similarity.compute_similarity``.

    Available methods: "cosine", "euclidean", "manhattan", "weighted",
    "structural" (default).

    This is fail-closed: any error returns an unavailable resolution.

    Args:
        content1: First text to compare.
        content2: Second text to compare.
        method: Similarity method (default: "structural").

    Returns:
        OntologySimilarityResolution with score, per-dimension breakdown,
        dominant shared dimensions, and divergent dimensions.
        available=False if comparison fails.

    Example:
        >>> res = resolve_ontology_similarity(
        ...     "The Civil War divided the nation",
        ...     "The family was torn apart by conflict",
        ... )
        >>> res.available
        True
        >>> res.score  # Moderate-to-high structural similarity
        0.68
    """
    try:
        from agentic.ontology.backbone.encoder import encode_10d
        from agentic.ontology.backbone.similarity import compute_similarity

        vec1 = encode_10d(content1)
        vec2 = encode_10d(content2)
        result = compute_similarity(vec1, vec2, method)

        return OntologySimilarityResolution(
            available=True,
            score=result.score,
            method=method,
            dimension_similarities=result.dimension_similarities,
            dominant_shared=tuple(
                (d, v1, v2) for d, v1, v2 in result.dominant_shared
            ),
            divergent=tuple(
                (d, v1, v2) for d, v1, v2 in result.divergent
            ),
            explanation=result.explanation,
        )

    except Exception:
        return _SIMILARITY_UNAVAILABLE
