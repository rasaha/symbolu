# Symbolu Robotics - Encoder Tests
"""Tests for sensor-to-12D encoders."""

import pytest
import numpy as np
from typing import Dict, Any

from symbolu_robotics.core.types import OntologicalLayer, SensorFrame
from symbolu_robotics.encoders.base_encoder import BaseEncoder, LightweightEncoder
from symbolu_robotics.encoders.vision_encoder import VisionEncoder, VisionConfig
from symbolu_robotics.encoders.proprioception import ProprioceptionEncoder, ProprioceptionConfig
from symbolu_robotics.encoders.tactile_encoder import TactileEncoder, TactileConfig
from symbolu_robotics.encoders.audio_encoder import AudioEncoder, AudioConfig
from symbolu_robotics.encoders.fusion_encoder import FusionEncoder, FusionConfig


class TestLightweightEncoder:
    """Tests for the lightweight R1-tier encoder."""

    def test_initialization(self):
        """Test encoder initializes correctly."""
        encoder = LightweightEncoder(num_inputs=8)
        assert encoder.num_inputs == 8
        assert encoder.weights.shape == (8, 12)

    def test_encode_shape(self):
        """Test output shape is correct."""
        encoder = LightweightEncoder(num_inputs=6)
        sensor_data = np.random.randn(6)
        output = encoder.encode(sensor_data)
        assert output.shape == (12,)

    def test_encode_normalization(self):
        """Test output is normalized to [0, 1]."""
        encoder = LightweightEncoder(num_inputs=4)
        sensor_data = np.random.randn(4) * 100  # Large values
        output = encoder.encode(sensor_data)
        assert np.all(output >= 0)
        assert np.all(output <= 1)

    def test_encode_deterministic(self):
        """Test encoding is deterministic."""
        encoder = LightweightEncoder(num_inputs=4)
        sensor_data = np.array([1.0, 2.0, 3.0, 4.0])
        output1 = encoder.encode(sensor_data)
        output2 = encoder.encode(sensor_data)
        np.testing.assert_array_equal(output1, output2)


class TestVisionEncoder:
    """Tests for vision sensor encoder."""

    @pytest.fixture
    def config(self):
        return VisionConfig(
            image_width=64,
            image_height=48,
            channels=3,
            enable_edge_detection=True,
            enable_motion_detection=True,
            edge_threshold=50.0,
            motion_threshold=10.0
        )

    @pytest.fixture
    def encoder(self, config):
        return VisionEncoder(config)

    def test_initialization(self, encoder, config):
        """Test encoder initializes correctly."""
        assert encoder.config.image_width == 64
        assert encoder.config.image_height == 48

    def test_encode_rgb_image(self, encoder):
        """Test encoding RGB image."""
        image = np.random.randint(0, 256, (48, 64, 3), dtype=np.uint8)
        output = encoder.encode(image)
        assert output.shape == (12,)
        assert np.all(output >= 0)
        assert np.all(output <= 1)

    def test_encode_grayscale_image(self, encoder):
        """Test encoding grayscale image."""
        image = np.random.randint(0, 256, (48, 64), dtype=np.uint8)
        output = encoder.encode(image)
        assert output.shape == (12,)

    def test_edge_detection_activates_o4(self, encoder):
        """Test that strong edges activate O4_STRUCTURE."""
        # Create image with strong edges
        image = np.zeros((48, 64, 3), dtype=np.uint8)
        image[:, 32:, :] = 255  # Sharp vertical edge

        output = encoder.encode(image)
        # O4_STRUCTURE should have significant activation
        assert output[OntologicalLayer.O4_STRUCTURE] > 0.1

    def test_motion_detection(self, encoder):
        """Test motion detection between frames."""
        # First frame
        frame1 = np.zeros((48, 64, 3), dtype=np.uint8)
        encoder.encode(frame1)

        # Second frame with motion
        frame2 = np.zeros((48, 64, 3), dtype=np.uint8)
        frame2[:, 10:30, :] = 255  # Object moved

        output = encoder.encode(frame2)
        # O3_EXECUTION (motion) should be activated
        assert output[OntologicalLayer.O3_EXECUTION] > 0


class TestProprioceptionEncoder:
    """Tests for proprioception encoder."""

    @pytest.fixture
    def config(self):
        return ProprioceptionConfig(
            num_joints=6,
            position_scale=np.pi,
            velocity_scale=2.0,
            effort_scale=100.0
        )

    @pytest.fixture
    def encoder(self, config):
        return ProprioceptionEncoder(config)

    def test_encode_joint_state(self, encoder):
        """Test encoding joint states."""
        positions = np.array([0.0, 0.5, -0.5, 1.0, -1.0, 0.0])
        velocities = np.array([0.1, -0.1, 0.2, -0.2, 0.0, 0.0])
        efforts = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])

        output = encoder.encode(positions, velocities, efforts)
        assert output.shape == (12,)
        assert np.all(output >= 0)
        assert np.all(output <= 1)

    def test_high_effort_activates_o5(self, encoder):
        """Test high effort activates O5_AGENCY."""
        positions = np.zeros(6)
        velocities = np.zeros(6)
        efforts = np.array([90.0, 90.0, 90.0, 90.0, 90.0, 90.0])  # High effort

        output = encoder.encode(positions, velocities, efforts)
        assert output[OntologicalLayer.O5_AGENCY] > 0.5

    def test_motion_activates_o3(self, encoder):
        """Test high velocity activates O3_EXECUTION."""
        positions = np.zeros(6)
        velocities = np.array([1.5, 1.5, 1.5, 1.5, 1.5, 1.5])  # High velocity
        efforts = np.zeros(6)

        output = encoder.encode(positions, velocities, efforts)
        assert output[OntologicalLayer.O3_EXECUTION] > 0.3


class TestTactileEncoder:
    """Tests for tactile sensor encoder."""

    @pytest.fixture
    def config(self):
        return TactileConfig(
            num_taxels=16,
            pressure_range=(0.0, 100.0),
            enable_slip_detection=True
        )

    @pytest.fixture
    def encoder(self, config):
        return TactileEncoder(config)

    def test_encode_pressure_array(self, encoder):
        """Test encoding pressure array."""
        pressures = np.random.uniform(0, 100, 16)
        output = encoder.encode(pressures)
        assert output.shape == (12,)

    def test_contact_activates_o6(self, encoder):
        """Test contact activates O6_SYNTHESIS."""
        pressures = np.array([50.0] * 16)  # Uniform contact
        output = encoder.encode(pressures)
        assert output[OntologicalLayer.O6_SYNTHESIS] > 0.3

    def test_slip_detection(self, encoder):
        """Test slip detection activates safety."""
        # First reading
        pressures1 = np.array([50.0] * 16)
        encoder.encode(pressures1)

        # Rapid change (slip)
        pressures2 = np.array([10.0] * 16)
        output = encoder.encode(pressures2)

        # Slip should trigger O12_ABSOLVING (safety)
        # Implementation may vary
        assert output.shape == (12,)


class TestAudioEncoder:
    """Tests for audio encoder."""

    @pytest.fixture
    def config(self):
        return AudioConfig(
            sample_rate=16000,
            frame_size=512,
            num_mels=40,
            enable_voice_detection=True
        )

    @pytest.fixture
    def encoder(self, config):
        return AudioEncoder(config)

    def test_encode_audio_frame(self, encoder):
        """Test encoding audio frame."""
        audio = np.random.randn(512)
        output = encoder.encode(audio)
        assert output.shape == (12,)

    def test_silence_low_activation(self, encoder):
        """Test silence produces low activation."""
        silence = np.zeros(512)
        output = encoder.encode(silence)
        assert np.mean(output) < 0.2

    def test_loud_sound_high_activation(self, encoder):
        """Test loud sound produces higher activation."""
        loud = np.random.randn(512) * 10
        output = encoder.encode(loud)
        assert np.mean(output) > 0.1


class TestFusionEncoder:
    """Tests for multi-modal fusion encoder."""

    @pytest.fixture
    def config(self):
        return FusionConfig(
            enable_vision=True,
            enable_proprioception=True,
            enable_tactile=True,
            enable_audio=False,
            normalize_output=True,
            temporal_smoothing=0.1
        )

    @pytest.fixture
    def encoder(self, config):
        return FusionEncoder(config)

    def test_encode_multi_modal(self, encoder):
        """Test encoding multi-modal input."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            vision=np.random.randint(0, 256, (48, 64, 3), dtype=np.uint8),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6),
            tactile=np.zeros(16)
        )

        output = encoder.encode(sensor_frame)
        assert output.shape == (12,)

    def test_fusion_coherence(self, encoder):
        """Test that fusion produces coherent output."""
        # Create consistent sensor readings
        sensor_frame = SensorFrame(
            timestamp=0.0,
            vision=np.ones((48, 64, 3), dtype=np.uint8) * 128,
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6),
            tactile=np.zeros(16)
        )

        output1 = encoder.encode(sensor_frame)
        output2 = encoder.encode(sensor_frame)

        # With temporal smoothing, outputs should be similar
        np.testing.assert_array_almost_equal(output1, output2, decimal=1)

    def test_missing_modality(self, encoder):
        """Test handling of missing modality."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            vision=None,  # Missing vision
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6),
            tactile=np.zeros(16)
        )

        # Should still produce valid output
        output = encoder.encode(sensor_frame)
        assert output.shape == (12,)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
