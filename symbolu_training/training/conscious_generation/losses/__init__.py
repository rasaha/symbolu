"""Loss functions for Conscious Generation training."""

from symbolu_training.training.conscious_generation.losses.ontological_structure import (
    OntologicalStructureLoss,
)
from symbolu_training.training.conscious_generation.losses.kosha_routing import (
    KoshaRoutingLoss,
)
from symbolu_training.training.conscious_generation.losses.primitive_auxiliary import (
    PrimitiveAuxiliaryLosses,
)
from symbolu_training.training.conscious_generation.losses.bliss_coherence import (
    BlissCoherenceLoss,
)

# Appendix F Stage 5: Auxiliary Loss Supervision
from symbolu_training.training.conscious_generation.losses.auxiliary_loss_supervisor import (
    AuxiliaryLossSupervisor,
    AuxiliaryLossConfig,
    TokenOntologyProjection,
    BlissCoherenceProjection,
    GradientSafetyMonitor,
)

__all__ = [
    "OntologicalStructureLoss",
    "KoshaRoutingLoss",
    "PrimitiveAuxiliaryLosses",
    "BlissCoherenceLoss",

    # Appendix F Stage 5
    "AuxiliaryLossSupervisor",
    "AuxiliaryLossConfig",
    "TokenOntologyProjection",
    "BlissCoherenceProjection",
    "GradientSafetyMonitor",
]
