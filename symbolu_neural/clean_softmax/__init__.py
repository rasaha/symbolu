"""Clean-softmax Symbol-U experiment.

A standard softmax decoder-only Transformer baseline with the Symbol-U patent
modules attached as OPTIONAL, CAUSAL augmentations — deliberately free of phase
attention, Sovereign State, JEPA, and CSR/phase mechanisms. Purpose: test whether
the Symbol-U formula improves or stabilizes a normal softmax Transformer,
independent of the Hybrid Phase stack. See README.md.
"""
from .backbone import SoftmaxTransformerLM, BackboneConfig
from .model import SymbolUSoftmaxModel
from .config import ExpConfig, ABLATIONS, get_ablation

__all__ = ["SoftmaxTransformerLM", "BackboneConfig", "SymbolUSoftmaxModel",
           "ExpConfig", "ABLATIONS", "get_ablation"]
