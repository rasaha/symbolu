"""
Stage 9 — Post-Training Attention Mechanism Ablation Audit
==========================================================

Provides toggle flags for independently disabling each attention modulation
mechanism at runtime, plus metrics collection and ablation runner utilities.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix F.14
"""

from .config import AttentionAblationConfig
from .metrics import AblationMetrics, compute_ablation_metrics
from .runner import AblationRunner, AblationResult, ABLATION_MATRIX

__all__ = [
    "AttentionAblationConfig",
    "AblationMetrics",
    "compute_ablation_metrics",
    "AblationRunner",
    "AblationResult",
    "ABLATION_MATRIX",
]
