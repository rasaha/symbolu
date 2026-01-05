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
- Ontological alignment scoring
- Tiered inference modes (Fast/Standard/Sovereign)

Phase 1 (Priority 1 - Critical):
- EvolutionaryInferenceEngine: Karma buffer and cross-sequence state

Phase 2 (Priority 2 - Important):
- InferenceMetacognition: Real-time generation quality monitoring
- InferenceGunas: Inference-time Guna approximation
- CSRInferenceGuard: CSR safety layer application
- SovereignInferenceScorer: Ontological alignment scoring

Phase 3 (Priority 3 - Orchestration):
- InferenceManager: Central orchestrator with tiered modes

Usage:
------
    from symbolu.inference import InferenceManager, InferenceMode

    # Recommended: Use InferenceManager for unified access
    manager = InferenceManager(model, mode=InferenceMode.SOVEREIGN)
    output, metrics = manager.generate(input_ids, max_new_tokens=100)

    # Alternative: Use individual components directly
    from symbolu.inference import (
        EvolutionaryInferenceEngine,
        InferenceMetacognition,
        InferenceGunas,
        CSRInferenceGuard,
        SovereignInferenceScorer,
    )

    # Create inference engine with karma persistence
    engine = EvolutionaryInferenceEngine(model)

    # Add quality monitoring
    metacog = InferenceMetacognition()
    gunas = InferenceGunas()

    # Add safety guard
    guard = CSRInferenceGuard(lm_head=model.lm_head)

    # Add scoring
    scorer = SovereignInferenceScorer(dim=768)
"""

from .evolutionary_inference import EvolutionaryInferenceEngine
from .metacognitive_monitor import InferenceMetacognition, Recommendation
from .guna_inference import InferenceGunas
from .csr_inference import CSRInferenceGuard, EntropySinkInference, SynthesisGateInference
from .sovereign_scorer import SovereignInferenceScorer, SOVEREIGN_R_MATRIX, VRTTI_NAMES
from .manager import InferenceManager, InferenceMode

__all__ = [
    # Phase 3 - Orchestration (recommended entry point)
    "InferenceManager",
    "InferenceMode",
    # Phase 1
    "EvolutionaryInferenceEngine",
    # Phase 2 - Metacognition
    "InferenceMetacognition",
    "Recommendation",
    # Phase 2 - Gunas
    "InferenceGunas",
    # Phase 2 - CSR Safety
    "CSRInferenceGuard",
    "EntropySinkInference",
    "SynthesisGateInference",
    # Phase 2 - Sovereign Scoring
    "SovereignInferenceScorer",
    "SOVEREIGN_R_MATRIX",
    "VRTTI_NAMES",
]
