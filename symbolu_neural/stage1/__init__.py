"""Stage-1 grounding validation harness for Symbol-U.

Frozen backbone + Symbol-U typed heads only. Tests whether the Vritti/aspect
heads learn signal above chance/majority baselines, and whether predictive
entropy tracks error — before any further architecture is built or trained.

Honesty contract: with the bundled toy data (synthetic, surface-feature labels)
a PASS validates the harness and a learnable signal, NOT the real grounding
hypothesis. Real validation needs a pretrained LM + human-labeled syllable data.
"""
from .model_stage1 import Stage1GroundingModel

__all__ = ["Stage1GroundingModel"]
