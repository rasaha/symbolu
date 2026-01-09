"""
Phase-JEPA: Joint Embedding Predictive Architecture with Phase Attention.

This module implements the Phase-JEPA architecture for predicting in
ontological latent space (32D Sovereign State) rather than token space.

Components:
    - PhaseJEPAPredictor: Core predictor using phase-space dynamics
    - VrittiValidatedPredictor: Predictor with epistemological validation
    - SovereignStateProjector: Projects hidden states to 32D Sovereign State
    - DeltaStateProjector: Computes state deltas for transition prediction
    - TargetEncoder: EMA-updated encoder for stable targets
    - VICRegLoss: Variance-Invariance-Covariance regularization
    - WeightedAlignmentLoss: Per-component weighted alignment for multimodal
    - JEPAPredictionLoss: Complete JEPA loss with regularization
    - CompositeJEPALoss: Curriculum-aware loss combining all components

References:
    - HYBRID_PHASE_JEPA_DESIGN.md
    - PHASE_ATTENTION_ALGORITHM.md
    - Meta AI I-JEPA paper
"""

__version__ = '1.0.0'

# Core predictor
from symbolu.jepa.predictor import (
    PhaseJEPAPredictor,
    VrittiValidatedPredictor,
)

# State projection
from symbolu.jepa.state_projector import (
    SovereignStateProjector,
    DeltaStateProjector,
    SOVEREIGN_STATE_DIM,
)

# Target encoder
from symbolu.jepa.target_encoder import (
    TargetEncoder,
    TargetEncoderWrapper,
    cosine_momentum_schedule,
    linear_momentum_schedule,
)

# Loss functions
from symbolu.jepa.losses import (
    VICRegLoss,
    WeightedAlignmentLoss,
    JEPAPredictionLoss,
    CompositeJEPALoss,
)

__all__ = [
    # Version
    '__version__',

    # Predictor
    'PhaseJEPAPredictor',
    'VrittiValidatedPredictor',

    # State projection
    'SovereignStateProjector',
    'DeltaStateProjector',
    'SOVEREIGN_STATE_DIM',

    # Target encoder
    'TargetEncoder',
    'TargetEncoderWrapper',
    'cosine_momentum_schedule',
    'linear_momentum_schedule',

    # Losses
    'VICRegLoss',
    'WeightedAlignmentLoss',
    'JEPAPredictionLoss',
    'CompositeJEPALoss',
]
