"""
SOULPI Core - Symbol-U Intelligence Engine
==========================================

Active submodules:
- smi: Semantic Mismatch Index computation (vritti mapping, acoustic mapping, aspect mapping)
- stitching: Candidate response scoring and cross-domain reasoning
- consciousness: Unified Consciousness Formula (P26)
- coherence: Multi-turn coherence tracking (P10/P12)
- counterfactual: Counterfactual sandbox simulation (P25)
- continuity: Adaptive continuity engine (P37)
- predictive: Identity memory and persona drift prediction

Shared data (cross-layer contract types):
- models: Core data structures (SMIResult, BhavaState, EntropyState, etc.)
         See ``models.GOVERNANCE_SAFE_TYPES`` for types safe for governance adapters.
- constants: Canonical kosha/ontology mappings and thresholds
         See ``constants.GOVERNANCE_SAFE_CONSTANTS`` for cross-layer constants.
- generation_gate: Generation access control gate
- ledger_generation_attest: Attestation blob generation

Placeholder submodules (NOT IMPLEMENTED — retained for future formula work):
- bhava: Consciousness state geometry (all methods raise NotImplementedError)
- energy: Energy word detection (all methods raise NotImplementedError)
- regulators: Three-force decision framework (all methods raise NotImplementedError)

Phase 0 Cleanup Notes:
- CoreInterface and CorePipeline facades removed (all methods were NotImplementedError)
- core/entropy/ stub removed (dead placeholder; real entropy lives in agentic/entropy/)
- See CANONICAL AUTHORITIES below for runtime signal sources

CANONICAL AUTHORITIES (runtime):
- Runtime vritti (cross-layer coherence): agentic/chitta_vritti/
- Runtime vritti (phonemic/syllable-level): agentic/core/smi/vritti_mapping.py (complementary)
- Runtime guna (pipeline-level, deterministic): agentic/guna_modulation/guna_derivation.py
- Runtime guna (token-level inference): agentic/inference/guna_inference.py (complementary)
- Runtime entropy: agentic/entropy/
"""

from agentic.core.models import (
    SyllableAnalysis,
    WordAnalysis,
    EntropyState,
    BhavaState,
    RecursionState,
    CandidateResponse,
    SMIResult,
    DeliveryMode,
    AnalysisResult,
)

__all__ = [
    # Core data models (always available)
    "SyllableAnalysis",
    "WordAnalysis",
    "EntropyState",
    "BhavaState",
    "RecursionState",
    "CandidateResponse",
    "SMIResult",
    "DeliveryMode",
    "AnalysisResult",
]
