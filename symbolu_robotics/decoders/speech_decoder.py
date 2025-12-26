"""
Speech Decoder for Robotics
============================

12D -> Voice synthesis parameters.

Layer Interpretation:
- O5_COGNITION: Speech content selection
- O7_REASONING: Message complexity
- O8_PURPOSE: Communication intent
- O10_UNIFYING: Multi-agent addressing
"""

from typing import Optional, List
from dataclasses import dataclass
import numpy as np

from symbolu_robotics.decoders.base_decoder import BaseDecoder, DecoderConfig
from symbolu_robotics.core.types import ActuatorCommand, Layer12D


@dataclass
class SpeechCommand:
    """Speech synthesis command."""
    text: str = ""
    pitch: float = 1.0        # Relative pitch (0.5 - 2.0)
    speed: float = 1.0        # Relative speed (0.5 - 2.0)
    volume: float = 1.0       # Volume (0.0 - 1.0)
    urgency: float = 0.0      # Urgency level (0.0 - 1.0)
    target_agents: List[str] = None  # Multi-agent addressing

    def __post_init__(self):
        if self.target_agents is None:
            self.target_agents = []


class SpeechDecoder(BaseDecoder):
    """12D to speech synthesis parameters."""

    def __init__(
        self,
        config: Optional[DecoderConfig] = None,
        phrases: Optional[dict] = None
    ):
        super().__init__(config)
        # Default phrase library indexed by dominant layer
        self.phrases = phrases or {
            "idle": "Standing by.",
            "moving": "Moving now.",
            "grasping": "Grasping object.",
            "obstacle": "Obstacle detected.",
            "goal_reached": "Goal reached.",
            "error": "Error encountered.",
            "waiting": "Waiting for command.",
        }

    @property
    def decoder_name(self) -> str:
        return "speech"

    def _decode_internal(self, layer_12d: Layer12D) -> ActuatorCommand:
        # This returns ActuatorCommand for interface compatibility
        # Actual speech command is available via get_speech_command
        return ActuatorCommand()

    def get_speech_command(self, layer_12d: Layer12D) -> SpeechCommand:
        """Get speech synthesis parameters from 12D state."""
        execution = layer_12d[2]      # O3_EXECUTION
        cognition = layer_12d[4]      # O5_COGNITION
        reasoning = layer_12d[6]      # O7_REASONING
        purpose = layer_12d[7]        # O8_PURPOSE
        unifying = layer_12d[9]       # O10_UNIFYING
        safety = layer_12d[11]        # O12_ABSOLVING

        # Select phrase based on dominant state
        if safety > 0.7:
            text = self.phrases.get("obstacle", "Caution.")
            urgency = safety
        elif execution > 0.6:
            text = self.phrases.get("moving", "In motion.")
            urgency = 0.3
        elif purpose > 0.6:
            text = self.phrases.get("goal_reached", "Complete.")
            urgency = 0.1
        else:
            text = self.phrases.get("idle", "Ready.")
            urgency = 0.0

        # Speech parameters from layers
        pitch = 0.8 + reasoning * 0.4  # Higher reasoning = higher pitch
        speed = 0.7 + execution * 0.6  # Higher execution = faster
        volume = 0.5 + purpose * 0.5   # Higher purpose = louder

        # Multi-agent addressing
        target_agents = []
        if unifying > 0.5:
            target_agents = ["all"]  # Broadcast

        return SpeechCommand(
            text=text,
            pitch=float(np.clip(pitch, 0.5, 2.0)),
            speed=float(np.clip(speed, 0.5, 2.0)),
            volume=float(np.clip(volume, 0.0, 1.0)),
            urgency=float(urgency),
            target_agents=target_agents
        )

    def set_phrase(self, key: str, phrase: str) -> None:
        """Set a phrase in the library."""
        self.phrases[key] = phrase
