"""
Hard Diagnostic Probe Library for PhaseAttention vs Quadratic Attention
=======================================================================

Refactored modular package from the monolithic train_hard_probes.py (13,758 lines).

Package Structure
-----------------

Core modules:
    imports         Centralized imports with availability flags for optional deps
    contracts       No-write contract enforcement (V10.6.2) and shape validation
    config          Config and SRKPhaseLearningConfig dataclasses
    diagnostics     SRK, Kosha, Witness, and layer influence diagnostic modules
    vocabulary      Hard probe vocabulary (48 tokens, train/test entity/role splits)
    schemas         Schema types, split types, binding state, 7 schema generators
    dataset         HardProbeDataset and collation utilities
    attention       QuadraticAttention and PhaseAttention mechanisms
    models          TransformerBlock, HybridTransformer, HardProbeTransformer
    protected       Protected Phase architecture (no gradient competition)
    evaluation      Evaluation, ablation, and rotation test functions
    language        WikiText, AssociativeRecall, Binding Cache architectures
    training        Main training loop (train_real_language)
    cli             CLI argument parser (~200 args) and main entry point

Benchmark modules (benchmarks/):
    interference            Text proposal scoring (V10.5)
    moe_ffn                 Mixture of Experts FFN (V10.6)
    hp_quad                 Hierarchical Phase-Quad (V10.7)
    rlm_phase_quad          RLM + Phase-Quad integration (V10.8)
    reflective_phase_quad   Self-reflective latent revision (V10.9)
    causal_world_model      DAG learning and intervention (V10.10)
    spatial_causal          Spatial reasoning + causal (V10.11)
    adaptation              IA3 + Surgical LoRA (V10.12)
    chunking                Chunking architecture tests (V10.2.1)

Backward Compatibility
----------------------
The original train_hard_probes.py is preserved unchanged. This package
provides an identical modular interface for maintainability and focused
development on individual features.
"""

__version__ = "10.12.0"
