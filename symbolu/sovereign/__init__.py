"""
Sovereign-1 Architecture Implementation
========================================

This package implements the Sovereign-1 specification for cognitive state
management in transformer models. Key components:

- SovereignLoss: Decomposed state friction with signal weighting
- SovereignObserver: State delta computation (C, R, S, Guna signals)
- PIDGovernor: Control-theoretic gating between attention layers

Based on: docs/hardware/SOVEREIGN_1_DESIGN_IMPLEMENTATION.md v2.0
"""

from symbolu.sovereign.loss import SovereignLoss
from symbolu.sovereign.observer import SovereignObserver, BhavaTransitionPrior

__all__ = [
    'SovereignLoss',
    'SovereignObserver',
    'BhavaTransitionPrior',
]
