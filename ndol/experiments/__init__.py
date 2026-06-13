"""Semantic-tiering experiment scaffolding (CPU-testable, GPU-ready).

Implements the building blocks of docs/SEMANTIC_TIERING_GPU_PROTOCOL.md:
  * coherence  — the coherence block-scorer (SCC S=cosine), pure + torch-gated
  * selector   — block selection by policy (attention / semantic / scc / random)
  * loo_importance — the Exp-A leave-one-block-out ground-truth harness, with a
                     synthetic CPU model (testable now) and a marked GPU hook

Nothing here loads a model unless you call the real-model path; the pure cores
run on plain Python lists so they are unit-testable without torch/GPU.
"""
from .coherence import context_centroid, coherence_scores, MODES
from .selector import select_by_policy, select_blocks, blend, POLICIES

__all__ = [
    "context_centroid",
    "coherence_scores",
    "MODES",
    "select_by_policy",
    "select_blocks",
    "blend",
    "POLICIES",
]
