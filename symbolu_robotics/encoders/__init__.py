"""
Symbolu Robotics Encoders
=========================

Sensor-to-12D encoding modules.

Patent Formulas Used:
- U1: Correlation matrix for sensor coherence
- S4: Cosine similarity between modalities
- S5: Semantic entropy monitoring
"""

from symbolu_robotics.encoders.base_encoder import BaseEncoder, EncoderConfig, LightweightEncoder
from symbolu_robotics.encoders.vision_encoder import VisionEncoder
from symbolu_robotics.encoders.proprioception import ProprioceptionEncoder
from symbolu_robotics.encoders.tactile_encoder import TactileEncoder
from symbolu_robotics.encoders.audio_encoder import AudioEncoder
from symbolu_robotics.encoders.fusion_encoder import FusionEncoder

__all__ = [
    "BaseEncoder",
    "EncoderConfig",
    "LightweightEncoder",
    "VisionEncoder",
    "ProprioceptionEncoder",
    "TactileEncoder",
    "AudioEncoder",
    "FusionEncoder",
]
