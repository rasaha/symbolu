"""
Ontological Projection Layers
=============================

Layer-specific projection implementations.

Implemented layers:
    - THINKING: Structural derivation chains
    - META_OBSERVING: Witness frames and invariant timelines
    - UNIFYING: Structural equivalence classes
"""

from agentic.ontology.projection.layers.thinking import project_thinking
from agentic.ontology.projection.layers.meta_observing import project_meta_observing
from agentic.ontology.projection.layers.unifying import project_unifying

__all__ = [
    "project_thinking",
    "project_meta_observing",
    "project_unifying",
]
