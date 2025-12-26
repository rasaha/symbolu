# Symbolu Robotics - Patent Formulas
"""
Patent formula implementations for robotics applications.

This module implements the core patent formulas adapted for robotics:

BCVF - Bidirectional Consistency Verification Framework (B1-B3):
    - B1: Consistency Lagrangian for action scoring
    - B2: Exponential weight conversion
    - B3: Softmax normalization across candidates

USE - Unified Sensor Encoding (U1-U4):
    - U1: Cross-modal correlation matrix
    - U2: Coherence-weighted fusion
    - U3: Temporal alignment
    - U4: Confidence estimation

SCC - Semantic Coherence Controller (S1-S9):
    - S1-S3: Layer coherence (adapted from main Symbolu)
    - S4: Cosine similarity between representations
    - S5: Semantic entropy monitoring
    - S6-S9: Extended coherence metrics
"""

from symbolu_robotics.formulas.bcvf import (
    compute_consistency_lagrangian,
    compute_bcvf_weight,
    normalize_bcvf_weights,
    score_action_candidates,
    BCVFScorer,
)

from symbolu_robotics.formulas.use import (
    compute_correlation_matrix,
    compute_coherence_fusion,
    compute_temporal_alignment,
    compute_confidence,
    USEFusion,
)

from symbolu_robotics.formulas.scc import (
    compute_layer_coherence,
    compute_global_coherence,
    compute_cosine_similarity,
    compute_semantic_entropy,
    SCCMonitor,
)

__all__ = [
    # BCVF (B1-B3)
    "compute_consistency_lagrangian",
    "compute_bcvf_weight",
    "normalize_bcvf_weights",
    "score_action_candidates",
    "BCVFScorer",
    # USE (U1-U4)
    "compute_correlation_matrix",
    "compute_coherence_fusion",
    "compute_temporal_alignment",
    "compute_confidence",
    "USEFusion",
    # SCC (S1-S9)
    "compute_layer_coherence",
    "compute_global_coherence",
    "compute_cosine_similarity",
    "compute_semantic_entropy",
    "SCCMonitor",
]
