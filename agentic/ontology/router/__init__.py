"""
Ontological Router Package
==========================

Deterministic routing of Phase artifacts onto ontological layers.
"""

from agentic.ontology.router.layer_router import (
    OntologicalLayerRouter,
    OntologicalLayerRouterError,
    route_projection,
)
from agentic.ontology.router.phase_layer_map import (
    PHASE_TO_LAYERS,
    VALID_PHASE_IDS,
    get_layers_for_phase,
    get_phases_for_layer,
    is_valid_phase_id,
)

__all__ = [
    # Router
    "OntologicalLayerRouter",
    "OntologicalLayerRouterError",
    "route_projection",
    # Mapping
    "PHASE_TO_LAYERS",
    "VALID_PHASE_IDS",
    "get_layers_for_phase",
    "get_phases_for_layer",
    "is_valid_phase_id",
]
