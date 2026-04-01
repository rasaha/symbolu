"""
Ontological State Predictor (OSP) with Phase Attention.

This module implements a latent-space state predictor operating on the
32D Sovereign State. It predicts ontological state transitions (deltas)
rather than tokens or pixels, using phase-space dynamics.

NOT Meta's VL-JEPA or I-JEPA. This is a custom architecture inspired by
the JEPA principle of predicting in latent space without reconstruction,
but applied to a domain-specific ontological state representation.

32D Sovereign State Planes:
    - Ontological Plane [0:12]:  12 Bhavas — identity/phase rotation (softmax)
    - Depth Plane [12:17]:       5 Koshas  — processing depth (sigmoid)
    - Intellectual Plane [17:22]: 5 Vrittis — cognitive reliability (softmax)
        Pramana (valid cognition), Viparyaya (error), Vikalpa (imagination),
        Nidra (void), Smriti (memory)
    - Dynamics Plane [22:28]:    6 Gunas   — energy/system dynamics (sigmoid)
    - Learning Plane [28:32]:    4 Reserved — goal encoding/feedback (tanh)

Components:
    - PhaseJEPAPredictor: Core predictor using phase-space dynamics
    - VrittiValidatedPredictor: Predictor with intellectual plane validation
    - SovereignStateProjector: Projects hidden states to 32D Sovereign State
    - DeltaStateProjector: Computes state deltas for transition prediction
    - TargetEncoder: EMA-updated encoder for stable targets
    - VICRegLoss: Variance-Invariance-Covariance regularization
    - WeightedAlignmentLoss: Per-component weighted alignment
    - JEPAPredictionLoss: Complete prediction loss with regularization
    - CompositeJEPALoss: Curriculum-aware loss combining all components

References:
    - HYBRID_PHASE_JEPA_DESIGN.md
    - PHASE_ATTENTION_ALGORITHM.md
    - Inspired by JEPA principle (LeCun, 2022) — predict in latent space
    - VICReg (Bardes et al., 2022) — collapse prevention
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

# Curriculum orchestrator
from symbolu.jepa.curriculum import (
    JEPAPhase,
    MacroPhase,
    PhaseConfig,
    CurriculumState,
    TrainingCurriculumOrchestrator,
    LossScheduler,
    create_curriculum_from_config,
)

# Transformer wrapper
from symbolu.jepa.transformer import (
    PhaseJEPAConfig,
    PhaseJEPATransformer,
    create_phase_jepa_transformer,
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

    # Curriculum
    'JEPAPhase',
    'MacroPhase',
    'PhaseConfig',
    'CurriculumState',
    'TrainingCurriculumOrchestrator',
    'LossScheduler',
    'create_curriculum_from_config',

    # Transformer
    'PhaseJEPAConfig',
    'PhaseJEPATransformer',
    'create_phase_jepa_transformer',
]
