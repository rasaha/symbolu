"""
Fusion Encoder for Robotics
============================

Multi-modal sensor fusion -> 12D encoding.

Uses patent formulas:
- U1: Cross-modal correlation matrix
- S4: Cosine similarity between modalities
- S5: Combined semantic entropy

Combines outputs from:
- Vision (camera, LIDAR)
- Proprioception (joints)
- Tactile (touch)
- Audio (microphone)
"""

from typing import Dict, List, Optional, Tuple
import numpy as np

from symbolu_robotics.encoders.base_encoder import BaseEncoder, EncoderConfig, EncoderMetrics
from symbolu_robotics.encoders.vision_encoder import VisionEncoder
from symbolu_robotics.encoders.proprioception import ProprioceptionEncoder
from symbolu_robotics.encoders.tactile_encoder import TactileEncoder
from symbolu_robotics.encoders.audio_encoder import AudioEncoder
from symbolu_robotics.core.types import SensorFrame, Layer12D


class FusionEncoder(BaseEncoder):
    """Multi-modal fusion to 12D layer encoding using patent formulas."""

    def __init__(
        self,
        config: Optional[EncoderConfig] = None,
        enable_vision: bool = True,
        enable_proprioception: bool = True,
        enable_tactile: bool = True,
        enable_audio: bool = False,
        modality_weights: Optional[Dict[str, float]] = None
    ):
        super().__init__(config)

        self.encoders: Dict[str, BaseEncoder] = {}
        if enable_vision:
            self.encoders["vision"] = VisionEncoder(config)
        if enable_proprioception:
            self.encoders["proprioception"] = ProprioceptionEncoder(config)
        if enable_tactile:
            self.encoders["tactile"] = TactileEncoder(config)
        if enable_audio:
            self.encoders["audio"] = AudioEncoder(config)

        # Default equal weights
        if modality_weights is None:
            n = len(self.encoders)
            modality_weights = {name: 1.0 / n for name in self.encoders}
        self.modality_weights = modality_weights

        # Store individual outputs for coherence analysis
        self._modality_outputs: Dict[str, Layer12D] = {}

    @property
    def encoder_name(self) -> str:
        return "fusion"

    @property
    def required_sensors(self) -> Tuple[str, ...]:
        sensors = []
        for encoder in self.encoders.values():
            sensors.extend(encoder.required_sensors)
        return tuple(set(sensors))

    def _encode_internal(self, sensor_frame: SensorFrame) -> Layer12D:
        # Get outputs from each modality
        self._modality_outputs = {}
        outputs = []
        weights = []

        for name, encoder in self.encoders.items():
            output = encoder.encode(sensor_frame)
            self._modality_outputs[name] = output
            outputs.append(output)
            weights.append(self.modality_weights.get(name, 1.0))

        if not outputs:
            return np.zeros(12, dtype=np.float32)

        # Normalize weights
        weights = np.array(weights)
        weights = weights / np.sum(weights)

        # Weighted combination
        outputs = np.array(outputs)
        fused = np.sum(outputs * weights[:, np.newaxis], axis=0)

        # Apply U1: Coherence-weighted adjustment
        coherence = self._compute_cross_modal_coherence(outputs)
        if coherence < 0.5:
            # Low coherence: reduce confidence, boost O12_ABSOLVING
            fused *= coherence
            fused[11] = max(fused[11], 1.0 - coherence)

        # O11_INTEGRATION: Fusion quality indicator
        fused[10] = coherence

        return fused

    def _compute_cross_modal_coherence(self, outputs: np.ndarray) -> float:
        """
        Compute U1-based cross-modal coherence.

        Uses simplified correlation between modality outputs.
        """
        if len(outputs) < 2:
            return 1.0

        # S4: Pairwise cosine similarities
        similarities = []
        for i in range(len(outputs)):
            for j in range(i + 1, len(outputs)):
                norm_i = np.linalg.norm(outputs[i])
                norm_j = np.linalg.norm(outputs[j])
                if norm_i > 0 and norm_j > 0:
                    sim = np.dot(outputs[i], outputs[j]) / (norm_i * norm_j)
                    similarities.append(sim)

        if not similarities:
            return 1.0

        # Average similarity as coherence measure
        return float(np.mean(similarities))

    def get_modality_outputs(self) -> Dict[str, Layer12D]:
        """Get individual modality outputs."""
        return self._modality_outputs.copy()

    def get_coherence_matrix(self) -> np.ndarray:
        """
        Compute U1 coherence matrix between modalities.

        Returns NxN matrix where N is number of modalities.
        """
        names = list(self._modality_outputs.keys())
        n = len(names)
        matrix = np.eye(n)

        for i in range(n):
            for j in range(i + 1, n):
                out_i = self._modality_outputs[names[i]]
                out_j = self._modality_outputs[names[j]]
                norm_i = np.linalg.norm(out_i)
                norm_j = np.linalg.norm(out_j)
                if norm_i > 0 and norm_j > 0:
                    sim = np.dot(out_i, out_j) / (norm_i * norm_j)
                    matrix[i, j] = sim
                    matrix[j, i] = sim

        return matrix

    def reset(self) -> None:
        super().reset()
        for encoder in self.encoders.values():
            encoder.reset()
        self._modality_outputs = {}
