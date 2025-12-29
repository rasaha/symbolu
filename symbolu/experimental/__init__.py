"""
SymbolU Experimental: Ontological State-Delta Training
=======================================================

This is a separate experimental tier exploring a paradigm shift from
token-centric to meaning-centric training.

Three-Tier Model Hierarchy:
---------------------------
Tier 1: Token-Centric (Standard LLM)
    - cross_entropy, contrastive, infonce losses
    - Predicts: P(token_{t+1} | context)
    - Memory: O(B·T·V) - 200GB at 1M context

Tier 2: State-Delta (Current Implementation)
    - state_delta loss in train.py
    - Predicts: ΔH = H_{t+1} - H_t (hidden space)
    - Memory: O(B·T·d) - 3GB at 1M context
    - 65x reduction, but still opaque

Tier 3: Ontological State-Delta (THIS MODULE - Experimental)
    - Predicts: ΔS = S_{t+1} - S_t (meaning space)
    - States are STRUCTURED: phonemes, ontology, constraints
    - Memory: O(B·T·s) where s << d - ~600MB at 1M context
    - 300x reduction AND interpretable

Key Insight:
-----------
"Traditional LLMs learn what word to say next;
 State-delta training learns how understanding itself should change."

Components:
-----------
- cognitive_state.py: CognitiveState dataclass and operations
- phoneme_encoder.py: Text → phoneme energy distribution
- ontology_mapper.py: Phonemes → Bhava state position
- ontological_trainer.py: Training loop for Tier 3
"""

from .cognitive_state import CognitiveState, StateDelta
