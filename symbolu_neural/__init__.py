"""Symbol-U as a trainable neural architecture — module-interface skeleton.

This package is an *interface design*, not a finished/trained model. It maps
each Symbol-U patent equation group (EQ-A..EQ-L) to a differentiable nn.Module
with documented tensor shapes, gradient-flow status, required auxiliary losses,
and failure modes, and assembles them onto a conventional backbone.

Full training is intentionally NOT implemented (see README milestones). Start
from the MVP: small frozen backbone + typed heads, then climb the ablation
ladder, honoring the kill criteria.
"""
from .config import SymbolUConfig
from .backbone import BackboneWrapper, DummyBackbone
from .model import SymbolUModel
from . import losses, ablations

__all__ = [
    "SymbolUConfig", "BackboneWrapper", "DummyBackbone", "SymbolUModel",
    "losses", "ablations",
]
