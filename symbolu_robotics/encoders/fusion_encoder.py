"""
Fusion Encoder for Robotics
============================

Multi-modal sensor fusion -> 12D encoding.

Implements USE (Unified Sensor Encoding) patent formulas:
- U1: Cross-modal correlation matrix for sensor coherence
- U2: Coherence-weighted fusion of modalities
- U3: Temporal alignment via EMA smoothing
- U4: Confidence estimation from entropy

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
from symbolu_robotics.formulas.use import (
    USEFusion,
    USEConfig,
    compute_correlation_matrix,
    compute_confidence,
    FusionResult,
)
from symbolu_robotics.formulas.scc import compute_semantic_entropy


class FusionEncoder(BaseEncoder):
    """
    Multi-modal fusion to 12D layer encoding using USE patent formulas.

    Implements U1-U4 for coherence-weighted sensor fusion with temporal
    alignment and confidence estimation.
    """

    def __init__(
        self,
        config: Optional[EncoderConfig] = None,
        enable_vision: bool = True,
        enable_proprioception: bool = True,
        enable_tactile: bool = True,
        enable_audio: bool = False,
        temporal_alpha: float = 0.3,
        coherence_threshold: float = 0.3,
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

        # USE fusion system (U1-U4)
        self._use_fusion = USEFusion(USEConfig(
            temporal_alpha=temporal_alpha,
            coherence_threshold=coherence_threshold,
            normalize_output=True,
        ))

        # Store individual outputs and fusion result
        self._modality_outputs: Dict[str, Layer12D] = {}
        self._last_fusion_result: Optional[FusionResult] = None

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
        """
        Encode sensor frame to 12D using USE formulas (U1-U4).

        Process:
        1. Encode each modality to 12D
        2. U1: Compute cross-modal correlation matrix
        3. U2: Coherence-weighted fusion
        4. U3: Temporal alignment (handled by USEFusion)
        5. U4: Confidence estimation
        """
        # Get outputs from each modality encoder
        self._modality_outputs = {}
        for name, encoder in self.encoders.items():
            output = encoder.encode(sensor_frame)
            self._modality_outputs[name] = output
            # U3: Update USE fusion with temporal alignment
            self._use_fusion.update(name, output)

        if not self._modality_outputs:
            return np.zeros(12, dtype=np.float32)

        # U1 + U2: Perform coherence-weighted fusion
        self._last_fusion_result = self._use_fusion.fuse()
        fused = self._last_fusion_result.fused_vector.copy()

        # S5: Compute semantic entropy for monitoring
        entropy = compute_semantic_entropy(fused)

        # Apply coherence-based adjustments
        coherence = self._last_fusion_result.coherence_score
        confidence = self._last_fusion_result.confidence

        if coherence < 0.5:
            # Low coherence: reduce confidence, boost O12_ABSOLVING (safety)
            fused *= coherence
            fused[11] = max(fused[11], 1.0 - coherence)

        # O11_INFORMING: Store fusion quality
        fused[10] = coherence

        # Normalize to [0, 1] range
        fused = np.clip(fused, 0.0, 1.0)

        return fused.astype(np.float32)

    def get_coherence_score(self) -> float:
        """Get overall coherence from last fusion (U1)."""
        if self._last_fusion_result is None:
            return 0.0
        return self._last_fusion_result.coherence_score

    def get_confidence(self) -> float:
        """Get confidence from last fusion (U4)."""
        if self._last_fusion_result is None:
            return 0.0
        return self._last_fusion_result.confidence

    def get_modality_weights(self) -> Dict[str, float]:
        """Get coherence-based modality weights (U2)."""
        if self._last_fusion_result is None:
            return {}
        return self._last_fusion_result.modality_weights

    def detect_sensor_failure(self, threshold: float = 0.2) -> List[str]:
        """
        Detect potential sensor failures from low coherence.

        Uses U1 correlation to identify inconsistent modalities.
        """
        return self._use_fusion.detect_sensor_failure(threshold)

    def get_modality_outputs(self) -> Dict[str, Layer12D]:
        """Get individual modality outputs."""
        return self._modality_outputs.copy()

    def get_coherence_matrix(self) -> np.ndarray:
        """
        Get U1 coherence matrix between modalities.

        Returns NxN matrix where N is number of modalities.
        Uses compute_correlation_matrix from USE formulas.
        """
        if not self._modality_outputs:
            return np.array([[]])

        # U1: Use formula implementation
        return compute_correlation_matrix(self._modality_outputs)

    def get_fusion_result(self) -> Optional[FusionResult]:
        """Get complete fusion result with all USE metrics."""
        return self._last_fusion_result

    def reset(self) -> None:
        super().reset()
        for encoder in self.encoders.values():
            encoder.reset()
        self._modality_outputs = {}
        self._last_fusion_result = None
        self._use_fusion.reset()
