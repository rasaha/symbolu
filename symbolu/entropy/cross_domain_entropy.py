"""
Cross-Domain Entropy Computation
================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CORE/SUBSTRATE LAYER                                   ║
║                                                                                ║
║  Deterministic, zero-LLM formula for cross-domain entropy computation.         ║
║  Measures structural incompatibility between domains.                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Cross-Domain Entropy Definition:
    Measures structural incompatibility when:
    - Input domain ≠ output domain
    - Structural profile drift exceeds threshold

    Formula: cross_domain_entropy = structural_distance(profile_a, profile_b)

    Interpretation:
    - Same structural profile → low entropy (close to 0.0)
    - Incompatible structures → high entropy (close to 1.0)

Example use cases:
    - Spiritual metaphor resolved as technical instruction → HIGH entropy
    - Emotional query answered with analytical response → MODERATE entropy
    - Technical question answered technically → LOW entropy

This module:
    - Computes cross-domain entropy from structural profiles
    - Provides explainability trace
    - Is fully deterministic (same input → same output)
    - Has NO side effects

Version: 1.0
Date: 2025-12-21
"""

from typing import Tuple, Dict, List, Optional
import math

from symbolu.entropy.types import DomainProfile, EntropyTraceEntry


# =============================================================================
# Constants
# =============================================================================

# The 12 structural dimensions (from name_resonance/types.py)
DIMENSION_NAMES = (
    "force",          # Low (flowing) to High (forceful)
    "stability",      # Variable to Constant
    "duration",       # Brief to Sustained
    "initiation",     # Gradual to Explosive
    "flow",           # Interrupted to Continuous
    "termination",    # Fading to Abrupt
    "complexity",     # Simple to Complex
    "density",        # Sparse to Dense
    "balance",        # Asymmetric to Symmetric
    "openness",       # Closed to Open
    "depth",          # Surface to Deep
    "connectivity",   # Isolated to Connected
)

# Default weights for each dimension (equal weighting)
DEFAULT_DIMENSION_WEIGHTS = {dim: 1.0 / len(DIMENSION_NAMES) for dim in DIMENSION_NAMES}

# Threshold for significant drift on a single dimension
DRIFT_THRESHOLD = 0.3


# =============================================================================
# Main Computation Functions
# =============================================================================

def compute_cross_domain_entropy(
    source_profile: DomainProfile,
    target_profile: DomainProfile,
    dimension_weights: Optional[Dict[str, float]] = None,
) -> Tuple[float, EntropyTraceEntry]:
    """
    Compute cross-domain entropy from source and target structural profiles.

    This measures the structural distance between the input domain
    (source profile) and the output domain (target profile).

    Algorithm:
        1. Compute dimension-wise differences
        2. Apply weighted Euclidean distance
        3. Identify drift dimensions (where difference > threshold)
        4. Generate explanation based on structural incompatibilities

    Args:
        source_profile: DomainProfile representing input structure
        target_profile: DomainProfile representing output structure
        dimension_weights: Optional custom weights for each dimension

    Returns:
        Tuple of (entropy_value, trace_entry) where:
        - entropy_value is in [0.0, 1.0]
        - trace_entry contains explainability information

    Determinism Guarantee:
        Same input profiles always produce same output.

    Examples:
        # Similar profiles (low entropy)
        source = DomainProfile(dimensions=(("force", 0.5), ("stability", 0.7), ...))
        target = DomainProfile(dimensions=(("force", 0.5), ("stability", 0.7), ...))
        entropy, _ = compute_cross_domain_entropy(source, target)
        # entropy ≈ 0.0

        # Incompatible profiles (high entropy)
        # Spiritual (low force, high openness) vs Technical (high stability, low openness)
        entropy, _ = compute_cross_domain_entropy(spiritual_profile, technical_profile)
        # entropy > 0.5
    """
    weights = dimension_weights or DEFAULT_DIMENSION_WEIGHTS

    # Compute per-dimension differences
    dimension_diffs: List[Tuple[str, float, float, float]] = []  # (name, source, target, diff)
    weighted_squared_diffs = []

    for dim in DIMENSION_NAMES:
        source_val = source_profile.get_dimension(dim)
        target_val = target_profile.get_dimension(dim)
        diff = abs(source_val - target_val)

        dimension_diffs.append((dim, source_val, target_val, diff))

        # Apply weight
        weight = weights.get(dim, 1.0 / len(DIMENSION_NAMES))
        weighted_squared_diffs.append((weight * diff) ** 2)

    # Compute weighted Euclidean distance
    distance = math.sqrt(sum(weighted_squared_diffs))

    # Maximum possible distance (all dimensions differ by 1.0)
    # For equal weights: sqrt(sum((1/12)^2 * 12)) = sqrt(1/12) ≈ 0.289
    # For unequal weights, we compute dynamically
    max_distance = math.sqrt(sum(weights.get(dim, 1.0 / len(DIMENSION_NAMES)) ** 2 for dim in DIMENSION_NAMES))

    # Normalize to [0, 1]
    if max_distance > 0:
        entropy = min(1.0, distance / max_distance)
    else:
        entropy = 0.0

    # Identify drift dimensions
    drift_dims = [(name, diff) for name, _, _, diff in dimension_diffs if diff >= DRIFT_THRESHOLD]
    drift_dims.sort(key=lambda x: x[1], reverse=True)

    # Generate explanation
    reason = _generate_reason(
        source_profile.domain_name,
        target_profile.domain_name,
        drift_dims,
        entropy,
    )
    trace = _create_trace(entropy, dimension_diffs, reason)

    return entropy, trace


def compute_structural_distance(
    profile_a: Dict[str, float],
    profile_b: Dict[str, float],
) -> Tuple[float, EntropyTraceEntry]:
    """
    Simplified cross-domain entropy computation from dimension dictionaries.

    Args:
        profile_a: Dictionary of dimension -> value for profile A
        profile_b: Dictionary of dimension -> value for profile B

    Returns:
        Tuple of (entropy_value, trace_entry)
    """
    # Convert to DomainProfile
    dims_a = tuple((dim, profile_a.get(dim, 0.5)) for dim in DIMENSION_NAMES)
    dims_b = tuple((dim, profile_b.get(dim, 0.5)) for dim in DIMENSION_NAMES)

    source = DomainProfile(dimensions=dims_a)
    target = DomainProfile(dimensions=dims_b)

    return compute_cross_domain_entropy(source, target)


# =============================================================================
# Helper Functions
# =============================================================================

def _create_trace(
    entropy: float,
    dimension_diffs: List[Tuple[str, float, float, float]],
    reason: str,
) -> EntropyTraceEntry:
    """Create an explainability trace entry."""
    # Include top drift dimensions in components
    top_drifts = sorted(dimension_diffs, key=lambda x: x[3], reverse=True)[:5]
    components = tuple(
        (f"{name}_drift", diff)
        for name, _, _, diff in top_drifts
    )

    return EntropyTraceEntry(
        metric_name="cross_domain_entropy",
        value=entropy,
        reason=reason,
        components=components,
    )


def _generate_reason(
    source_name: Optional[str],
    target_name: Optional[str],
    drift_dims: List[Tuple[str, float]],
    entropy: float,
) -> str:
    """Generate human-readable explanation for the entropy value."""
    # No significant drift
    if not drift_dims:
        if source_name and target_name:
            return f"Coherent transfer from {source_name} to {target_name}"
        return "Structurally coherent (no significant dimension drift)"

    # Format drift dimensions
    drift_descriptions = []
    for dim, diff in drift_dims[:3]:  # Top 3 drifts
        drift_descriptions.append(f"{dim} ({diff:.2f})")

    drift_str = ", ".join(drift_descriptions)

    # Generate description based on entropy level
    if entropy < 0.3:
        level = "Minor"
    elif entropy < 0.6:
        level = "Moderate"
    else:
        level = "Significant"

    if source_name and target_name:
        return f"{level} structural drift from {source_name} to {target_name}: {drift_str}"
    else:
        return f"{level} structural drift in: {drift_str}"


# =============================================================================
# Pattern Detection
# =============================================================================

def detect_incompatibility_pattern(
    source_profile: DomainProfile,
    target_profile: DomainProfile,
) -> Optional[str]:
    """
    Detect known incompatibility patterns between profiles.

    Returns a description of the pattern if detected, None otherwise.

    Known patterns:
    - Spiritual → Technical: High openness/depth → High stability/density
    - Emotional → Analytical: High connectivity/flow → High complexity/termination
    - Physical → Abstract: High force/density → High depth/openness
    """
    source_dims = source_profile.to_dict()
    target_dims = target_profile.to_dict()

    # Spiritual → Technical pattern
    spiritual_to_technical = (
        source_dims.get("openness", 0) > 0.6 and
        source_dims.get("depth", 0) > 0.6 and
        target_dims.get("stability", 0) > 0.6 and
        target_dims.get("density", 0) > 0.6 and
        target_dims.get("openness", 1) < 0.4
    )
    if spiritual_to_technical:
        return "Spiritual metaphor resolved as technical instruction"

    # Emotional → Analytical pattern
    emotional_to_analytical = (
        source_dims.get("connectivity", 0) > 0.6 and
        source_dims.get("flow", 0) > 0.6 and
        target_dims.get("complexity", 0) > 0.6 and
        target_dims.get("termination", 0) > 0.6 and
        target_dims.get("connectivity", 1) < 0.4
    )
    if emotional_to_analytical:
        return "Emotional input routed to analytical output"

    # Physical → Abstract pattern
    physical_to_abstract = (
        source_dims.get("force", 0) > 0.6 and
        source_dims.get("density", 0) > 0.6 and
        target_dims.get("depth", 0) > 0.6 and
        target_dims.get("openness", 0) > 0.6 and
        target_dims.get("force", 1) < 0.4
    )
    if physical_to_abstract:
        return "Physical context resolved as abstract concept"

    return None


# =============================================================================
# Utility Functions
# =============================================================================

def create_profile_from_dict(
    dimensions: Dict[str, float],
    domain_name: Optional[str] = None,
) -> DomainProfile:
    """Create a DomainProfile from a dictionary of dimensions."""
    dim_tuple = tuple(
        (dim, dimensions.get(dim, 0.5))
        for dim in DIMENSION_NAMES
    )
    return DomainProfile(dimensions=dim_tuple, domain_name=domain_name)


def get_dimension_drift(
    source_profile: DomainProfile,
    target_profile: DomainProfile,
) -> Dict[str, float]:
    """Get the drift (absolute difference) for each dimension."""
    return {
        dim: abs(source_profile.get_dimension(dim) - target_profile.get_dimension(dim))
        for dim in DIMENSION_NAMES
    }
