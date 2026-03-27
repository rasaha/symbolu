"""
Experiential Learning for Conscious Generation (CG) Training.

Models the five analogs of natural experience in AI training:

1. ExperientialLossSignal — Multi-modal, cross-frequency loss that propagates
   differently across modalities (semantic, temporal, somatic-analog). Maps to
   FSCS frequency-stratified coherence where error at one frequency resonates
   into others.

2. VrittiResistanceGate — Vritti-gated update mechanism that introduces
   resistance fields regulating how much a gradient update restructures a
   given region. Gates are state-dependent, stake-sensitive, and temporally
   variable.

3. OfflineConsolidationCycle — Sleep analog that replays high-loss events,
   reconciles contradictory updates, prunes low-salience memories, and
   enforces cross-layer coherence during mandatory offline phases.

4. SalienceWeighter — Consequence-based error weighting that develops
   "scar tissue" in regions that have experienced cascade failures.
   Errors that propagate downstream leave deeper traces.

5. IdentityLayer — Persistent self-model separate from task weights,
   updatable only by sufficiently profound error signals. Maps to the
   12-layer ontological architecture where deeper layers resist surface
   task errors.

Flow:
    Input -> Prediction
         |
    Error Signal (multi-modal, not scalar)
         |
    Salience Gate (is this consequential?)
         |
    Vritti Resistance Field (does the system resist this update?)
         |
    If resistance overcome -> propagate to identity layer
    If resistance holds -> queue for offline consolidation
         |
    Offline Cycle (sleep analog) -> reconcile, prune, deepen
         |
    Emergent reorganization (self-model revision)

Reference: docs/design/EXPERIENTIAL_LEARNING_DESIGN.md
"""

from symbolu.training.conscious_generation.experiential.experiential_loss import (
    ExperientialLossSignal,
    ExperientialLossConfig,
)
from symbolu.training.conscious_generation.experiential.vritti_resistance_gate import (
    VrittiResistanceGate,
    VrittiResistanceConfig,
)
from symbolu.training.conscious_generation.experiential.offline_consolidation import (
    OfflineConsolidationCycle,
    ConsolidationConfig,
)
from symbolu.training.conscious_generation.experiential.salience_weighter import (
    SalienceWeighter,
    SalienceConfig,
)
from symbolu.training.conscious_generation.experiential.identity_layer import (
    IdentityLayer,
    IdentityLayerConfig,
)
from symbolu.training.conscious_generation.experiential.experiential_training_loop import (
    ExperientialTrainingLoop,
    ExperientialTrainingConfig,
)

__all__ = [
    "ExperientialLossSignal",
    "ExperientialLossConfig",
    "VrittiResistanceGate",
    "VrittiResistanceConfig",
    "OfflineConsolidationCycle",
    "ConsolidationConfig",
    "SalienceWeighter",
    "SalienceConfig",
    "IdentityLayer",
    "IdentityLayerConfig",
    "ExperientialTrainingLoop",
    "ExperientialTrainingConfig",
]
