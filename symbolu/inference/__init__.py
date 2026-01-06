#!/usr/bin/env python3
"""
SymbolU Inference Module
========================

Inference-time components that bridge training capabilities to generation.

This module implements the inference-side equivalents of training components:
- EvolutionaryInferenceEngine: Karma buffer and O12->O1 state persistence
- CSRInferenceGuard: Safety layer with entropy monitoring
- InferenceMetacognition: Real-time generation quality monitoring
- InferenceGunas: Sattva/Rajas/Tamas approximation during generation
- SovereignInferenceScorer: Quality scoring using Sovereign-1 metrics
- LayerInferenceConfig: 6:6 / 9:3 layer configuration for inference

See docs/INFERENCE_HYBRID_TRANSFORMER_GAPS.md for detailed gap analysis.

Author: Sovereign-1 Training Initiative
Date: January 2026
Version: 1.0.0
"""

from .evolutionary_inference import EvolutionaryInferenceEngine
from .csr_inference import CSRInferenceGuard
from .metacognitive_monitor import InferenceMetacognition
from .guna_inference import InferenceGunas
from .sovereign_scorer import SovereignInferenceScorer
from .layer_config import LayerInferenceConfig
from .checkpoint_utils import load_inference_engine, InferenceCheckpointLoader
from .manager import InferenceManager

__all__ = [
    # Core engines
    "EvolutionaryInferenceEngine",
    "CSRInferenceGuard",
    "InferenceManager",

    # Monitoring
    "InferenceMetacognition",
    "InferenceGunas",
    "SovereignInferenceScorer",

    # Configuration
    "LayerInferenceConfig",

    # Utilities
    "load_inference_engine",
    "InferenceCheckpointLoader",
]

__version__ = "1.0.0"
