"""
Test Suite for Experiment Pack v1
=================================

Tests for:
    - Determinism (same inputs, same seed → same outputs/hashes)
    - Grounding enforcement (ensure JSON loader used, no heuristic imports)
    - Negative control sanity (scramble/swap reduces agreement)
    - Ablation sanity (RANDOM ablation degrades agreement vs baseline)
"""

__all__ = [
    "test_determinism",
    "test_grounding_enforcement",
    "test_negative_controls",
    "test_ablations",
]
