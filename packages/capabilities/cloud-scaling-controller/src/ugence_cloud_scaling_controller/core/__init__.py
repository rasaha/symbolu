"""Core control modules — domain-agnostic math ported from CG controller."""

from ugence_cloud_scaling_controller.core.plasticity_gate import PlasticityGate
from ugence_cloud_scaling_controller.core.adaptive_gain import AdaptiveGain
from ugence_cloud_scaling_controller.core.damping import Damping
from ugence_cloud_scaling_controller.core.identity_ema import IdentityEMA
from ugence_cloud_scaling_controller.core.coherence import CoherenceModel
from ugence_cloud_scaling_controller.core.replay_buffer import ReplayBuffer

__all__ = [
    "PlasticityGate",
    "AdaptiveGain",
    "Damping",
    "IdentityEMA",
    "CoherenceModel",
    "ReplayBuffer",
]
