"""
Symbolu Robotics Decoders
=========================

12D-to-actuator command decoding modules.

Patent Formulas Used:
- B1-B3: BCVF for action selection
- S6: Coherence-weighted output scaling
"""

from symbolu_robotics.decoders.base_decoder import BaseDecoder, DecoderConfig
from symbolu_robotics.decoders.motor_decoder import MotorDecoder
from symbolu_robotics.decoders.gripper_decoder import GripperDecoder
from symbolu_robotics.decoders.locomotion_decoder import LocomotionDecoder
from symbolu_robotics.decoders.speech_decoder import SpeechDecoder

__all__ = [
    "BaseDecoder",
    "DecoderConfig",
    "MotorDecoder",
    "GripperDecoder",
    "LocomotionDecoder",
    "SpeechDecoder",
]
