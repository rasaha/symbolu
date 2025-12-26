"""
Vision Encoder for Robotics
============================

Camera/LIDAR -> 12D encoding.

Layer Mapping:
- Edges/shapes -> O4_STRUCTURE
- Motion vectors -> O3_EXECUTION
- Object recognition -> O5_COGNITION
- Spatial layout -> O9_WITNESSES
- Depth discontinuities -> O12_ABSOLVING (obstacles)
"""

from typing import Tuple, Optional
import numpy as np

from symbolu_robotics.encoders.base_encoder import BaseEncoder, EncoderConfig
from symbolu_robotics.core.types import SensorFrame, Layer12D


class VisionEncoder(BaseEncoder):
    """Camera/LIDAR to 12D layer encoding."""

    def __init__(self, config: Optional[EncoderConfig] = None):
        super().__init__(config)
        self._prev_frame: Optional[np.ndarray] = None

    @property
    def encoder_name(self) -> str:
        return "vision"

    @property
    def required_sensors(self) -> Tuple[str, ...]:
        return ("rgb_image", "depth_image")

    def _encode_internal(self, sensor_frame: SensorFrame) -> Layer12D:
        layer_values = np.zeros(12, dtype=np.float32)

        # O1_POTENTIAL: Sensor readiness
        if sensor_frame.rgb_image is not None or sensor_frame.depth_image is not None:
            layer_values[0] = 1.0

        # Process RGB image
        if sensor_frame.rgb_image is not None:
            frame = sensor_frame.rgb_image

            # O4_STRUCTURE: Edge density (Sobel approximation)
            gray = np.mean(frame, axis=2) if len(frame.shape) == 3 else frame
            dx = np.abs(np.diff(gray, axis=1))
            dy = np.abs(np.diff(gray, axis=0))
            edge_density = (np.mean(dx) + np.mean(dy)) / 255.0
            layer_values[3] = min(1.0, edge_density * 5)

            # O3_EXECUTION: Motion detection (frame difference)
            if self._prev_frame is not None and self._prev_frame.shape == frame.shape:
                motion = np.mean(np.abs(frame.astype(float) - self._prev_frame.astype(float)))
                layer_values[2] = min(1.0, motion / 50.0)
            self._prev_frame = frame.copy()

            # O5_COGNITION: Object salience (contrast)
            contrast = np.std(gray) / 128.0
            layer_values[4] = min(1.0, contrast)

        # Process depth image
        if sensor_frame.depth_image is not None:
            depth = sensor_frame.depth_image

            # O9_WITNESSES: Spatial entropy
            depth_normalized = depth / (np.max(depth) + 1e-6)
            spatial_entropy = np.std(depth_normalized)
            layer_values[8] = min(1.0, spatial_entropy * 2)

            # O12_ABSOLVING: Obstacle proximity
            min_depth = np.min(depth[depth > 0]) if np.any(depth > 0) else 10.0
            layer_values[11] = max(0.0, 1.0 - min_depth / 2.0)  # Within 2m

        # Process LIDAR
        if sensor_frame.lidar_points is not None:
            points = sensor_frame.lidar_points
            if len(points) > 0:
                # O9_WITNESSES: Point cloud spread
                spread = np.std(points, axis=0)
                layer_values[8] = max(layer_values[8], np.mean(spread) / 10.0)

                # O12_ABSOLVING: Closest point
                distances = np.linalg.norm(points, axis=1)
                min_dist = np.min(distances)
                layer_values[11] = max(layer_values[11], 1.0 - min_dist / 2.0)

        return layer_values

    def reset(self) -> None:
        super().reset()
        self._prev_frame = None
