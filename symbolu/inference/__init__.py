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
- 9:3 Authority/Sensory layer configuration
- Checkpoint metadata for auto-configuration

Phase 1 (Priority 1 - Critical):
- EvolutionaryInferenceEngine: Karma buffer and cross-sequence state

Phase 2 (Priority 2 - Important):
- InferenceMetacognition: Real-time generation quality monitoring
- InferenceGunas: Inference-time Guna approximation
- CSRInferenceGuard: CSR safety layer application
- SovereignInferenceScorer: Ontological alignment scoring

Phase 3 (Priority 3 - Orchestration & Enhancements):
- InferenceManager: Central orchestrator with tiered modes
- LayerInferenceConfig: 9:3 hierarchical split configuration
- Checkpoint utilities: Save/load with inference hints

Usage:
------
    from symbolu.inference import InferenceManager, InferenceMode

    # Recommended: Use InferenceManager for unified access
    manager = InferenceManager(model, mode=InferenceMode.SOVEREIGN)
    output, metrics = manager.generate(input_ids, max_new_tokens=100)

    # Load model with auto-configured inference settings
    from symbolu.inference import load_sovereign_config, LayerInferenceConfig

    config = load_sovereign_config("checkpoint.pt")
    print(f"Recommended alpha: {config.recommended_alpha}")
    print(f"Split: {config.authority_sensory_split}")

    # Check layer configuration
    print(LayerInferenceConfig.summarize())
"""

from .evolutionary_inference import EvolutionaryInferenceEngine
from .metacognitive_monitor import InferenceMetacognition, Recommendation
from .guna_inference import InferenceGunas
from .csr_inference import CSRInferenceGuard, EntropySinkInference, SynthesisGateInference
from .sovereign_scorer import SovereignInferenceScorer, SOVEREIGN_R_MATRIX, VRTTI_NAMES
from .manager import InferenceManager, InferenceMode
from .layer_config import (
    LayerInferenceConfig,
    LayerType,
    CachePriority,
    AUTHORITY_LAYERS,
    SENSORY_LAYERS,
    LAYER_NAMES,
)
from .checkpoint_utils import (
    InferenceConfig,
    save_sovereign_checkpoint,
    load_sovereign_config,
    load_model_with_config,
    get_checkpoint_info,
)

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
    # Phase 3 - Layer Configuration
    "LayerInferenceConfig",
    "LayerType",
    "CachePriority",
    "AUTHORITY_LAYERS",
    "SENSORY_LAYERS",
    "LAYER_NAMES",
    # Phase 3 - Checkpoint Utilities
    "InferenceConfig",
    "save_sovereign_checkpoint",
    "load_sovereign_config",
    "load_model_with_config",
    "get_checkpoint_info",
]
