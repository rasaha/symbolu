"""
Conscious Generation modules for the ontological_hybrid model type.

Phase 1: Token-side ontological foundation
  - TokenOntologyProjector: e_w -> o_w (32D ontological codes per token)
  - TokenPrimitiveCache: Precomputed O_tok for full vocabulary
  - OntologyCompatibilityScorer: S_ont(w) = o_t^T M_ont o_w
  - OntologicalStructureLoss: InfoNCE contrastive for 32D manifold clustering

Phase 2: Primitive scoring heads
  - BaseScorer: S_base(w) from transformer logits
  - PlausibilityTokenScorer: S_plausibility(w) contextual plausibility
  - CSRTokenScorer: S_csr(w) phonemic resonance
  - VrittiTokenScorer: S_vritti(w) cognitive mode compatibility
  - GunaTokenScorer: S_guna(w) energetic compatibility
  - TokenEvaluationTensor: Orchestrates T_t ∈ ℝ^{K×6}

Phase 3: Governance integration
  - KoshaPrimitiveRouter: Dynamic α_t weights over 6 primitives
  - BlissTokenGate: Per-token coherence gating B(w)
  - IntegratedTokenScorer: Z*(w) = B(w) · Σ_f α_f S_f(w)
  - KoshaRoutingLoss: Agreement-based + entropy routing supervision
  - PrimitiveAuxiliaryLosses: Per-primitive contrastive token losses
  - BlissCoherenceLoss: Correct tokens → high Bliss, negatives → low Bliss

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix D
"""

from symbolu_training.training.conscious_generation.token_ontology import TokenOntologyProjector
from symbolu_training.training.conscious_generation.token_cache import TokenPrimitiveCache
from symbolu_training.training.conscious_generation.primitives.ontology_scorer import (
    OntologyCompatibilityScorer,
)
from symbolu_training.training.conscious_generation.losses.ontological_structure import (
    OntologicalStructureLoss,
)
from symbolu_training.training.conscious_generation.primitives import (
    BaseScorer,
    PlausibilityTokenScorer,
    JEPATokenScorer,  # backward-compatible alias
    CSRTokenScorer,
    VrittiTokenScorer,
    GunaTokenScorer,
    TokenEvaluationTensor,
)
from symbolu_training.training.conscious_generation.governance.kosha_router import (
    KoshaPrimitiveRouter,
)
from symbolu_training.training.conscious_generation.governance.bliss_gate import (
    BlissTokenGate,
)
from symbolu_training.training.conscious_generation.integration.token_scorer import (
    IntegratedTokenScorer,
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

__all__ = [
    "TokenOntologyProjector",
    "TokenPrimitiveCache",
    "OntologyCompatibilityScorer",
    "OntologicalStructureLoss",
    "BaseScorer",
    "PlausibilityTokenScorer",
    "JEPATokenScorer",  # backward-compatible alias
    "CSRTokenScorer",
    "VrittiTokenScorer",
    "GunaTokenScorer",
    "TokenEvaluationTensor",
    "KoshaPrimitiveRouter",
    "BlissTokenGate",
    "IntegratedTokenScorer",
    "KoshaRoutingLoss",
    "PrimitiveAuxiliaryLosses",
    "BlissCoherenceLoss",
]
