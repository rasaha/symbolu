"""
Hybrid Phoneme-Transformer Optimization
========================================

Uses deterministic 10D phoneme vectors to reduce transformer computation.

Strategies:
1. PhonemeAttentionHead: Replace learned attention with phoneme similarity
2. CandidatePreFilter: Pre-filter candidates before expensive inference
3. SemanticRouter: Route queries to specialized sub-models

Computational Savings:
- Attention: O(n² × 10) vs O(n² × 768) = 77x reduction
- Pre-filtering: 100x fewer transformer calls
- Routing: Use smaller specialized models

Usage:
    from symbolu.hybrid import (
        PhonemeAttentionHead,
        CandidatePreFilter,
        SemanticRouter,
    )

    # Pre-filter candidates
    prefilter = CandidatePreFilter(threshold=0.6)
    filtered = prefilter.filter(candidates, target="truth")
    # Now run expensive transformer only on filtered set

    # Route to specialized model
    router = SemanticRouter()
    model = router.route("Love conquers all")  # → relationship_model
"""

from symbolu.hybrid.attention import PhonemeAttentionHead
from symbolu.hybrid.prefilter import CandidatePreFilter
from symbolu.hybrid.router import SemanticRouter
from symbolu.hybrid.benchmark import ComputationBenchmark

__all__ = [
    "PhonemeAttentionHead",
    "CandidatePreFilter",
    "SemanticRouter",
    "ComputationBenchmark",
]
