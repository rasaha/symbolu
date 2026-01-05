"""
Symbolu Inference Module
========================

Inference-time implementations of training components for the hybrid transformer.

This module bridges the gap between training-time logic (in train_unified_llm.py)
and inference-time behavior, enabling:

- Cross-sequence state persistence (karma buffer)
- Delayed resonance injection
- Metacognitive monitoring
- Guna-based quality tracking
- CSR safety layers

Phase 1 (Priority 1 - Critical):
- EvolutionaryInferenceEngine: Karma buffer and cross-sequence state

Phase 2 (Priority 2 - Important):
- InferenceMetacognition: Real-time generation quality monitoring
- InferenceGunas: Inference-time Guna approximation
- CSRInferenceGuard: CSR safety layer application
"""

from .evolutionary_inference import EvolutionaryInferenceEngine

__all__ = [
    "EvolutionaryInferenceEngine",
]
