"""Core control modules — domain-agnostic math ported from CG controller."""

from symbolu_core.cloud_controller.core.plasticity_gate import PlasticityGate
from symbolu_core.cloud_controller.core.adaptive_gain import AdaptiveGain
from symbolu_core.cloud_controller.core.damping import Damping
from symbolu_core.cloud_controller.core.identity_ema import IdentityEMA
from symbolu_core.cloud_controller.core.coherence import CoherenceModel
from symbolu_core.cloud_controller.core.replay_buffer import ReplayBuffer

__all__ = [
    "PlasticityGate",
    "AdaptiveGain",
    "Damping",
    "IdentityEMA",
    "CoherenceModel",
    "ReplayBuffer",
]
