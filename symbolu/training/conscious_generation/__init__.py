"""
Conscious Generation modules for the ontological_hybrid model type.

Phase 1: Token-side ontological foundation
  - TokenOntologyProjector: e_w -> o_w (32D ontological codes per token)
  - TokenPrimitiveCache: Precomputed O_tok for full vocabulary
  - OntologyCompatibilityScorer: S_ont(w) = o_t^T M_ont o_w

Phase 2+: Primitive scoring, governance, integration (future)

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix D
"""

from symbolu.training.conscious_generation.token_ontology import TokenOntologyProjector
from symbolu.training.conscious_generation.token_cache import TokenPrimitiveCache
from symbolu.training.conscious_generation.primitives.ontology_scorer import (
    OntologyCompatibilityScorer,
)
from symbolu.training.conscious_generation.losses.ontological_structure import (
    OntologicalStructureLoss,
)

__all__ = [
    "TokenOntologyProjector",
    "TokenPrimitiveCache",
    "OntologyCompatibilityScorer",
    "OntologicalStructureLoss",
]
