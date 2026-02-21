"""
Spanda-Softmax Hybrid v0.4

Spanda adds explicit semantic state trajectory (Psi) at the emission layer
while preserving the softmax probabilistic emission and transformer backbone.

Modules:
    state       - SpandaState: MLP delta computation + leaky cumsum Psi recurrence
    emission    - AnchorEmission: distance-based logit computation with algebraic expansion
                  ProjectedDotEmission: dot-product logits through same projection (no geometry)
    regularizers - L_step and L_smooth trajectory regularizers
    wrapper     - SpandaHybridWrapper: wraps any backbone transformer with Spanda emission
    metrics     - SpandaMetrics: logging and diagnostic checks
    plotting    - Visualization utilities for training curves, anchors, and Psi trajectories
"""

from .state import SpandaState
from .emission import AnchorEmission, ProjectedDotEmission
from .regularizers import SpandaRegularizers
from .wrapper import SpandaHybridWrapper
from .metrics import SpandaMetrics

__version__ = "0.4.0"
__all__ = [
    "SpandaState",
    "AnchorEmission",
    "ProjectedDotEmission",
    "SpandaRegularizers",
    "SpandaHybridWrapper",
    "SpandaMetrics",
]
