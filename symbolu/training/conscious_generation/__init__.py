"""
Conscious Generation modules for the ontological_hybrid model type.

Phase 1: Token-side ontological foundation
  - TokenOntologyProjector: e_w -> o_w (32D ontological codes per token)
  - TokenPrimitiveCache: Precomputed O_tok for full vocabulary
  - OntologyCompatibilityScorer: S_ont(w) = o_t^T M_ont o_w
  - OntologicalStructureLoss: InfoNCE contrastive for 32D manifold clustering

Phase 2: Primitive scoring heads
  - BaseScorer: S_base(w) from transformer logits
  - JEPATokenScorer: S_jepa(w) physical plausibility
  - CSRTokenScorer: S_csr(w) phonemic resonance
  - VrittiTokenScorer: S_vritti(w) cognitive mode compatibility
  - GunaTokenScorer: S_guna(w) energetic compatibility
  - TokenEvaluationTensor: Orchestrates T_t ∈ ℝ^{K×6}

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
from symbolu.training.conscious_generation.primitives import (
    BaseScorer,
    JEPATokenScorer,
    CSRTokenScorer,
    VrittiTokenScorer,
    GunaTokenScorer,
    TokenEvaluationTensor,
)

__all__ = [
    "TokenOntologyProjector",
    "TokenPrimitiveCache",
    "OntologyCompatibilityScorer",
    "OntologicalStructureLoss",
    "BaseScorer",
    "JEPATokenScorer",
    "CSRTokenScorer",
    "VrittiTokenScorer",
    "GunaTokenScorer",
    "TokenEvaluationTensor",
]
