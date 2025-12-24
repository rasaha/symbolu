"""R[v,a] Vṛtti-Aspect Coupling Matrix.

Defines the 5×10 coupling matrix that relates the 5 cognitive modes (vṛtti)
to the 10 ontological aspects. This matrix is used in the core formula:

    p_w[a] = normalize( E(w,c) · Φ(a) · Σ p_v[v] · R[v,a] + B_c(h(c)) )

Values are derived from the August 20, 2025 Soulpi-Resonance Model document
with illustrative couplings based on philosophical grounding.

The matrix encodes: "When in cognitive mode v, which aspects become more prominent?"
"""

import numpy as np

# Aspect indices (matching Dimension enum in ontology/backbone/encoder.py)
ASPECT_NAMES = [
    "karma",        # 0 - ACTION
    "identification",  # 1 - IDENTIFICATION
    "body",         # 2 - BODY
    "mind",         # 3 - MIND
    "ego",          # 4 - EGO
    "intellect",    # 5 - INTELLECT
    "soul",         # 6 - SOUL
    "witness",      # 7 - WITNESS
    "atman",        # 8 - SINGULARITY
    "brahman",      # 9 - ABSOLUTE
]

# Vṛtti indices
VRITTI_NAMES = ["pramana", "viparyaya", "vikalpa", "smrti", "nidra"]

# R[v,a] Coupling Matrix (5 rows × 10 columns)
# Values derived from August 20, 2025 document with illustrative extensions
#
# Key couplings from document:
# - R[Pramāṇa, Intellect] = 0.9 (explicitly stated)
# - Pramāṇa high for factual/logical domains (Intellect, Karma)
# - Viparyaya high for self-referential conflict (Ego)
# - Vikalpa high for creative/mental domains (Mind)
# - Smṛti high for continuity (Soul)
# - Nidrā high for physical inertia or transcendence (Body, Brahman)

R_MATRIX = np.array([
    # Karma  Ident  Body   Mind   Ego    Intel  Soul   Witn   Atman  Brahm
    [0.70,  0.80,  0.60,  0.70,  0.50,  0.95,  0.60,  0.80,  0.70,  0.60],  # Pramāṇa
    [0.50,  0.70,  0.40,  0.60,  0.90,  0.40,  0.30,  0.50,  0.30,  0.20],  # Viparyaya
    [0.60,  0.50,  0.50,  0.85,  0.60,  0.70,  0.50,  0.60,  0.40,  0.30],  # Vikalpa
    [0.80,  0.60,  0.70,  0.70,  0.50,  0.60,  0.80,  0.50,  0.60,  0.40],  # Smṛti
    [0.30,  0.30,  0.70,  0.40,  0.30,  0.20,  0.40,  0.60,  0.50,  0.75],  # Nidrā
], dtype=np.float64)

# Validate matrix shape
assert R_MATRIX.shape == (5, 10), f"R matrix shape mismatch: {R_MATRIX.shape}"


def get_coupling_matrix() -> np.ndarray:
    """Get the R[v,a] coupling matrix.

    Returns:
        5×10 numpy array where R[v,a] is the coupling strength
        between vṛtti v and aspect a.
    """
    return R_MATRIX.copy()


def get_aspect_weights(vritti_distribution: dict[str, float]) -> dict[str, float]:
    """Compute aspect weights from vṛtti distribution via R matrix.

    Implements: weights[a] = Σ_v p_v[v] · R[v,a]

    Args:
        vritti_distribution: Normalized vṛtti probabilities

    Returns:
        Dict mapping aspect names to weights
    """
    # Convert vṛtti dict to vector in correct order
    vritti_vec = np.array([
        vritti_distribution.get("pramana", 0.0),
        vritti_distribution.get("viparyaya", 0.0),
        vritti_distribution.get("vikalpa", 0.0),
        vritti_distribution.get("smrti", 0.0),
        vritti_distribution.get("nidra", 0.0),
    ])

    # Matrix multiply: (1×5) @ (5×10) = (1×10)
    aspect_weights = vritti_vec @ R_MATRIX

    # Convert to dict
    return {name: float(weight) for name, weight in zip(ASPECT_NAMES, aspect_weights)}


def get_primary_coupling(vritti_name: str) -> str:
    """Get the aspect with strongest coupling for a given vṛtti.

    Args:
        vritti_name: Name of the vṛtti mode

    Returns:
        Name of the aspect with highest coupling
    """
    if vritti_name not in VRITTI_NAMES:
        raise ValueError(f"Unknown vṛtti: {vritti_name}")

    vritti_idx = VRITTI_NAMES.index(vritti_name)
    aspect_idx = int(np.argmax(R_MATRIX[vritti_idx]))

    return ASPECT_NAMES[aspect_idx]


# Primary couplings (precomputed for reference)
PRIMARY_COUPLINGS = {
    "pramana": "intellect",     # Valid cognition → discriminative wisdom
    "viparyaya": "ego",         # Misperception → self-referential conflict
    "vikalpa": "mind",          # Conceptual branching → mental proliferation
    "smrti": "karma",           # Memory persistence → action/continuity (also soul)
    "nidra": "brahman",         # Dormancy → transcendence (also body)
}


def get_coupling_explanation(vritti_name: str) -> str:
    """Get human-readable explanation of vṛtti-aspect coupling.

    Args:
        vritti_name: Name of the vṛtti mode

    Returns:
        Explanation string
    """
    explanations = {
        "pramana": "Pramāṇa (valid cognition) activates Intellect (0.95) - discriminative wisdom for clear understanding",
        "viparyaya": "Viparyaya (misperception) activates Ego (0.90) - self-referential conflict and distortion",
        "vikalpa": "Vikalpa (conceptual branching) activates Mind (0.85) - mental proliferation and imagination",
        "smrti": "Smṛti (memory persistence) activates Karma (0.80) and Soul (0.80) - continuity of action and being",
        "nidra": "Nidrā (dormancy) activates Brahman (0.75) and Body (0.70) - transcendent stillness or physical inertia",
    }
    return explanations.get(vritti_name, f"Unknown vṛtti: {vritti_name}")
