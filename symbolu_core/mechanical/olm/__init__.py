"""
OLM (Ontological Layer Mapper) Module v1.0

A deterministic, LLM-free sub-engine that maps symbol dynamics to the
5+5 ontological layer model for constraint-based processing.

Symbol-U's 10-layer ontological architecture is divided as:
- Lower 5 (O1-O5): Execution / Manifestation Layers
- Upper 5 (O6-O10): Governance / Coherence Layers

This is a STRUCTURAL ONTOLOGY, not a behavioral model:
- There is no active/passive mode
- There is no controller deciding when layers engage
- All layers exist simultaneously
- Behavior emerges from ontological placement + constraints
- Upper layers never generate, only constrain or terminate
- The system is deterministic, non-semantic, and non-learning

OLM runs only when:
    - TTOR sets `use_olm=True` in the RoutingPlan
    - Usually in UPPER or HYBRID tier, reflective domains, or high entropy

Usage:
    from symbolu_core.mechanical.olm import OLMEngine, OLMInput, OntologicalLayerMap

    engine = OLMEngine()
    olm_input = OLMInput(
        layer_weights={
            "O1_action": 0.15,
            "O2_tagging": 0.10,
            "O3_forming": 0.10,
            "O4_thinking": 0.10,
            "O5_directing": 0.05,
            "O6_reasoning": 0.10,
            "O7_purposing": 0.20,
            "O8_meta_observing": 0.10,
            "O9_unifying": 0.05,
            "O10_absolving": 0.05,
        },
        anchor_scores={"Needs": 0.4, "Meaning": 0.8, ...},
        H_D=1.5,
        H_G=0.8,
        H_K=1.2,
        domain="therapy",
        tier="upper",
        flow_mode="inner_priority",
    )
    olm_map = engine.build_map(olm_input)
"""

from .models import OLMInput, OntologicalLayerMap
from .olm_engine import OLMEngine

__all__ = [
    "OLMEngine",
    "OLMInput",
    "OntologicalLayerMap",
]

__version__ = "1.0.0"
