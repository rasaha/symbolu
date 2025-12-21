"""
Domain Distance - Symbolic Distance Matrix for Cross-Domain Reasoning
======================================================================

This module provides symbolic (not embedding-based) distance measurements
between domains for the Stitching Encoder's domain-jump penalty calculation.

Patent Reference:
    Claim [12] - Resonance modulation coefficient
    Claim [13] - Cross-domain entropy gate

Key Principle:
    Domain distances are human-curated symbolic relationships, NOT learned
    embeddings. This ensures deterministic, auditable cross-domain reasoning.
"""

from typing import Dict, Tuple, Optional
from symbolu.temporal.cross_domain_intelligence import CrossDomainIntelligence


# =============================================================================
# Domain Categories for Distance Calculation
# =============================================================================

# Domains organized by category for structured distance computation
DOMAIN_CATEGORIES: Dict[str, str] = {
    # Scientific/Analytical
    "finance": "analytical",
    "physics": "analytical",
    "mathematics": "analytical",
    "engineering": "analytical",

    # Human/Behavioral
    "psychology": "behavioral",
    "medicine": "behavioral",
    "education": "behavioral",
    "therapy": "behavioral",

    # Social/Institutional
    "legal": "institutional",
    "corporate": "institutional",
    "politics": "institutional",
    "governance": "institutional",

    # Creative/Abstract
    "philosophy": "abstract",
    "ethics": "abstract",
    "religion": "abstract",
    "art": "abstract",

    # Generic fallback
    "generic": "generic",
}


# =============================================================================
# Symbolic Domain Distance Matrix
# =============================================================================

# Pre-computed distances between domain pairs
# Values in range [0, 1]:
#   0.0 = same domain
#   0.1-0.3 = closely related (low penalty)
#   0.4-0.6 = moderately related (medium penalty)
#   0.7-0.9 = distantly related (high penalty)
#   1.0 = completely unrelated (maximum penalty)

DOMAIN_DISTANCE_MATRIX: Dict[Tuple[str, str], float] = {
    # Finance relationships
    ("finance", "psychology"): 0.30,   # Behavioral finance overlap
    ("finance", "economics"): 0.15,    # Core overlap
    ("finance", "mathematics"): 0.25,  # Quantitative methods
    ("finance", "physics"): 0.50,      # Structural analogies only
    ("finance", "corporate"): 0.20,    # Business context
    ("finance", "legal"): 0.35,        # Regulatory overlap
    ("finance", "ethics"): 0.45,       # Governance concerns
    ("finance", "politics"): 0.55,     # Policy impact

    # Psychology relationships
    ("psychology", "medicine"): 0.20,  # Clinical overlap
    ("psychology", "education"): 0.25, # Learning theory
    ("psychology", "philosophy"): 0.35, # Mind/consciousness
    ("psychology", "therapy"): 0.10,   # Direct application
    ("psychology", "corporate"): 0.40, # Organizational behavior
    ("psychology", "legal"): 0.45,     # Forensic/witness

    # Medicine relationships
    ("medicine", "psychology"): 0.20,  # Clinical overlap
    ("medicine", "education"): 0.40,   # Medical education
    ("medicine", "ethics"): 0.35,      # Bioethics
    ("medicine", "legal"): 0.40,       # Malpractice, regulations
    ("medicine", "physics"): 0.55,     # Medical physics

    # Physics relationships
    ("physics", "mathematics"): 0.15,  # Core dependency
    ("physics", "engineering"): 0.20,  # Applied physics
    ("physics", "philosophy"): 0.45,   # Philosophy of science
    ("physics", "chemistry"): 0.25,    # Physical chemistry

    # Legal relationships
    ("legal", "corporate"): 0.25,      # Business law
    ("legal", "ethics"): 0.30,         # Legal ethics
    ("legal", "politics"): 0.35,       # Constitutional law
    ("legal", "psychology"): 0.45,     # Forensic psychology

    # Education relationships
    ("education", "psychology"): 0.25, # Educational psychology
    ("education", "corporate"): 0.45,  # Training/development
    ("education", "philosophy"): 0.40, # Philosophy of education

    # Philosophy relationships
    ("philosophy", "ethics"): 0.15,    # Core overlap
    ("philosophy", "religion"): 0.30,  # Metaphysics/theology
    ("philosophy", "psychology"): 0.35, # Philosophy of mind
    ("philosophy", "physics"): 0.45,   # Natural philosophy

    # Corporate relationships
    ("corporate", "legal"): 0.25,      # Business law
    ("corporate", "finance"): 0.20,    # Corporate finance
    ("corporate", "psychology"): 0.40, # Organizational behavior
    ("corporate", "education"): 0.45,  # Training

    # Cross-category high distances
    ("finance", "art"): 0.75,          # Creative vs analytical
    ("physics", "religion"): 0.70,     # Science vs faith
    ("medicine", "art"): 0.65,         # Different domains
    ("legal", "art"): 0.60,            # Institutional vs creative
    ("psychology", "physics"): 0.55,   # Behavioral vs physical

    # Generic domain distances
    ("generic", "finance"): 0.50,
    ("generic", "psychology"): 0.50,
    ("generic", "medicine"): 0.50,
    ("generic", "physics"): 0.50,
    ("generic", "legal"): 0.50,
    ("generic", "education"): 0.50,
    ("generic", "corporate"): 0.50,
    ("generic", "philosophy"): 0.50,
    ("generic", "ethics"): 0.50,
}


# =============================================================================
# Distance Calculation Functions
# =============================================================================

def _normalize_domain(domain: str) -> str:
    """Normalize domain name to lowercase."""
    return domain.lower().strip() if domain else "generic"


def _make_pair_key(domain_a: str, domain_b: str) -> Tuple[str, str]:
    """Create canonical pair key (sorted alphabetically)."""
    a = _normalize_domain(domain_a)
    b = _normalize_domain(domain_b)
    return tuple(sorted([a, b]))


def get_domain_distance(domain_a: str, domain_b: str) -> float:
    """
    Get symbolic distance between two domains.

    This is a SYMBOLIC distance based on human-curated domain relationships,
    NOT an embedding-based similarity. This ensures:
    - Deterministic behavior
    - Auditable cross-domain reasoning
    - Explicit control over domain transfers

    Args:
        domain_a: First domain name
        domain_b: Second domain name

    Returns:
        Distance in range [0, 1]:
        - 0.0: Same domain
        - 0.1-0.3: Closely related
        - 0.4-0.6: Moderately related
        - 0.7-1.0: Distantly related

    Patent Reference:
        This implements the domain distance function D(di, dj) referenced
        in the stitching encoder's domain-jump penalty calculation.
    """
    a = _normalize_domain(domain_a)
    b = _normalize_domain(domain_b)

    # Same domain = no distance
    if a == b:
        return 0.0

    # Check direct lookup
    pair_key = _make_pair_key(a, b)
    if pair_key in DOMAIN_DISTANCE_MATRIX:
        return DOMAIN_DISTANCE_MATRIX[pair_key]

    # Check reverse lookup (matrix is symmetric)
    reverse_key = (pair_key[1], pair_key[0])
    if reverse_key in DOMAIN_DISTANCE_MATRIX:
        return DOMAIN_DISTANCE_MATRIX[reverse_key]

    # Fallback: compute from category distance
    return _compute_category_distance(a, b)


def _compute_category_distance(domain_a: str, domain_b: str) -> float:
    """
    Compute distance based on domain categories when no direct mapping exists.

    Category distances:
    - Same category: 0.35
    - Adjacent categories: 0.55
    - Distant categories: 0.70
    - Unknown: 0.60 (default)
    """
    cat_a = DOMAIN_CATEGORIES.get(domain_a, "generic")
    cat_b = DOMAIN_CATEGORIES.get(domain_b, "generic")

    if cat_a == cat_b:
        return 0.35  # Same category, different domain

    # Define category adjacencies
    adjacent_categories = {
        ("analytical", "behavioral"): 0.50,
        ("analytical", "institutional"): 0.55,
        ("behavioral", "institutional"): 0.50,
        ("behavioral", "abstract"): 0.45,
        ("institutional", "abstract"): 0.55,
        ("analytical", "abstract"): 0.60,
    }

    pair = tuple(sorted([cat_a, cat_b]))
    if pair in adjacent_categories:
        return adjacent_categories[pair]

    # Generic category
    if "generic" in (cat_a, cat_b):
        return 0.50

    # Default for unknown category pairs
    return 0.60


def get_domain_distance_with_context(
    domain_a: str,
    domain_b: str,
    aspect_overlap: float = 0.0,
    confidence: float = 1.0,
) -> float:
    """
    Get context-adjusted domain distance.

    The base distance can be reduced if there's strong aspect overlap,
    indicating structural similarity despite domain difference.

    Args:
        domain_a: First domain name
        domain_b: Second domain name
        aspect_overlap: Overlap score [0, 1] from aspect vectors
        confidence: Confidence in the cross-domain transfer

    Returns:
        Adjusted distance in range [0, 1]

    Formula:
        adjusted_distance = base_distance * (1 - aspect_overlap * 0.3) * (2 - confidence)

    This allows high-confidence, structurally-similar cross-domain transfers
    to have reduced penalties.
    """
    base_distance = get_domain_distance(domain_a, domain_b)

    # Aspect overlap can reduce distance by up to 30%
    aspect_adjustment = 1.0 - (aspect_overlap * 0.3)

    # Low confidence increases distance
    confidence_adjustment = 2.0 - confidence  # Range [1.0, 2.0]

    adjusted = base_distance * aspect_adjustment * confidence_adjustment

    # Clamp to valid range
    return min(max(adjusted, 0.0), 1.0)


def is_cross_domain(domain_a: str, domain_b: str) -> bool:
    """Check if two domains are different (cross-domain reasoning required)."""
    a = _normalize_domain(domain_a)
    b = _normalize_domain(domain_b)
    return a != b


def get_all_domains() -> list:
    """Get list of all known domains."""
    domains = set()
    for pair in DOMAIN_DISTANCE_MATRIX.keys():
        domains.add(pair[0])
        domains.add(pair[1])
    return sorted(list(domains))


def get_domain_category(domain: str) -> str:
    """Get category for a domain."""
    return DOMAIN_CATEGORIES.get(_normalize_domain(domain), "generic")


# =============================================================================
# Aspect Definitions for Cross-Domain Matching
# =============================================================================

# Domain-agnostic aspects used for structural pattern matching
# These allow matching across domains via shared structural patterns
UNIVERSAL_ASPECTS = {
    "ENTROPY": "Disorder, chaos, uncertainty, volatility",
    "CAUSALITY": "Cause-effect relationships, chains, triggers",
    "AGENCY": "Actor capability, autonomy, control",
    "BALANCE": "Equilibrium, stability, homeostasis",
    "FLOW": "Movement, transfer, progression",
    "CONSTRAINT": "Limits, boundaries, restrictions",
    "EMERGENCE": "Novel properties from interactions",
    "FEEDBACK": "Loops, self-regulation, adaptation",
    "HIERARCHY": "Levels, structure, organization",
    "THRESHOLD": "Tipping points, phase transitions, limits",
}


def get_aspect_overlap(
    aspect_a: Dict[str, float],
    aspect_b: Dict[str, float],
) -> float:
    """
    Calculate overlap between two aspect vectors.

    Uses dot product normalized by magnitude for overlap calculation.
    This measures structural similarity independent of domain.

    Args:
        aspect_a: First aspect vector {aspect_name: weight}
        aspect_b: Second aspect vector {aspect_name: weight}

    Returns:
        Overlap score in range [0, 1]
    """
    if not aspect_a or not aspect_b:
        return 0.0

    # Get common aspects
    common_aspects = set(aspect_a.keys()) & set(aspect_b.keys())
    if not common_aspects:
        return 0.0

    # Compute dot product
    dot_product = sum(
        aspect_a[k] * aspect_b[k]
        for k in common_aspects
    )

    # Compute magnitudes
    mag_a = sum(v * v for v in aspect_a.values()) ** 0.5
    mag_b = sum(v * v for v in aspect_b.values()) ** 0.5

    if mag_a == 0 or mag_b == 0:
        return 0.0

    # Normalized overlap
    return dot_product / (mag_a * mag_b)


__all__ = [
    "get_domain_distance",
    "get_domain_distance_with_context",
    "is_cross_domain",
    "get_all_domains",
    "get_domain_category",
    "get_aspect_overlap",
    "DOMAIN_DISTANCE_MATRIX",
    "DOMAIN_CATEGORIES",
    "UNIVERSAL_ASPECTS",
]
