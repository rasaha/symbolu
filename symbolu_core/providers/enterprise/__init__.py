"""
Enterprise Providers
====================

Symbolic/auditable providers for enterprise use cases.
These wrap the existing resonance and hybrid components.

Enterprise providers are characterized by:
- Deterministic, hash-based embeddings (256D)
- Phoneme-based symbolic routing
- Resonance-based candidate filtering
- Canonical matching (C × R × S framework)
- Full audit trail support

Tier: Core/Substrate (Tier 1)
Authority: NONE (signal processing only)
"""

from symbolu_core.providers.enterprise.hash_embedding import HashEmbeddingProvider
from symbolu_core.providers.enterprise.phoneme_router import PhonemeRouterProvider
from symbolu_core.providers.enterprise.resonance_filter import ResonanceFilterProvider
from symbolu_core.providers.enterprise.canonical_match import (
    CanonicalMatchProvider,
    create_canonical_match_provider,
)
from symbolu_core.providers.enterprise.coherence_filter import (
    CoherenceFilterProvider,
    CoherenceFilterResult,
    create_coherence_filter_provider,
)

__all__ = [
    # Embedding
    "HashEmbeddingProvider",
    # Router
    "PhonemeRouterProvider",
    # Filter
    "ResonanceFilterProvider",
    "CoherenceFilterProvider",
    "CoherenceFilterResult",
    "create_coherence_filter_provider",
    # Match (Canonical C × R × S)
    "CanonicalMatchProvider",
    "create_canonical_match_provider",
]
