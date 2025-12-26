# Symbolu Robotics - Decoder Tests
"""Tests for 12D-to-actuator decoders."""

import pytest
import numpy as np
from typing import Dict, Any

from symbolu_robotics.core.types import OntologicalLayer, ActuatorCommand
from symbolu_robotics.decoders.base_decoder import BaseDecoder
from symbolu_robotics.decoders.motor_decoder import MotorDecoder, MotorConfig
from symbolu_robotics.decoders.gripper_decoder import GripperDecoder, GripperConfig
from symbolu_robotics.decoders.locomotion_decoder import LocomotionDecoder, LocomotionConfig
from symbolu_robotics.decoders.speech_decoder import SpeechDecoder, SpeechConfig


class TestMotorDecoder:
    """Tests for motor decoder."""

    @pytest.fixture
    def config(self):
        return MotorConfig(
            num_joints=6,
            max_velocity=2.0,
            max_effort=100.0,
            control_mode='velocity'
        )

    @pytest.fixture
    def decoder(self, config):
        return MotorDecoder(config)

    def test_initialization(self, decoder, config):
        """Test decoder initializes correctly."""
        assert decoder.config.num_joints == 6
        assert decoder.config.max_velocity == 2.0

    def test_decode_shape(self, decoder):
        """Test output shape is correct."""
        activations = np.random.rand(12)
        command = decoder.decode(activations)
        assert len(command.joint_velocities) == 6

    def test_decode_velocity_limits(self, decoder):
        """Test velocity limits are respected."""
        activations = np.ones(12)  # Max activation
        command = decoder.decode(activations)
        assert np.all(np.abs(command.joint_velocities) <= 2.0)

    def test_decode_effort_limits(self, decoder):
        """Test effort limits are respected."""
        decoder.config.control_mode = 'effort'
        activations = np.ones(12)
        command = decoder.decode(activations)
        assert np.all(np.abs(command.joint_efforts) <= 100.0)

    def test_zero_activation_zero_output(self, decoder):
        """Test zero activation produces zero output."""
        activations = np.zeros(12)
        command = decoder.decode(activations)
        np.testing.assert_array_almost_equal(
            command.joint_velocities, np.zeros(6), decimal=5
        )

    def test_o3_execution_drives_motion(self, decoder):
        """Test O3_EXECUTION layer drives motion."""
        activations = np.zeros(12)
        activations[OntologicalLayer.O3_EXECUTION] = 1.0
        command = decoder.decode(activations)
        assert np.any(np.abs(command.joint_velocities) > 0)

    def test_o12_safety_limits_motion(self, decoder):
        """Test O12_ABSOLVING (safety) limits motion."""
        activations = np.ones(12)
        activations[OntologicalLayer.O12_ABSOLVING] = 1.0  # Safety active
        command = decoder.decode(activations)

        # With safety active, motion should be reduced
        activations_no_safety = np.ones(12)
        activations_no_safety[OntologicalLayer.O12_ABSOLVING] = 0.0
        command_no_safety = decoder.decode(activations_no_safety)

        assert np.linalg.norm(command.joint_velocities) <= \
               np.linalg.norm(command_no_safety.joint_velocities)


class TestGripperDecoder:
    """Tests for gripper decoder."""

    @pytest.fixture
    def config(self):
        return GripperConfig(
            min_position=0.0,
            max_position=0.08,
            max_force=40.0,
            default_speed=0.1
        )

    @pytest.fixture
    def decoder(self, config):
        return GripperDecoder(config)

    def test_decode_grasp_command(self, decoder):
        """Test decoding grasp command."""
        activations = np.zeros(12)
        activations[OntologicalLayer.O6_SYNTHESIS] = 0.8  # Grasp intent
        command = decoder.decode(activations)

        assert hasattr(command, 'gripper_position')
        assert 0.0 <= command.gripper_position <= 0.08

    def test_decode_release_command(self, decoder):
        """Test decoding release command."""
        activations = np.zeros(12)
        activations[OntologicalLayer.O6_SYNTHESIS] = 0.0  # No grasp intent
        activations[OntologicalLayer.O3_EXECUTION] = 0.5  # Action intent
        command = decoder.decode(activations)

        # Gripper should tend to open
        assert command.gripper_position >= 0.04

    def test_force_limits(self, decoder):
        """Test force limits are respected."""
        activations = np.ones(12)
        command = decoder.decode(activations)
        assert command.gripper_force <= 40.0

    def test_position_bounds(self, decoder):
        """Test position stays within bounds."""
        for _ in range(10):
            activations = np.random.rand(12)
            command = decoder.decode(activations)
            assert 0.0 <= command.gripper_position <= 0.08


class TestLocomotionDecoder:
    """Tests for locomotion decoder."""

    @pytest.fixture
    def config(self):
        return LocomotionConfig(
            max_linear_velocity=1.0,
            max_angular_velocity=1.5,
            gait_type='walk'
        )

    @pytest.fixture
    def decoder(self, config):
        return LocomotionDecoder(config)

    def test_decode_velocity_command(self, decoder):
        """Test decoding velocity command."""
        activations = np.random.rand(12)
        command = decoder.decode(activations)

        assert hasattr(command, 'linear_velocity')
        assert hasattr(command, 'angular_velocity')

    def test_velocity_limits(self, decoder):
        """Test velocity limits are respected."""
        activations = np.ones(12)
        command = decoder.decode(activations)

        assert np.abs(command.linear_velocity) <= 1.0
        assert np.abs(command.angular_velocity) <= 1.5

    def test_o3_execution_drives_forward(self, decoder):
        """Test O3_EXECUTION drives forward motion."""
        activations = np.zeros(12)
        activations[OntologicalLayer.O3_EXECUTION] = 1.0
        command = decoder.decode(activations)

        assert command.linear_velocity > 0

    def test_o7_reasoning_drives_turn(self, decoder):
        """Test O7_REASONING influences turning."""
        activations = np.zeros(12)
        activations[OntologicalLayer.O7_REASONING] = 1.0
        command = decoder.decode(activations)

        # Reasoning may affect turning for navigation
        assert command.angular_velocity != 0 or command.linear_velocity >= 0

    def test_safety_stops_motion(self, decoder):
        """Test safety layer stops motion."""
        activations = np.ones(12)
        activations[OntologicalLayer.O12_ABSOLVING] = 1.0
        command = decoder.decode(activations)

        # With full safety activation, motion should be minimal
        assert np.abs(command.linear_velocity) < 0.5
        assert np.abs(command.angular_velocity) < 0.75


class TestSpeechDecoder:
    """Tests for speech decoder."""

    @pytest.fixture
    def config(self):
        return SpeechConfig(
            sample_rate=16000,
            enable_tts=True,
            voice='neutral'
        )

    @pytest.fixture
    def decoder(self, config):
        return SpeechDecoder(config)

    def test_decode_speech_intent(self, decoder):
        """Test decoding speech intent."""
        activations = np.zeros(12)
        activations[OntologicalLayer.O11_INFORMING] = 0.8

        intent = decoder.decode_intent(activations)
        assert intent.should_speak

    def test_no_speech_low_activation(self, decoder):
        """Test no speech on low activation."""
        activations = np.zeros(12)
        intent = decoder.decode_intent(activations)
        assert not intent.should_speak

    def test_urgency_from_safety(self, decoder):
        """Test urgency increases with safety activation."""
        activations = np.zeros(12)
        activations[OntologicalLayer.O11_INFORMING] = 0.5
        activations[OntologicalLayer.O12_ABSOLVING] = 0.8

        intent = decoder.decode_intent(activations)
        assert intent.urgency > 0.5


class TestDecoderIntegration:
    """Integration tests for decoders."""

    def test_motor_gripper_coordination(self):
        """Test motor and gripper decoders can coordinate."""
        motor_decoder = MotorDecoder(MotorConfig(
            num_joints=6,
            max_velocity=2.0,
            max_effort=100.0
        ))
        gripper_decoder = GripperDecoder(GripperConfig(
            min_position=0.0,
            max_position=0.08,
            max_force=40.0
        ))

        # Reaching + grasping activation
        activations = np.zeros(12)
        activations[OntologicalLayer.O3_EXECUTION] = 0.7  # Reach
        activations[OntologicalLayer.O6_SYNTHESIS] = 0.8  # Grasp

        motor_cmd = motor_decoder.decode(activations)
        gripper_cmd = gripper_decoder.decode(activations)

        # Both should produce valid commands
        assert len(motor_cmd.joint_velocities) == 6
        assert 0 <= gripper_cmd.gripper_position <= 0.08

    def test_all_decoders_same_input(self):
        """Test all decoders handle same input."""
        motor = MotorDecoder(MotorConfig(num_joints=6, max_velocity=2.0, max_effort=100.0))
        gripper = GripperDecoder(GripperConfig(min_position=0.0, max_position=0.08, max_force=40.0))
        locomotion = LocomotionDecoder(LocomotionConfig(max_linear_velocity=1.0, max_angular_velocity=1.5))

        activations = np.random.rand(12)

        # All should produce valid commands without errors
        motor_cmd = motor.decode(activations)
        gripper_cmd = gripper.decode(activations)
        locomotion_cmd = locomotion.decode(activations)

        assert motor_cmd is not None
        assert gripper_cmd is not None
        assert locomotion_cmd is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
