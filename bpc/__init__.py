"""
Belief-Predictability Coherence (BPC) Training Suite
=====================================================

Integrates a second training stream alongside CE that enforces forward
predictability/coherence using short rollouts and counterfactual perturbations
in a learned PCA belief subspace.

Modules:
    losses        - BPC loss functions (rollout consistency, counterfactual invariance)
    counterfactual - Controlled perturbation generators
    trainer       - BPC-augmented training loop
    scaling       - Scaling-law experiment runner
"""

from bpc.losses import (
    BPCConfig,
    BPCLoss,
    RolloutPredictor,
)
from bpc.counterfactual import CounterfactualPerturber

__all__ = [
    "BPCConfig",
    "BPCLoss",
    "RolloutPredictor",
    "CounterfactualPerturber",
]
