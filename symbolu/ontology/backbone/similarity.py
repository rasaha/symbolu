"""
Cross-Domain Similarity Engine
==============================

Computes structural similarity between 10D vectors to enable
cross-domain reasoning without requiring semantic understanding.

The key insight: Two pieces of content from different domains
(e.g., history and literature) can be structurally similar if
they share the same dimensional profile.

Example:
    "The Civil War divided the nation" (History)
    "The family was torn apart by conflict" (Literature)

    Both have high scores in:
    - 1D Action (conflict unfolding)
    - 2D Identification (polarity/division)
    - 5D Ego (choices made)

    This structural similarity enables cross-domain retrieval
    without needing to "understand" either domain.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any, Callable
import math
from functools import lru_cache

from .encoder import DimensionalVector, Dimension, encode_10d


@dataclass
class SimilarityResult:
    """
    Result of similarity computation between two vectors.

    Attributes:
        score: Overall similarity [0.0, 1.0]
        dimension_similarities: Per-dimension similarity scores
        dominant_shared: Dimensions where both vectors are strong
        divergent: Dimensions where vectors differ most
        explanation: Human-readable explanation
    """
    score: float
    dimension_similarities: Dict[str, float]
    dominant_shared: List[Tuple[str, float, float]]  # (dim, vec1_val, vec2_val)
    divergent: List[Tuple[str, float, float]]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "dimension_similarities": self.dimension_similarities,
            "dominant_shared": [
                {"dimension": d, "vec1": v1, "vec2": v2}
                for d, v1, v2 in self.dominant_shared
            ],
            "divergent": [
                {"dimension": d, "vec1": v1, "vec2": v2}
                for d, v1, v2 in self.divergent
            ],
            "explanation": self.explanation,
        }


# =============================================================================
# Similarity Metrics
# =============================================================================

def cosine_similarity(vec1: DimensionalVector, vec2: DimensionalVector) -> float:
    """
    Compute cosine similarity between two 10D vectors.

    Cosine similarity measures the angle between vectors,
    ignoring magnitude. Good for comparing "shape" of profiles.

    Args:
        vec1: First dimensional vector
        vec2: Second dimensional vector

    Returns:
        Similarity score in [-1.0, 1.0], normalized to [0.0, 1.0]
    """
    dot_product = sum(a * b for a, b in zip(vec1.values, vec2.values))
    magnitude1 = math.sqrt(sum(a * a for a in vec1.values))
    magnitude2 = math.sqrt(sum(b * b for b in vec2.values))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    cosine = dot_product / (magnitude1 * magnitude2)
    # Normalize from [-1, 1] to [0, 1]
    return (cosine + 1) / 2


def euclidean_similarity(vec1: DimensionalVector, vec2: DimensionalVector) -> float:
    """
    Compute Euclidean similarity (inverse of distance).

    Good for comparing absolute positions in 10D space.

    Args:
        vec1: First dimensional vector
        vec2: Second dimensional vector

    Returns:
        Similarity score in [0.0, 1.0]
    """
    distance = math.sqrt(
        sum((a - b) ** 2 for a, b in zip(vec1.values, vec2.values))
    )
    # Max possible distance in 10D unit hypercube is sqrt(10) ≈ 3.16
    max_distance = math.sqrt(10)
    return 1.0 - (distance / max_distance)


def manhattan_similarity(vec1: DimensionalVector, vec2: DimensionalVector) -> float:
    """
    Compute Manhattan similarity (inverse of L1 distance).

    Good for sparse vectors where only some dimensions matter.

    Args:
        vec1: First dimensional vector
        vec2: Second dimensional vector

    Returns:
        Similarity score in [0.0, 1.0]
    """
    distance = sum(abs(a - b) for a, b in zip(vec1.values, vec2.values))
    # Max possible Manhattan distance is 10 (all dimensions differ by 1.0)
    return 1.0 - (distance / 10.0)


def weighted_similarity(
    vec1: DimensionalVector,
    vec2: DimensionalVector,
    weights: Optional[Dict[Dimension, float]] = None
) -> float:
    """
    Compute weighted similarity with dimension importance.

    Allows prioritizing certain dimensions over others.

    Args:
        vec1: First dimensional vector
        vec2: Second dimensional vector
        weights: Optional weight per dimension (default: uniform)

    Returns:
        Similarity score in [0.0, 1.0]
    """
    if weights is None:
        weights = {dim: 1.0 for dim in Dimension}

    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0.0

    weighted_sum = 0.0
    for dim in Dimension:
        weight = weights.get(dim, 1.0)
        val1 = vec1.get(dim)
        val2 = vec2.get(dim)
        # Per-dimension similarity: 1 - |diff|
        dim_sim = 1.0 - abs(val1 - val2)
        weighted_sum += weight * dim_sim

    return weighted_sum / total_weight


def structural_similarity(vec1: DimensionalVector, vec2: DimensionalVector) -> float:
    """
    Compute structural similarity based on dominant dimensions.

    Instead of comparing all dimensions equally, this focuses on
    dimensions where at least one vector has significant activation.

    This is useful for cross-domain matching where irrelevant
    dimensions (both near zero) shouldn't affect similarity.

    Args:
        vec1: First dimensional vector
        vec2: Second dimensional vector

    Returns:
        Similarity score in [0.0, 1.0]
    """
    threshold = 0.3  # Minimum activation to consider dimension "active"
    active_dims = []

    for dim in Dimension:
        val1 = vec1.get(dim)
        val2 = vec2.get(dim)
        if val1 >= threshold or val2 >= threshold:
            active_dims.append(dim)

    if not active_dims:
        # Both vectors have low activation everywhere
        return 0.5  # Neutral similarity

    # Compute similarity only on active dimensions
    total_sim = 0.0
    for dim in active_dims:
        val1 = vec1.get(dim)
        val2 = vec2.get(dim)
        dim_sim = 1.0 - abs(val1 - val2)
        total_sim += dim_sim

    return total_sim / len(active_dims)


# =============================================================================
# Main Similarity Interface
# =============================================================================

def compute_similarity(
    vec1: DimensionalVector,
    vec2: DimensionalVector,
    method: str = "structural"
) -> SimilarityResult:
    """
    Compute detailed similarity between two dimensional vectors.

    Args:
        vec1: First dimensional vector
        vec2: Second dimensional vector
        method: Similarity method - "cosine", "euclidean", "manhattan",
                "weighted", or "structural" (default)

    Returns:
        SimilarityResult with score and detailed breakdown
    """
    # Select similarity function
    methods = {
        "cosine": cosine_similarity,
        "euclidean": euclidean_similarity,
        "manhattan": manhattan_similarity,
        "weighted": weighted_similarity,
        "structural": structural_similarity,
    }
    sim_func = methods.get(method, structural_similarity)

    # Compute overall score
    score = sim_func(vec1, vec2)

    # Compute per-dimension similarities
    dim_sims = {}
    for dim in Dimension:
        val1 = vec1.get(dim)
        val2 = vec2.get(dim)
        dim_sims[dim.name] = 1.0 - abs(val1 - val2)

    # Find dominant shared dimensions (both high)
    threshold = 0.4
    dominant_shared = []
    for dim in Dimension:
        val1 = vec1.get(dim)
        val2 = vec2.get(dim)
        if val1 >= threshold and val2 >= threshold:
            dominant_shared.append((dim.name, val1, val2))

    # Sort by combined strength
    dominant_shared.sort(key=lambda x: x[1] + x[2], reverse=True)

    # Find divergent dimensions (large difference)
    divergent = []
    for dim in Dimension:
        val1 = vec1.get(dim)
        val2 = vec2.get(dim)
        diff = abs(val1 - val2)
        if diff >= 0.3:
            divergent.append((dim.name, val1, val2))

    # Sort by difference
    divergent.sort(key=lambda x: abs(x[1] - x[2]), reverse=True)

    # Generate explanation
    explanation = _generate_explanation(score, dominant_shared, divergent)

    return SimilarityResult(
        score=score,
        dimension_similarities=dim_sims,
        dominant_shared=dominant_shared[:5],  # Top 5
        divergent=divergent[:3],  # Top 3 differences
        explanation=explanation,
    )


def _generate_explanation(
    score: float,
    dominant_shared: List[Tuple[str, float, float]],
    divergent: List[Tuple[str, float, float]]
) -> str:
    """Generate human-readable explanation of similarity."""
    parts = []

    # Overall assessment
    if score >= 0.8:
        parts.append("Strong structural similarity.")
    elif score >= 0.6:
        parts.append("Moderate structural similarity.")
    elif score >= 0.4:
        parts.append("Weak structural similarity.")
    else:
        parts.append("Low structural similarity.")

    # Shared dimensions
    if dominant_shared:
        dims = [d[0] for d in dominant_shared[:3]]
        parts.append(f"Both strong in: {', '.join(dims)}.")

    # Divergent dimensions
    if divergent:
        for dim_name, val1, val2 in divergent[:2]:
            if val1 > val2:
                parts.append(f"First stronger in {dim_name}.")
            else:
                parts.append(f"Second stronger in {dim_name}.")

    return " ".join(parts)


# =============================================================================
# Batch Operations
# =============================================================================

def find_similar(
    query: DimensionalVector,
    candidates: List[DimensionalVector],
    top_k: int = 5,
    method: str = "structural",
    min_threshold: float = 0.0
) -> List[Tuple[int, SimilarityResult]]:
    """
    Find most similar vectors from a candidate list.

    Args:
        query: Query vector
        candidates: List of candidate vectors to search
        top_k: Number of results to return
        method: Similarity method
        min_threshold: Minimum similarity to include

    Returns:
        List of (index, SimilarityResult) tuples, sorted by score descending
    """
    results = []
    for idx, candidate in enumerate(candidates):
        sim = compute_similarity(query, candidate, method)
        if sim.score >= min_threshold:
            results.append((idx, sim))

    # Sort by score descending
    results.sort(key=lambda x: x[1].score, reverse=True)
    return results[:top_k]


def find_similar_content(
    query_text: str,
    candidate_texts: List[str],
    top_k: int = 5,
    method: str = "structural"
) -> List[Tuple[int, str, SimilarityResult]]:
    """
    Find similar content by encoding and comparing.

    Convenience function that handles encoding.

    Args:
        query_text: Query text
        candidate_texts: List of candidate texts
        top_k: Number of results
        method: Similarity method

    Returns:
        List of (index, text, SimilarityResult) tuples
    """
    query_vec = encode_10d(query_text)
    candidate_vecs = [encode_10d(text) for text in candidate_texts]

    results = find_similar(query_vec, candidate_vecs, top_k, method)
    return [(idx, candidate_texts[idx], sim) for idx, sim in results]


# =============================================================================
# Cross-Domain Analysis
# =============================================================================

@dataclass
class CrossDomainMatch:
    """
    Represents a cross-domain structural match.

    Attributes:
        content1: First content text
        content2: Second content text
        domain1: Domain of first content
        domain2: Domain of second content
        similarity: Similarity result
        shared_structure: Description of shared structure
        referent_coherence: Optional C × R × S referent coherence score
    """
    content1: str
    content2: str
    domain1: str
    domain2: str
    similarity: SimilarityResult
    shared_structure: str
    referent_coherence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "content1": self.content1[:100] + "..." if len(self.content1) > 100 else self.content1,
            "content2": self.content2[:100] + "..." if len(self.content2) > 100 else self.content2,
            "domain1": self.domain1,
            "domain2": self.domain2,
            "similarity_score": self.similarity.score,
            "shared_structure": self.shared_structure,
        }
        if self.referent_coherence is not None:
            result["referent_coherence"] = self.referent_coherence
        return result

    @property
    def combined_score(self) -> float:
        """Combined score including referent coherence if available."""
        base = self.similarity.score
        if self.referent_coherence is not None:
            # Weight: 80% structural, 20% referent coherence
            return base * 0.8 + self.referent_coherence * 0.2
        return base


def analyze_cross_domain(
    content1: str,
    content2: str,
    domain1: str = "unknown",
    domain2: str = "unknown",
    compute_referent_coherence: bool = False,
    terms1: Optional[List[str]] = None,
    terms2: Optional[List[str]] = None,
) -> CrossDomainMatch:
    """
    Analyze structural relationship between content from different domains.

    Args:
        content1: First content text
        content2: Second content text
        domain1: Domain label for first content
        domain2: Domain label for second content
        compute_referent_coherence: If True, compute C × R × S referent coherence
        terms1: Optional key terms from content1 for referent matching
        terms2: Optional key terms from content2 for referent matching

    Returns:
        CrossDomainMatch with detailed analysis
    """
    vec1 = encode_10d(content1)
    vec2 = encode_10d(content2)
    similarity = compute_similarity(vec1, vec2, "structural")

    # Generate shared structure description
    shared_parts = []
    for dim_name, val1, val2 in similarity.dominant_shared:
        shared_parts.append(f"{dim_name}({val1:.2f}/{val2:.2f})")

    if shared_parts:
        shared_structure = f"Shared dimensional pattern: {', '.join(shared_parts)}"
    else:
        shared_structure = "No strongly shared dimensional structure"

    # Compute referent coherence using canonical matching (C × R × S)
    referent_coherence = None
    if compute_referent_coherence and terms1 and terms2:
        referent_coherence = _compute_cross_domain_referent_coherence(terms1, terms2)
        if referent_coherence is not None:
            shared_structure += f" | Referent coherence: {referent_coherence:.2f}"

    return CrossDomainMatch(
        content1=content1,
        content2=content2,
        domain1=domain1,
        domain2=domain2,
        similarity=similarity,
        shared_structure=shared_structure,
        referent_coherence=referent_coherence,
    )


def _compute_cross_domain_referent_coherence(
    terms1: List[str],
    terms2: List[str],
) -> Optional[float]:
    """
    Compute referent coherence between term sets using canonical matching.

    Uses the S term from C × R × S to provide NON-phonemic validation.

    Args:
        terms1: Key terms from first content
        terms2: Key terms from second content

    Returns:
        Average S term (referent coherence) or None if not available
    """
    try:
        from symbolu.providers import get_match_provider
        match_provider = get_match_provider("enterprise")

        s_scores = []
        for t1 in terms1[:5]:
            for t2 in terms2[:5]:
                if t1.lower() != t2.lower():
                    result = match_provider.match(t1, t2)
                    s_scores.append(result.referent)

        if s_scores:
            return sum(s_scores) / len(s_scores)
        return None

    except ImportError:
        return None


def find_cross_domain_connections(
    contents: Dict[str, List[str]],  # domain -> list of texts
    min_similarity: float = 0.6
) -> List[CrossDomainMatch]:
    """
    Find structural connections across multiple domains.

    Args:
        contents: Dict mapping domain name to list of content texts
        min_similarity: Minimum similarity threshold

    Returns:
        List of CrossDomainMatch objects for significant connections
    """
    # Encode all content
    encoded = {}  # (domain, idx) -> (text, vector)
    for domain, texts in contents.items():
        for idx, text in enumerate(texts):
            vec = encode_10d(text)
            encoded[(domain, idx)] = (text, vec)

    # Find cross-domain matches
    matches = []
    domains = list(contents.keys())

    for i, domain1 in enumerate(domains):
        for domain2 in domains[i + 1:]:  # Only compare different domains
            for idx1 in range(len(contents[domain1])):
                text1, vec1 = encoded[(domain1, idx1)]
                for idx2 in range(len(contents[domain2])):
                    text2, vec2 = encoded[(domain2, idx2)]

                    similarity = compute_similarity(vec1, vec2, "structural")
                    if similarity.score >= min_similarity:
                        match = CrossDomainMatch(
                            content1=text1,
                            content2=text2,
                            domain1=domain1,
                            domain2=domain2,
                            similarity=similarity,
                            shared_structure=similarity.explanation,
                        )
                        matches.append(match)

    # Sort by similarity score
    matches.sort(key=lambda m: m.similarity.score, reverse=True)
    return matches
