"""
Hybrid Phoneme-Transformer Optimization
========================================

Uses deterministic 12D phoneme vectors to reduce transformer computation.

Strategies:
1. PhonemeAttentionHead: Replace learned attention with phoneme similarity
2. CandidatePreFilter: Pre-filter candidates before expensive inference
3. SemanticRouter: Route queries to specialized sub-models
4. RichRouting: Detailed routing analysis with phase/coherence signals (new!)

Computational Savings:
- Attention: O(n² × 12) vs O(n² × 768) = 64x reduction
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

    # Rich routing analysis (new!)
    from symbolu.hybrid import print_routing_report
    print_routing_report("How do atoms bond together?")
"""

from symbolu.hybrid.attention import PhonemeAttentionHead
from symbolu.hybrid.prefilter import CandidatePreFilter
from symbolu.hybrid.router import SemanticRouter
from symbolu.hybrid.benchmark import ComputationBenchmark
from symbolu.hybrid.rich_routing import (
    analyze_routing,
    format_rich_routing,
    print_routing_report,
    RichRoutingReport,
    PhaseProfile,
    SemanticField,
    WordContribution,
    QueryMode,
    PHASE_MAPPING,
    PHASE_DESCRIPTIONS,
)

__all__ = [
    # Core components
    "PhonemeAttentionHead",
    "CandidatePreFilter",
    "SemanticRouter",
    "ComputationBenchmark",
    # Rich routing (new!)
    "analyze_routing",
    "format_rich_routing",
    "print_routing_report",
    "RichRoutingReport",
    "PhaseProfile",
    "SemanticField",
    "WordContribution",
    "QueryMode",
    "PHASE_MAPPING",
    "PHASE_DESCRIPTIONS",
]
