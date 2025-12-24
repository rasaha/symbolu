"""R[v,a] Vṛtti-Aspect Coupling Matrix (12D).

Defines the 5×12 coupling matrix that relates the 5 cognitive modes (vṛtti)
to the 12 ontological layers. This matrix is used in the core formula:

    p_w[a] = normalize( E(w,c) · Φ(a) · Σ p_v[v] · R[v,a] + B_c(h(c)) )

Values are derived from the August 20, 2025 Soulpi-Resonance Model document
with illustrative couplings based on philosophical grounding.

The matrix encodes: "When in cognitive mode v, which layers become more prominent?"

12D Migration (from 10D):
    - Added O1_POTENTIAL (dormant capacity) at position 0
    - Added O11_INTEGRATION (resolution, consolidation) at position 10
    - Reordered existing aspects to match 12D patent-exact sequence
"""

import numpy as np

# Aspect indices (matching 12D ontological layers in resonance/types.py)
ASPECT_NAMES = [
    "O1_POTENTIAL",     # 0 - Dormant capacity
    "O2_IDENTITY",      # 1 - Classification, labeling
    "O3_EXECUTION",     # 2 - Action, karma
    "O4_STRUCTURE",     # 3 - Form, shape (body)
    "O5_COGNITION",     # 4 - Perception, attention (mind)
    "O6_AGENCY",        # 5 - Direction, control (ego)
    "O7_REASONING",     # 6 - Logic, analysis (intellect)
    "O8_PURPOSE",       # 7 - Intent, goals (soul)
    "O9_WITNESSES",     # 8 - Awareness, observation
    "O10_UNIFYING",     # 9 - Connection, harmony (atman)
    "O11_INTEGRATION",  # 10 - Resolution, consolidation (NEW)
    "O12_ABSOLVING",    # 11 - Release, transcendence (brahman)
]

# Vṛtti indices
VRITTI_NAMES = ["pramana", "viparyaya", "vikalpa", "smrti", "nidra"]

# R[v,a] Coupling Matrix (5 rows × 12 columns)
# Values derived from August 20, 2025 document with 12D extensions
#
# Key couplings from document (updated for 12D):
# - R[Pramāṇa, O7_REASONING] = 0.95 (valid cognition → discriminative wisdom)
# - Pramāṇa high for factual/logical domains (O7_REASONING, O3_EXECUTION)
# - Viparyaya high for self-referential conflict (O6_AGENCY)
# - Vikalpa high for creative/mental domains (O5_COGNITION, O4_STRUCTURE)
# - Smṛti high for continuity (O8_PURPOSE, O3_EXECUTION)
# - Nidrā high for physical inertia or transcendence (O4_STRUCTURE, O12_ABSOLVING)
#
# New dimensions:
# - O1_POTENTIAL: High for Nidrā (dormancy = unrealized potential), Smṛti (stored patterns)
# - O11_INTEGRATION: High for Pramāṇa (valid cognition integrates), Smṛti (memory consolidates)

R_MATRIX = np.array([
    # POT    ID     EXEC   STR    COG    AGN    RSN    PUR    WIT    UNI    INT    ABS
    [0.40,  0.80,  0.70,  0.60,  0.70,  0.50,  0.95,  0.60,  0.80,  0.70,  0.75,  0.60],  # Pramāṇa
    [0.30,  0.70,  0.50,  0.40,  0.60,  0.90,  0.40,  0.30,  0.50,  0.30,  0.35,  0.20],  # Viparyaya
    [0.50,  0.50,  0.60,  0.50,  0.85,  0.60,  0.70,  0.50,  0.60,  0.40,  0.55,  0.30],  # Vikalpa
    [0.70,  0.60,  0.80,  0.70,  0.70,  0.50,  0.60,  0.80,  0.50,  0.60,  0.70,  0.40],  # Smṛti
    [0.85,  0.30,  0.30,  0.70,  0.40,  0.30,  0.20,  0.40,  0.60,  0.50,  0.55,  0.75],  # Nidrā
], dtype=np.float64)

# Validate matrix shape
assert R_MATRIX.shape == (5, 12), f"R matrix shape mismatch: {R_MATRIX.shape}"


def get_coupling_matrix() -> np.ndarray:
    """Get the R[v,a] coupling matrix.

    Returns:
        5×12 numpy array where R[v,a] is the coupling strength
        between vṛtti v and ontological layer a.
    """
    return R_MATRIX.copy()


def get_aspect_weights(vritti_distribution: dict[str, float]) -> dict[str, float]:
    """Compute aspect weights from vṛtti distribution via R matrix.

    Implements: weights[a] = Σ_v p_v[v] · R[v,a]

    Args:
        vritti_distribution: Normalized vṛtti probabilities

    Returns:
        Dict mapping 12D layer names to weights
    """
    # Convert vṛtti dict to vector in correct order
    vritti_vec = np.array([
        vritti_distribution.get("pramana", 0.0),
        vritti_distribution.get("viparyaya", 0.0),
        vritti_distribution.get("vikalpa", 0.0),
        vritti_distribution.get("smrti", 0.0),
        vritti_distribution.get("nidra", 0.0),
    ])

    # Matrix multiply: (1×5) @ (5×12) = (1×12)
    aspect_weights = vritti_vec @ R_MATRIX

    # Convert to dict
    return {name: float(weight) for name, weight in zip(ASPECT_NAMES, aspect_weights)}


def get_primary_coupling(vritti_name: str) -> str:
    """Get the layer with strongest coupling for a given vṛtti.

    Args:
        vritti_name: Name of the vṛtti mode

    Returns:
        Name of the layer with highest coupling
    """
    if vritti_name not in VRITTI_NAMES:
        raise ValueError(f"Unknown vṛtti: {vritti_name}")

    vritti_idx = VRITTI_NAMES.index(vritti_name)
    aspect_idx = int(np.argmax(R_MATRIX[vritti_idx]))

    return ASPECT_NAMES[aspect_idx]


# Primary couplings (precomputed for reference - 12D)
PRIMARY_COUPLINGS = {
    "pramana": "O7_REASONING",     # Valid cognition → discriminative wisdom (0.95)
    "viparyaya": "O6_AGENCY",      # Misperception → self-referential conflict (0.90)
    "vikalpa": "O5_COGNITION",     # Conceptual branching → mental proliferation (0.85)
    "smrti": "O3_EXECUTION",       # Memory persistence → action/continuity (0.80), also O8_PURPOSE
    "nidra": "O1_POTENTIAL",       # Dormancy → unrealized potential (0.85), also O12_ABSOLVING
}


def get_coupling_explanation(vritti_name: str) -> str:
    """Get human-readable explanation of vṛtti-layer coupling.

    Args:
        vritti_name: Name of the vṛtti mode

    Returns:
        Explanation string
    """
    explanations = {
        "pramana": "Pramāṇa (valid cognition) activates O7_REASONING (0.95) - discriminative wisdom for clear understanding",
        "viparyaya": "Viparyaya (misperception) activates O6_AGENCY (0.90) - self-referential conflict and distortion",
        "vikalpa": "Vikalpa (conceptual branching) activates O5_COGNITION (0.85) - mental proliferation and imagination",
        "smrti": "Smṛti (memory persistence) activates O3_EXECUTION (0.80) and O8_PURPOSE (0.80) - continuity of action and being",
        "nidra": "Nidrā (dormancy) activates O1_POTENTIAL (0.85) and O12_ABSOLVING (0.75) - unrealized potential or transcendent stillness",
    }
    return explanations.get(vritti_name, f"Unknown vṛtti: {vritti_name}")


# Cross-domain disambiguation enhancement:
# The 12D R[v,a] matrix can help disambiguate homonyms by computing
# context-aware layer weights. When integrated with the phoneme router:
#
# 1. Compute p_v[v] from cross-layer coherence signals
# 2. Apply: weights[a] = Σ_v p_v[v] · R[v,a]
# 3. Use weights to bias phoneme-based layer totals
#
# Example: "bank" disambiguation
#   - Financial context → high Pramāṇa → boosts O7_REASONING, O3_EXECUTION
#   - Nature context → high Vikalpa → boosts O5_COGNITION, O4_STRUCTURE
