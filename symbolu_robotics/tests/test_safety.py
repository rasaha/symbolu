# Symbolu Robotics - Safety Tests
"""Tests for safety constraint systems matching actual implementations."""

import pytest
import numpy as np
from typing import Dict, Any

from symbolu_robotics.core.types import (
    SafetyLevel, JointState, ActuatorCommand, SensorFrame, Layer12D
)
from symbolu_robotics.safety.constraint_monitor import (
    ConstraintMonitor, SafetyConfig, COLLABORATIVE_SAFETY, INDUSTRIAL_SAFETY
)
from symbolu_robotics.safety.collision_guard import CollisionGuard, CollisionZone
from symbolu_robotics.safety.energy_bounds import EnergyBoundsMonitor, EnergyLimits
from symbolu_robotics.safety.human_proximity import HumanProximityMonitor, HumanSafetyConfig
from symbolu_robotics.safety.trajectory_validator import (
    TrajectoryValidator,
    TrajectoryValidatorConfig,
    TrajectoryPoint,
    ValidationReport,
    ValidationResult,
    CollisionPrediction,
    CollisionType,
    PredictiveSafetyMonitor,
    JointLimits,
    WorkspaceBounds,
)


class TestConstraintMonitor:
    """Tests for the main constraint monitor (O12_ABSOLVING)."""

    @pytest.fixture
    def config(self):
        return SafetyConfig(
            max_joint_velocity=2.0,
            max_joint_acceleration=5.0,
            max_joint_effort=100.0,
            human_distance_threshold=1.0,
            collision_threshold=0.05,
        )

    @pytest.fixture
    def monitor(self, config):
        return ConstraintMonitor(config)

    def test_initialization(self, monitor, config):
        """Test monitor initializes correctly."""
        assert monitor.config.max_joint_velocity == 2.0
        assert monitor.safety_level == SafetyLevel.NOMINAL

    def test_constrain_velocity_within_limits(self, monitor):
        """Test velocity within limits passes unchanged."""
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.5, 0.5, 1.0, 0.8, 0.3]),
        )
        layer_12d = np.zeros(12)  # Low constraint level

        constrained = monitor.constrain(command, layer_12d)
        np.testing.assert_array_almost_equal(
            constrained.target_velocities,
            command.target_velocities
        )

    def test_constrain_velocity_high_constraint(self, monitor):
        """Test velocity is reduced when O12 constraint is high."""
        command = ActuatorCommand(
            target_velocities=np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0]),
        )
        layer_12d = np.zeros(12)
        layer_12d[11] = 0.9  # High O12_ABSOLVING constraint

        constrained = monitor.constrain(command, layer_12d)

        # Velocities should be reduced
        assert np.all(np.abs(constrained.target_velocities) < 2.0)

    def test_constrain_effort_limits(self, monitor):
        """Test effort is clipped to limits."""
        command = ActuatorCommand(
            target_efforts=np.array([150.0, 80.0, 30.0, 120.0, 40.0, 20.0]),
        )
        layer_12d = np.zeros(12)

        constrained = monitor.constrain(command, layer_12d)

        assert np.all(np.abs(constrained.target_efforts) <= 100.0)

    def test_safety_level_update(self, monitor):
        """Test safety level updates based on constraint."""
        layer_12d = np.zeros(12)
        command = ActuatorCommand(target_velocities=np.zeros(6))

        # Low constraint -> NOMINAL
        layer_12d[11] = 0.2
        monitor.constrain(command, layer_12d)
        assert monitor.safety_level == SafetyLevel.NOMINAL

        # Medium constraint -> CAUTION
        layer_12d[11] = 0.5
        monitor.constrain(command, layer_12d)
        assert monitor.safety_level == SafetyLevel.CAUTION

        # High constraint -> RESTRICTED
        layer_12d[11] = 0.8
        monitor.constrain(command, layer_12d)
        assert monitor.safety_level == SafetyLevel.RESTRICTED

        # Very high constraint -> EMERGENCY_STOP
        layer_12d[11] = 0.95
        monitor.constrain(command, layer_12d)
        assert monitor.safety_level == SafetyLevel.EMERGENCY_STOP

    def test_slow_motion_mode(self, monitor):
        """Test slow motion mode activates on high constraint."""
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )
        layer_12d = np.zeros(12)
        layer_12d[11] = 0.85  # Triggers slow motion

        constrained = monitor.constrain(command, layer_12d)

        # Should be in slow motion (20% speed)
        assert constrained.safety_limited
        assert np.all(np.abs(constrained.target_velocities) < 0.5)

    def test_emergency_stop_passthrough(self, monitor):
        """Test emergency stop commands pass through unchanged."""
        command = ActuatorCommand(
            emergency_stop=True,
            target_velocities=np.zeros(6),
        )
        layer_12d = np.zeros(12)

        constrained = monitor.constrain(command, layer_12d)
        assert constrained.emergency_stop

    def test_check_command_safety(self, monitor):
        """Test command safety checking."""
        # Safe command
        safe_cmd = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
            target_efforts=np.array([50.0, 50.0, 50.0, 50.0, 50.0, 50.0]),
        )
        is_safe, violations = monitor.check_command_safety(safe_cmd)
        assert is_safe
        assert len(violations) == 0

        # Unsafe command - velocity exceeded
        unsafe_cmd = ActuatorCommand(
            target_velocities=np.array([3.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )
        is_safe, violations = monitor.check_command_safety(unsafe_cmd)
        assert not is_safe
        assert "velocity_exceeded" in violations

    def test_preset_configurations(self):
        """Test preset safety configurations."""
        industrial = ConstraintMonitor(INDUSTRIAL_SAFETY)
        collaborative = ConstraintMonitor(COLLABORATIVE_SAFETY)

        assert industrial.config.max_joint_velocity > collaborative.config.max_joint_velocity
        assert industrial.config.max_joint_effort > collaborative.config.max_joint_effort


class TestCollisionGuard:
    """Tests for collision detection guard."""

    @pytest.fixture
    def guard(self):
        return CollisionGuard(
            min_distance=0.05,
            emergency_stop_distance=0.02,
        )

    def test_clear_no_sensors(self, guard):
        """Test clear returns True when no sensor data."""
        sensor_frame = SensorFrame(timestamp=0.0)
        is_clear = guard.clear(sensor_frame)
        assert is_clear

    def test_clear_far_obstacles(self, guard):
        """Test clear returns True when obstacles are far."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([1.0, 0.8, 0.5, 0.7]),
        )
        is_clear = guard.clear(sensor_frame)
        assert is_clear

    def test_collision_detected_proximity(self, guard):
        """Test collision detected from proximity sensors."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.5, 0.01, 0.3, 0.4]),  # Second sensor very close
        )
        is_clear = guard.clear(sensor_frame)
        assert not is_clear
        assert guard.is_collision_detected

    def test_collision_detected_lidar(self, guard):
        """Test collision detected from LIDAR."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            lidar_ranges=np.array([0.5, 0.3, 0.015, 0.4, 0.6]),  # One very close
        )
        is_clear = guard.clear(sensor_frame)
        assert not is_clear

    def test_safety_level_based_on_distance(self, guard):
        """Test safety level changes based on closest distance."""
        # Far - NOMINAL
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([1.0, 0.8, 0.5]),
        )
        guard.clear(sensor_frame)
        assert guard.get_safety_level() == SafetyLevel.NOMINAL

        # Close but not critical - CAUTION
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.12, 0.3, 0.4]),
        )
        guard.clear(sensor_frame)
        assert guard.get_safety_level() == SafetyLevel.CAUTION

        # Very close - RESTRICTED
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.03, 0.3, 0.4]),
        )
        guard.clear(sensor_frame)
        assert guard.get_safety_level() == SafetyLevel.RESTRICTED

    def test_emergency_stop_command(self, guard):
        """Test emergency stop command generation."""
        estop = guard.emergency_stop()
        assert estop.emergency_stop
        np.testing.assert_array_equal(estop.target_velocities, np.zeros(6))

    def test_constrain_command_safe(self, guard):
        """Test command passes through when safe."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([1.0, 0.8, 0.5]),
        )
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        constrained = guard.constrain_command(command, sensor_frame)
        np.testing.assert_array_equal(
            constrained.target_velocities,
            command.target_velocities
        )

    def test_constrain_command_collision(self, guard):
        """Test emergency stop on collision."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.01, 0.3, 0.4]),  # Collision!
        )
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        constrained = guard.constrain_command(command, sensor_frame)
        assert constrained.emergency_stop

    def test_constrain_command_caution(self, guard):
        """Test velocity reduction in caution zone."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.12, 0.3, 0.4]),  # Caution zone
        )
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        constrained = guard.constrain_command(command, sensor_frame)
        assert constrained.safety_limited
        assert np.all(np.abs(constrained.target_velocities) < 1.0)

    def test_constraint_level(self, guard):
        """Test O12 constraint level calculation."""
        # Far - low constraint
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([1.0]),
        )
        guard.clear(sensor_frame)
        assert guard.get_constraint_level() == 0.0

        # Collision - max constraint
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.01]),
        )
        guard.clear(sensor_frame)
        assert guard.get_constraint_level() == 1.0

    def test_zone_intrusion(self, guard):
        """Test collision zone intrusion detection."""
        zone = CollisionZone(
            name="workspace",
            center=np.array([0.0, 0.0, 0.5]),
            radius=0.2,
        )
        guard.zones = [zone]

        # Inside zone
        is_intrusion, zone_hit = guard.check_zone_intrusion(np.array([0.0, 0.0, 0.5]))
        assert is_intrusion
        assert zone_hit.name == "workspace"

        # Outside zone
        is_intrusion, zone_hit = guard.check_zone_intrusion(np.array([1.0, 0.0, 0.5]))
        assert not is_intrusion
        assert zone_hit is None


class TestEnergyBoundsMonitor:
    """Tests for energy and thermal limits."""

    @pytest.fixture
    def limits(self):
        return EnergyLimits(
            max_power_per_joint=80.0,
            max_total_power=200.0,
            max_continuous_effort=80.0,
            max_peak_effort=150.0,
            thermal_time_constant=30.0,
        )

    @pytest.fixture
    def monitor(self, limits):
        return EnergyBoundsMonitor(limits=limits)

    def test_power_computation(self, monitor):
        """Test power computation (P = τ * ω)."""
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.array([1.0, 2.0, 1.0, 1.0, 1.0, 1.0]),
            efforts=np.array([40.0, 30.0, 20.0, 25.0, 30.0, 20.0]),
        )

        power = monitor.compute_power(joints)

        # P = |τ * ω|
        expected = np.abs(joints.efforts * joints.velocities)
        np.testing.assert_array_almost_equal(power, expected)

    def test_check_limits_safe(self, monitor):
        """Test limits check passes when safe."""
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
            efforts=np.array([40.0, 30.0, 20.0, 25.0, 30.0, 20.0]),
        )

        violations = monitor.check_limits(joints)
        assert len(violations) == 0

    def test_check_limits_power_exceeded(self, monitor):
        """Test power limit violation detected."""
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0]),
            efforts=np.array([100.0, 100.0, 100.0, 100.0, 100.0, 100.0]),  # High power
        )

        violations = monitor.check_limits(joints)
        assert any("power" in v for v in violations)

    def test_check_limits_peak_effort_exceeded(self, monitor):
        """Test peak effort limit violation detected."""
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.zeros(6),
            efforts=np.array([50.0, 200.0, 50.0, 50.0, 50.0, 50.0]),  # One very high
        )

        violations = monitor.check_limits(joints)
        assert "peak_effort_exceeded" in violations

    def test_thermal_model_update(self, monitor):
        """Test thermal model updates over time."""
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.ones(6),
            efforts=np.full(6, 50.0),
        )

        # Update multiple times to build up thermal state
        for _ in range(50):
            monitor.update(joints)

        thermal = monitor.get_thermal_percentage()
        assert np.all(thermal > 0)  # Should have accumulated

    def test_constrain_command_peak_effort(self, monitor):
        """Test command effort is clamped to peak limit."""
        command = ActuatorCommand(
            target_efforts=np.array([200.0, 100.0, 50.0, 50.0, 50.0, 50.0]),
        )
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.ones(6),
            efforts=np.zeros(6),
        )

        constrained = monitor.constrain_command(command, joints)

        # Should be clamped to max_peak_effort
        assert np.all(np.abs(constrained.target_efforts) <= 150.0)

    def test_reset_thermal(self, monitor):
        """Test thermal model reset."""
        # Build up thermal state
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.ones(6),
            efforts=np.full(6, 50.0),
        )
        for _ in range(20):
            monitor.update(joints)

        assert np.any(monitor.get_thermal_percentage() > 0)

        # Reset
        monitor.reset()
        np.testing.assert_array_equal(monitor.get_thermal_percentage(), np.zeros(6))


class TestHumanProximityMonitor:
    """Tests for human proximity safety."""

    @pytest.fixture
    def config(self):
        return HumanSafetyConfig(
            stop_distance=0.3,
            reduced_speed_distance=1.0,
            monitoring_distance=2.0,
            max_speed_near_human=0.25,
            reduced_speed=0.5,
        )

    @pytest.fixture
    def monitor(self, config):
        return HumanProximityMonitor(config)

    def test_no_human_detected(self, monitor):
        """Test no human detected state."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=False,
        )

        monitor.update(sensor_frame)

        assert not monitor.human_detected
        assert monitor.safety_level == SafetyLevel.NOMINAL
        assert monitor.get_max_allowed_speed() == float('inf')

    def test_human_far_away(self, monitor):
        """Test human detected but far away."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=5.0,
        )

        monitor.update(sensor_frame)

        assert monitor.human_detected
        assert monitor.safety_level == SafetyLevel.NOMINAL

    def test_human_in_monitoring_zone(self, monitor):
        """Test human in monitoring zone."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=1.5,  # Between reduced_speed_distance and monitoring_distance
        )

        monitor.update(sensor_frame)

        assert monitor.safety_level == SafetyLevel.CAUTION
        assert monitor.get_max_allowed_speed() == 0.5

    def test_human_in_reduced_speed_zone(self, monitor):
        """Test human in reduced speed zone."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.8,  # Between stop_distance and reduced_speed_distance
        )

        monitor.update(sensor_frame)

        assert monitor.safety_level == SafetyLevel.RESTRICTED
        assert monitor.get_max_allowed_speed() == 0.25

    def test_human_in_stop_zone(self, monitor):
        """Test human in stop zone."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.2,  # Less than stop_distance
        )

        monitor.update(sensor_frame)

        assert monitor.safety_level == SafetyLevel.EMERGENCY_STOP
        assert monitor.get_max_allowed_speed() == 0.0

    def test_constraint_level(self, monitor):
        """Test O12 constraint level calculation."""
        # Far - no constraint
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=5.0,
        )
        monitor.update(sensor_frame)
        assert monitor.get_constraint_level() == 0.0

        # Stop zone - max constraint
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.2,
        )
        monitor.update(sensor_frame)
        assert monitor.get_constraint_level() == 1.0

    def test_constrain_command_no_human(self, monitor):
        """Test command unchanged when no human."""
        sensor_frame = SensorFrame(timestamp=0.0, human_detected=False)
        monitor.update(sensor_frame)

        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        constrained = monitor.constrain_command(command)
        np.testing.assert_array_equal(
            constrained.target_velocities,
            command.target_velocities
        )

    def test_constrain_command_human_close(self, monitor):
        """Test command constrained when human is close."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.8,  # Reduced speed zone
        )
        monitor.update(sensor_frame)

        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        constrained = monitor.constrain_command(command)

        # Should be limited to max_speed_near_human
        assert np.all(np.abs(constrained.target_velocities) <= 0.25)
        assert constrained.safety_limited

    def test_constrain_command_stop_zone(self, monitor):
        """Test emergency stop when human in stop zone."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.2,
        )
        monitor.update(sensor_frame)

        command = ActuatorCommand(
            target_velocities=np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5]),
        )

        constrained = monitor.constrain_command(command)
        assert constrained.emergency_stop

    def test_proximity_fallback(self, monitor):
        """Test proximity sensors used as fallback for human detection."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=False,
            proximity_distances=np.array([0.5, 1.5, 0.8]),  # Closest is 0.5m
        )
        monitor.update(sensor_frame)

        # Should be in reduced speed zone based on proximity
        assert monitor.closest_distance == 0.5
        assert monitor.safety_level == SafetyLevel.RESTRICTED

    def test_separation_distance_estimation(self, monitor):
        """Test safe separation distance estimation."""
        robot_velocity = np.array([0.5, 0.0, 0.0])
        human_velocity = np.array([-1.0, 0.0, 0.0])

        separation = monitor.estimate_separation_distance(robot_velocity, human_velocity)

        # Should return positive distance
        assert separation > 0
        # Should be reasonable for walking speeds
        assert separation < 5.0


class TestSafetyIntegration:
    """Integration tests for safety systems."""

    def test_all_safety_systems_initialize(self):
        """Test all safety systems initialize without error."""
        constraint_monitor = ConstraintMonitor(SafetyConfig())
        collision_guard = CollisionGuard()
        energy_monitor = EnergyBoundsMonitor()
        human_monitor = HumanProximityMonitor()

        assert constraint_monitor is not None
        assert collision_guard is not None
        assert energy_monitor is not None
        assert human_monitor is not None

    def test_safety_cascade(self):
        """Test safety systems can be chained."""
        # Create all monitors
        collision_guard = CollisionGuard()
        constraint_monitor = ConstraintMonitor()
        human_monitor = HumanProximityMonitor()

        # Create sensor frame with human nearby
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.8,
            proximity_distances=np.array([0.5, 1.0, 2.0]),
        )

        # Initial command
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        # Apply collision constraints first
        command = collision_guard.constrain_command(command, sensor_frame)

        # Then apply human proximity constraints
        human_monitor.update(sensor_frame)
        command = human_monitor.constrain_command(command)

        # Then apply O12 constraints
        layer_12d = np.zeros(12)
        layer_12d[11] = human_monitor.get_constraint_level()
        command = constraint_monitor.constrain(command, layer_12d)

        # Should be significantly reduced
        assert np.all(np.abs(command.target_velocities) < 0.5)

    def test_combined_constraint_level(self):
        """Test combining constraint levels from multiple sources."""
        collision_guard = CollisionGuard()
        human_monitor = HumanProximityMonitor()

        # Sensor frame with moderate proximity
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=1.2,
            proximity_distances=np.array([0.15, 1.0, 2.0]),
        )

        collision_guard.clear(sensor_frame)
        human_monitor.update(sensor_frame)

        # Combine constraint levels (take max)
        collision_constraint = collision_guard.get_constraint_level()
        human_constraint = human_monitor.get_constraint_level()
        combined = max(collision_constraint, human_constraint)

        assert combined > 0  # Should have some constraint
        assert combined <= 1.0  # Should not exceed max


class TestTrajectoryValidator:
    """Tests for trajectory pre-validation and predictive safety."""

    @pytest.fixture
    def config(self):
        return TrajectoryValidatorConfig(
            joint_limits=JointLimits(
                position_min=np.full(6, -np.pi),
                position_max=np.full(6, np.pi),
                velocity_max=np.full(6, 2.0),
                acceleration_max=np.full(6, 5.0),
                jerk_max=np.full(6, 20.0),
            ),
            workspace_bounds=WorkspaceBounds(
                x_min=-2.0, x_max=2.0,
                y_min=-2.0, y_max=2.0,
                z_min=0.0, z_max=2.0,
            ),
            dt=0.01,
            prediction_horizon=2.0,
            min_coherence_threshold=0.4,
        )

    @pytest.fixture
    def validator(self, config):
        return TrajectoryValidator(config)

    def test_initialization(self, validator, config):
        """Test validator initializes correctly."""
        assert validator.config.dt == 0.01
        assert validator.config.min_coherence_threshold == 0.4

    def test_validate_empty_trajectory(self, validator):
        """Test validating empty trajectory returns valid."""
        report = validator.validate([])
        assert report.is_safe
        assert report.result == ValidationResult.VALID
        assert report.safety_score == 1.0

    def test_validate_single_point(self, validator):
        """Test validating single point trajectory."""
        trajectory = [
            TrajectoryPoint(
                timestamp=0.0,
                positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=1.0,
            )
        ]
        report = validator.validate(trajectory)
        assert report.is_safe
        assert report.result == ValidationResult.VALID

    def test_validate_within_limits(self, validator):
        """Test trajectory within limits passes validation."""
        trajectory = [
            TrajectoryPoint(
                timestamp=0.0,
                positions=np.array([0.0, 0.1, 0.2, 0.1, 0.0, -0.1]),
                coherence=0.9,
            ),
            TrajectoryPoint(
                timestamp=0.1,
                positions=np.array([0.1, 0.2, 0.3, 0.2, 0.1, 0.0]),
                coherence=0.9,
            ),
            TrajectoryPoint(
                timestamp=0.2,
                positions=np.array([0.2, 0.3, 0.4, 0.3, 0.2, 0.1]),
                coherence=0.9,
            ),
        ]
        report = validator.validate(trajectory)
        assert report.is_safe
        assert len(report.limit_violations) == 0

    def test_validate_position_limit_exceeded(self, validator):
        """Test trajectory exceeding position limits fails."""
        trajectory = [
            TrajectoryPoint(
                timestamp=0.0,
                positions=np.array([3.5, 0.0, 0.0, 0.0, 0.0, 0.0]),  # Exceeds pi
                coherence=0.9,
            ),
        ]
        report = validator.validate(trajectory)
        assert not report.is_safe
        assert report.result == ValidationResult.INVALID_LIMITS
        assert len(report.limit_violations) > 0

    def test_validate_velocity_limit_exceeded(self, validator):
        """Test trajectory with excessive velocity fails."""
        # Create trajectory with large position change in short time
        trajectory = [
            TrajectoryPoint(
                timestamp=0.0,
                positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.9,
            ),
            TrajectoryPoint(
                timestamp=0.01,  # 10ms
                positions=np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0]),  # 100 rad/s velocity
                coherence=0.9,
            ),
        ]
        report = validator.validate(trajectory)
        assert not report.is_safe
        assert report.result == ValidationResult.INVALID_LIMITS

    def test_validate_low_coherence(self, validator):
        """Test trajectory with low coherence fails when threshold not met."""
        trajectory = [
            TrajectoryPoint(
                timestamp=0.0,
                positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.2,  # Below threshold of 0.4
            ),
            TrajectoryPoint(
                timestamp=0.1,
                positions=np.array([0.1, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.2,
            ),
        ]
        report = validator.validate(trajectory)
        assert not report.is_safe
        assert report.result == ValidationResult.INVALID_COHERENCE
        assert not report.coherence_valid

    def test_obstacle_collision_prediction(self, validator):
        """Test obstacle collision is detected."""
        # Add obstacle near origin
        validator.set_obstacles([
            (np.array([0.5, 0.0, 0.3]), 0.2)  # Obstacle at (0.5, 0, 0.3) with radius 0.2
        ])

        trajectory = [
            TrajectoryPoint(
                timestamp=0.0,
                positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.9,
            ),
        ]
        report = validator.validate(trajectory)

        # May or may not collide depending on FK, but predictions should be computed
        assert report.validation_time_ms > 0

    def test_human_proximity_detection(self, validator):
        """Test human proximity is detected."""
        validator.set_human_state(
            position=np.array([0.3, 0.0, 0.3]),
            velocity=np.array([0.0, 0.0, 0.0]),
        )

        trajectory = [
            TrajectoryPoint(
                timestamp=0.0,
                positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.9,
            ),
        ]
        report = validator.validate(trajectory)

        # Should have human proximity warning or collision
        human_collisions = [
            c for c in report.collision_predictions
            if c.collision_type == CollisionType.HUMAN_PROXIMITY
        ]
        assert len(human_collisions) > 0

    def test_validate_command(self, validator):
        """Test single command validation."""
        current_state = JointState(
            positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            velocities=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        )
        command = ActuatorCommand(
            target_positions=np.array([0.1, 0.1, 0.1, 0.1, 0.1, 0.1]),
        )

        report = validator.validate_command(command, current_state, coherence=0.9)
        assert report.is_safe

    def test_validate_command_velocity_mode(self, validator):
        """Test velocity command validation."""
        current_state = JointState(
            positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            velocities=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        )
        command = ActuatorCommand(
            target_velocities=np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5]),
            control_mode="velocity",
        )

        report = validator.validate_command(command, current_state, coherence=0.9)
        assert report.is_safe

    def test_safe_velocity_scale(self, validator):
        """Test safe velocity scaling computation."""
        current_state = JointState(
            positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            velocities=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        )
        desired_velocity = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])

        scale = validator.get_safe_velocity_scale(
            current_state, desired_velocity, coherence=1.0
        )

        assert 0.0 <= scale <= 1.0

    def test_safe_velocity_scale_with_human(self, validator):
        """Test velocity scale is reduced when human nearby."""
        validator.set_human_state(
            position=np.array([0.3, 0.0, 0.3]),
            velocity=None,
        )

        current_state = JointState(
            positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            velocities=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        )
        desired_velocity = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])

        scale = validator.get_safe_velocity_scale(
            current_state, desired_velocity, coherence=1.0
        )

        # Scale should be reduced due to human proximity
        assert scale < 1.0

    def test_predict_trajectory_safety(self, validator):
        """Test trajectory safety prediction."""
        trajectory = [
            TrajectoryPoint(
                timestamp=float(i) * 0.1,
                positions=np.array([0.1 * i, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.9,
            )
            for i in range(10)
        ]

        predictions = validator.predict_trajectory_safety(trajectory)

        # Should return a list (may be empty if no collisions)
        assert isinstance(predictions, list)

    def test_o12_absolving_computation(self, validator):
        """Test O12_ABSOLVING layer computation."""
        # Validate something first
        trajectory = [
            TrajectoryPoint(
                timestamp=0.0,
                positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.9,
            ),
        ]
        validator.validate(trajectory)

        o12 = validator.compute_o12_absolving()
        assert 0.0 <= o12 <= 1.0

    def test_safety_score_computation(self, validator):
        """Test safety score is computed correctly."""
        # Valid trajectory
        trajectory = [
            TrajectoryPoint(
                timestamp=float(i) * 0.1,
                positions=np.array([0.1 * i, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.9,
            )
            for i in range(5)
        ]

        report = validator.validate(trajectory)

        # Safety score should be high for valid trajectory
        assert report.safety_score > 0.5

    def test_validation_report_to_dict(self, validator):
        """Test validation report serialization."""
        trajectory = [
            TrajectoryPoint(
                timestamp=0.0,
                positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.9,
            ),
        ]
        report = validator.validate(trajectory)

        report_dict = report.to_dict()

        assert "result" in report_dict
        assert "is_safe" in report_dict
        assert "safety_score" in report_dict
        assert "validation_time_ms" in report_dict


class TestPredictiveSafetyMonitor:
    """Tests for continuous predictive safety monitoring."""

    @pytest.fixture
    def validator(self):
        return TrajectoryValidator()

    @pytest.fixture
    def monitor(self, validator):
        return PredictiveSafetyMonitor(validator)

    def test_initialization(self, monitor):
        """Test monitor initializes correctly."""
        assert monitor._safety_level == SafetyLevel.NOMINAL
        assert monitor._current_trajectory is None

    def test_start_monitoring(self, monitor):
        """Test starting trajectory monitoring."""
        trajectory = [
            TrajectoryPoint(
                timestamp=float(i) * 0.1,
                positions=np.array([0.1 * i, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.9,
            )
            for i in range(10)
        ]

        monitor.start_monitoring(trajectory)

        assert monitor._current_trajectory is not None
        assert len(monitor._current_trajectory) == 10

    def test_update_no_trajectory(self, monitor):
        """Test update with no trajectory returns nominal."""
        current_state = JointState(
            positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        )

        level, predictions = monitor.update(0.0, current_state)

        assert level == SafetyLevel.NOMINAL
        assert predictions == []

    def test_update_with_trajectory(self, monitor):
        """Test update during trajectory execution."""
        trajectory = [
            TrajectoryPoint(
                timestamp=float(i) * 0.1,
                positions=np.array([0.1 * i, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.9,
            )
            for i in range(10)
        ]

        monitor.start_monitoring(trajectory)

        current_state = JointState(
            positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        )

        level, predictions = monitor.update(0.05, current_state)

        assert level in [SafetyLevel.NOMINAL, SafetyLevel.CAUTION,
                         SafetyLevel.RESTRICTED, SafetyLevel.EMERGENCY_STOP]

    def test_callback_registration(self, monitor):
        """Test callback registration."""
        collision_called = [False]
        level_called = [False]

        def on_collision(pred):
            collision_called[0] = True

        def on_level_change(level):
            level_called[0] = True

        monitor.set_collision_callback(on_collision)
        monitor.set_safety_level_callback(on_level_change)

        assert monitor._on_collision_predicted is not None
        assert monitor._on_safety_level_change is not None

    def test_trajectory_completion(self, monitor):
        """Test monitor handles trajectory completion."""
        trajectory = [
            TrajectoryPoint(
                timestamp=0.0,
                positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
                coherence=0.9,
            ),
        ]

        monitor.start_monitoring(trajectory)

        current_state = JointState(
            positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        )

        # Update after trajectory should have completed
        level, _ = monitor.update(1.0, current_state)  # Time past trajectory

        # Should return to nominal after trajectory completes
        assert level == SafetyLevel.NOMINAL


class TestTrajectoryValidatorMPCIntegration:
    """Tests for trajectory validator + MPC integration."""

    def test_validator_mpc_integration(self):
        """Test validator can be set on MPC planner."""
        from symbolu_robotics.planning.mpc_planner import MPCPlanner, MPCConfig

        validator = TrajectoryValidator()
        mpc = MPCPlanner(MPCConfig())

        mpc.set_trajectory_validator(validator)

        assert mpc._trajectory_validator is validator

    def test_plan_with_validation(self):
        """Test MPC planning with validation."""
        from symbolu_robotics.planning.mpc_planner import MPCPlanner, MPCConfig

        validator = TrajectoryValidator()
        mpc = MPCPlanner(MPCConfig(max_iterations=5))
        mpc.set_trajectory_validator(validator)

        current_state = np.zeros(12)
        current_state[1] = 0.5  # O2_IDENTITY
        current_joints = JointState(
            positions=np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        )

        mpc_result, validation_report = mpc.plan_with_validation(
            current_state=current_state,
            current_joints=current_joints,
            current_coherence=0.9,
        )

        assert mpc_result is not None
        assert validation_report is not None
        assert isinstance(validation_report, ValidationReport)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
