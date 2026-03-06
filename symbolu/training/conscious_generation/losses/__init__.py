"""Loss functions for Conscious Generation training."""

from symbolu.training.conscious_generation.losses.ontological_structure import (
    OntologicalStructureLoss,
)
from symbolu.training.conscious_generation.losses.kosha_routing import (
    KoshaRoutingLoss,
)
from symbolu.training.conscious_generation.losses.primitive_auxiliary import (
    PrimitiveAuxiliaryLosses,
)
from symbolu.training.conscious_generation.losses.bliss_coherence import (
    BlissCoherenceLoss,
)

__all__ = [
    "OntologicalStructureLoss",
    "KoshaRoutingLoss",
    "PrimitiveAuxiliaryLosses",
    "BlissCoherenceLoss",
]
