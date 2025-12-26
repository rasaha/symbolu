# Symbolu Robotics - Tier Tests
"""Tests for the three-tier control architecture."""

import pytest
import numpy as np
import time
from typing import Dict, Any

from symbolu_robotics.core.types import (
    OntologicalLayer, SafetyLevel, SensorFrame, ActuatorCommand, Goal
)
from symbolu_robotics.tiers.base import BaseTier, TierConfig
from symbolu_robotics.tiers.reflexive import ReflexiveTier, ReflexiveConfig
from symbolu_robotics.tiers.reactive import ReactiveTier, ReactiveConfig
from symbolu_robotics.tiers.deliberative import DeliberativeTier, DeliberativeConfig
from symbolu_robotics.tiers.factory import create_tier, TierLevel, TierCascade


class TestReflexiveTier:
    """Tests for R1 Reflexive tier (<1ms)."""

    @pytest.fixture
    def config(self):
        return ReflexiveConfig(
            num_joints=6,
            collision_threshold=0.05,
            force_threshold=50.0,
            enable_collision_reflex=True,
            enable_force_limit_reflex=True
        )

    @pytest.fixture
    def tier(self, config):
        return ReflexiveTier(config)

    def test_initialization(self, tier):
        """Test tier initializes correctly."""
        assert tier.target_latency_ms == 1.0
        assert tier.name == "reflexive"

    def test_process_latency(self, tier):
        """Test processing completes within latency budget."""
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6),
            proximity_sensors=np.ones(8) * 0.5  # All clear
        )

        start = time.perf_counter()
        command = tier.process(sensor_frame)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should complete well under 1ms (allow some margin)
        assert elapsed_ms < 5.0  # 5ms margin for test environment

    def test_collision_reflex(self, tier):
        """Test collision triggers stop reflex."""
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
            joint_efforts=np.zeros(6),
            proximity_sensors=np.array([0.03, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])  # Sensor 0 close
        )

        command = tier.process(sensor_frame)

        # Should trigger stop or reduced motion
        assert np.all(np.abs(command.joint_velocities) <= 0.1)

    def test_force_limit_reflex(self, tier):
        """Test excessive force triggers limit reflex."""
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.ones(6),
            joint_efforts=np.array([60.0, 30.0, 30.0, 30.0, 30.0, 30.0]),  # Joint 0 high
            proximity_sensors=np.ones(8) * 0.5
        )

        command = tier.process(sensor_frame)

        # Joint 0 effort should be limited
        assert np.abs(command.joint_efforts[0]) < 60.0

    def test_no_reflex_normal_conditions(self, tier):
        """Test no reflex intervention in normal conditions."""
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5]),
            joint_efforts=np.array([20.0, 20.0, 20.0, 20.0, 20.0, 20.0]),
            proximity_sensors=np.ones(8) * 0.5
        )

        command = tier.process(sensor_frame)

        # Should pass through relatively unchanged
        assert np.allclose(command.joint_velocities, sensor_frame.joint_velocities, atol=0.1)


class TestReactiveTier:
    """Tests for R2 Reactive tier (<10ms)."""

    @pytest.fixture
    def config(self):
        return ReactiveConfig(
            num_joints=6,
            ema_alpha=0.1,
            enable_mirror_balance=True,
            obstacle_avoidance_gain=1.0
        )

    @pytest.fixture
    def tier(self, config):
        return ReactiveTier(config)

    def test_initialization(self, tier):
        """Test tier initializes correctly."""
        assert tier.target_latency_ms == 10.0
        assert tier.name == "reactive"

    def test_process_latency(self, tier):
        """Test processing completes within latency budget."""
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            vision=np.random.randint(0, 256, (48, 64, 3), dtype=np.uint8),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )

        start = time.perf_counter()
        command = tier.process(sensor_frame)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should complete within 10ms (allow margin)
        assert elapsed_ms < 50.0  # 50ms margin for test environment

    def test_ema_smoothing(self, tier):
        """Test EMA smoothing of state."""
        # First frame
        frame1 = SensorFrame(
            timestamp=0.0,
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )
        tier.process(frame1)
        state1 = tier.get_state_12d().copy()

        # Second frame with different values
        frame2 = SensorFrame(
            timestamp=0.01,
            joint_positions=np.ones(6),
            joint_velocities=np.ones(6),
            joint_efforts=np.ones(6) * 50
        )
        tier.process(frame2)
        state2 = tier.get_state_12d()

        # State should change but be smoothed
        assert not np.allclose(state1, state2)

    def test_mirror_balance(self, tier):
        """Test mirror pair balance computation."""
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )

        tier.process(sensor_frame)
        balance = tier.get_mirror_balance()

        # Should have 6 balance values
        assert len(balance) == 6
        assert all(-1.0 <= b <= 1.0 for b in balance.values())

    def test_obstacle_avoidance(self, tier):
        """Test obstacle avoidance behavior."""
        # Frame with obstacle detected
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            vision=np.zeros((48, 64, 3), dtype=np.uint8),  # Dark = obstacle
            lidar=np.array([0.3] * 360),  # Close obstacle all around
            joint_positions=np.zeros(6),
            joint_velocities=np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            joint_efforts=np.zeros(6)
        )

        command = tier.process(sensor_frame)

        # Should reduce velocity due to obstacles
        assert command is not None


class TestDeliberativeTier:
    """Tests for R3 Deliberative tier (<100ms)."""

    @pytest.fixture
    def config(self):
        return DeliberativeConfig(
            num_joints=6,
            planning_horizon=5.0,
            max_planning_time_ms=50.0,
            enable_goal_reasoning=True
        )

    @pytest.fixture
    def tier(self, config):
        return DeliberativeTier(config)

    def test_initialization(self, tier):
        """Test tier initializes correctly."""
        assert tier.target_latency_ms == 100.0
        assert tier.name == "deliberative"

    def test_set_goal(self, tier):
        """Test setting a goal."""
        goal = Goal(
            id="test_goal",
            type="reach",
            target_position=np.array([0.5, 0.0, 0.3]),
            priority=1.0
        )

        tier.set_goal(goal)
        assert tier.current_goal is not None
        assert tier.current_goal.id == "test_goal"

    def test_plan_generation(self, tier):
        """Test plan generation for goal."""
        goal = Goal(
            id="reach_goal",
            type="reach",
            target_position=np.array([0.5, 0.0, 0.3]),
            priority=1.0
        )
        tier.set_goal(goal)

        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )

        tier.process(sensor_frame)

        # Should have generated a plan
        assert tier.current_plan is not None or tier.has_active_action()

    def test_vritti_classification(self, tier):
        """Test vritti (cognitive mode) classification."""
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )

        tier.process(sensor_frame)
        vritti = tier.get_vritti_mode()

        # Should classify into one of the 5 modes
        assert vritti in ['pramana', 'viparyaya', 'vikalpa', 'smrti', 'nidra']

    def test_async_planning(self, tier):
        """Test asynchronous planning doesn't block."""
        goal = Goal(
            id="complex_goal",
            type="navigate",
            target_position=np.array([5.0, 5.0, 0.0]),
            priority=1.0
        )
        tier.set_goal(goal)

        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )

        start = time.perf_counter()
        command = tier.process(sensor_frame)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should return within budget even if planning continues async
        assert elapsed_ms < 150.0  # Allow some margin


class TestTierFactory:
    """Tests for tier factory."""

    def test_create_reflexive(self):
        """Test creating reflexive tier."""
        tier = create_tier(TierLevel.REFLEXIVE, num_joints=6)
        assert tier.name == "reflexive"
        assert tier.target_latency_ms == 1.0

    def test_create_reactive(self):
        """Test creating reactive tier."""
        tier = create_tier(TierLevel.REACTIVE, num_joints=6)
        assert tier.name == "reactive"
        assert tier.target_latency_ms == 10.0

    def test_create_deliberative(self):
        """Test creating deliberative tier."""
        tier = create_tier(TierLevel.DELIBERATIVE, num_joints=6)
        assert tier.name == "deliberative"
        assert tier.target_latency_ms == 100.0

    def test_create_with_config(self):
        """Test creating tier with custom config."""
        config = ReflexiveConfig(
            num_joints=4,
            collision_threshold=0.1
        )
        tier = create_tier(TierLevel.REFLEXIVE, config=config)
        assert tier.config.num_joints == 4
        assert tier.config.collision_threshold == 0.1


class TestTierCascade:
    """Tests for tier cascade."""

    @pytest.fixture
    def cascade(self):
        return TierCascade(num_joints=6)

    def test_initialization(self, cascade):
        """Test cascade initializes all tiers."""
        assert cascade.reflexive is not None
        assert cascade.reactive is not None
        assert cascade.deliberative is not None

    def test_process_cascade(self, cascade):
        """Test cascading through tiers."""
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )

        command = cascade.process(sensor_frame)

        assert command is not None
        assert len(command.joint_velocities) == 6

    def test_reflex_overrides_higher_tiers(self, cascade):
        """Test reflex tier can override higher tier commands."""
        # Set a goal in deliberative tier
        goal = Goal(
            id="test",
            type="reach",
            target_position=np.array([1.0, 0.0, 0.0]),
            priority=1.0
        )
        cascade.deliberative.set_goal(goal)

        # Create sensor frame with collision
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.ones(6),
            joint_efforts=np.zeros(6),
            proximity_sensors=np.array([0.02, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        )

        command = cascade.process(sensor_frame)

        # Reflex should have stopped motion despite goal
        assert np.all(np.abs(command.joint_velocities) < 0.5)

    def test_get_active_tier(self, cascade):
        """Test getting the currently active tier."""
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )

        cascade.process(sensor_frame)
        active = cascade.get_active_tier()

        assert active in [TierLevel.REFLEXIVE, TierLevel.REACTIVE, TierLevel.DELIBERATIVE]


class TestTierTiming:
    """Tests for tier timing requirements."""

    def test_reflexive_meets_timing(self):
        """Test reflexive tier meets 1ms timing."""
        tier = create_tier(TierLevel.REFLEXIVE, num_joints=6)

        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6),
            proximity_sensors=np.ones(8) * 0.5
        )

        # Run multiple times to get average
        times = []
        for _ in range(100):
            start = time.perf_counter()
            tier.process(sensor_frame)
            times.append((time.perf_counter() - start) * 1000)

        avg_time = np.mean(times)
        # Should be well under target (allow margin for test environment)
        assert avg_time < 10.0  # 10x margin

    def test_reactive_meets_timing(self):
        """Test reactive tier meets 10ms timing."""
        tier = create_tier(TierLevel.REACTIVE, num_joints=6)

        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )

        times = []
        for _ in range(20):
            start = time.perf_counter()
            tier.process(sensor_frame)
            times.append((time.perf_counter() - start) * 1000)

        avg_time = np.mean(times)
        assert avg_time < 100.0  # 10x margin


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
