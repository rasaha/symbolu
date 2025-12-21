"""
Consumer Providers
==================

Pre-trained/semantic providers for consumer use cases.
These are placeholder stubs that will be replaced with trained models.

Consumer providers are characterized by:
- Pre-trained embeddings (768D, placeholder until trained)
- Trained classifier routing (placeholder returns GENERAL)
- Attention-based filtering (placeholder passes through)
- Optimized for natural conversation
"""

from symbolu.providers.consumer.learned_embedding import LearnedEmbeddingProvider
from symbolu.providers.consumer.trained_router import TrainedRouterProvider
from symbolu.providers.consumer.attention_filter import AttentionFilterProvider

__all__ = [
    "LearnedEmbeddingProvider",
    "TrainedRouterProvider",
    "AttentionFilterProvider",
]
