# Symbolu Robotics - Integration Tests
"""End-to-end integration tests for the robotics system."""

import pytest
import numpy as np
import time
from typing import Dict, Any, List

from symbolu_robotics.core.types import (
    OntologicalLayer, SafetyLevel, SensorFrame, ActuatorCommand,
    Goal, Plan, JointState, RobotPose
)
from symbolu_robotics.core.ontology_12d import LAYER_NAMES, get_layer_index
from symbolu_robotics.core.mirror_pairs_12d import MirrorPair12D, compute_mirror_balance
from symbolu_robotics.core.chitta_vritti import compute_vritti, VrittiMode
from symbolu_robotics.core.v27_state import EMAConfig, RobotStateTracker

from symbolu_robotics.encoders.fusion_encoder import FusionEncoder, FusionConfig
from symbolu_robotics.decoders.motor_decoder import MotorDecoder, MotorConfig
from symbolu_robotics.decoders.gripper_decoder import GripperDecoder, GripperConfig

from symbolu_robotics.safety.constraint_monitor import ConstraintMonitor, SafetyConfig
from symbolu_robotics.safety.human_proximity import HumanProximity, HumanProximityConfig

from symbolu_robotics.tiers.factory import create_tier, TierLevel, TierCascade

from symbolu_robotics.planning.goal_stack import GoalStack
from symbolu_robotics.planning.action_primitives import ActionLibrary, ActionType
from symbolu_robotics.planning.world_model import WorldModel
from symbolu_robotics.planning.path_planner import PathPlanner

from symbolu_robotics.state.robot_state import RobotStateEstimator
from symbolu_robotics.state.world_state import WorldState


class TestOntologyIntegration:
    """Test 12D ontology integration."""

    def test_layer_indexing_consistency(self):
        """Test layer indexing is consistent."""
        for layer in OntologicalLayer:
            assert get_layer_index(layer.name) == layer.value

    def test_mirror_pairs_complete(self):
        """Test all mirror pairs are defined."""
        pairs = list(MirrorPair12D)
        assert len(pairs) == 6

        # Each pair should reference valid layers
        for pair in pairs:
            assert pair.layer_a in OntologicalLayer
            assert pair.layer_b in OntologicalLayer

    def test_mirror_balance_computation(self):
        """Test mirror balance from 12D state."""
        state_12d = np.random.rand(12)
        balances = compute_mirror_balance(state_12d)

        assert len(balances) == 6
        for pair, balance in balances.items():
            assert -1.0 <= balance <= 1.0

    def test_vritti_classification(self):
        """Test vritti classification from 12D state."""
        state_12d = np.random.rand(12)
        vritti, confidence, action = compute_vritti(state_12d)

        assert vritti in VrittiMode
        assert 0.0 <= confidence <= 1.0
        assert action is not None


class TestEncoderDecoderPipeline:
    """Test encoder-decoder pipeline."""

    @pytest.fixture
    def encoder(self):
        return FusionEncoder(FusionConfig(
            enable_vision=True,
            enable_proprioception=True,
            enable_tactile=True
        ))

    @pytest.fixture
    def motor_decoder(self):
        return MotorDecoder(MotorConfig(
            num_joints=6,
            max_velocity=2.0,
            max_effort=100.0
        ))

    @pytest.fixture
    def gripper_decoder(self):
        return GripperDecoder(GripperConfig(
            min_position=0.0,
            max_position=0.08,
            max_force=40.0
        ))

    def test_full_pipeline(self, encoder, motor_decoder, gripper_decoder):
        """Test sensor -> 12D -> actuator pipeline."""
        # Create sensor frame
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            vision=np.random.randint(0, 256, (48, 64, 3), dtype=np.uint8),
            joint_positions=np.array([0.0, 0.5, -0.5, 0.0, 0.3, 0.0]),
            joint_velocities=np.array([0.1, 0.0, 0.1, 0.0, 0.0, 0.0]),
            joint_efforts=np.array([10.0, 20.0, 15.0, 5.0, 5.0, 2.0]),
            tactile=np.random.rand(16) * 50
        )

        # Encode to 12D
        state_12d = encoder.encode(sensor_frame)
        assert state_12d.shape == (12,)

        # Decode to motor commands
        motor_cmd = motor_decoder.decode(state_12d)
        assert len(motor_cmd.joint_velocities) == 6

        # Decode to gripper command
        gripper_cmd = gripper_decoder.decode(state_12d)
        assert 0.0 <= gripper_cmd.gripper_position <= 0.08

    def test_pipeline_preserves_safety(self, encoder, motor_decoder):
        """Test pipeline respects safety constraints."""
        # High activity sensor frame
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.ones(6) * 2.0,
            joint_velocities=np.ones(6) * 3.0,  # High velocity
            joint_efforts=np.ones(6) * 150.0,    # High effort
            tactile=np.ones(16) * 100  # High pressure
        )

        state_12d = encoder.encode(sensor_frame)
        motor_cmd = motor_decoder.decode(state_12d)

        # Decoder should respect limits
        assert np.all(np.abs(motor_cmd.joint_velocities) <= 2.0)
        assert np.all(np.abs(motor_cmd.joint_efforts) <= 100.0)


class TestSafetyIntegration:
    """Test safety system integration."""

    @pytest.fixture
    def safety_monitor(self):
        return ConstraintMonitor(SafetyConfig(
            max_joint_velocity=2.0,
            max_joint_acceleration=10.0,
            max_joint_effort=100.0
        ))

    @pytest.fixture
    def human_proximity(self):
        return HumanProximity(HumanProximityConfig(
            stop_distance=0.3,
            reduced_speed_distance=1.0,
            max_speed_near_human=0.25
        ))

    def test_safety_with_pipeline(self, safety_monitor):
        """Test safety integrates with encode/decode pipeline."""
        encoder = FusionEncoder(FusionConfig(enable_proprioception=True))
        decoder = MotorDecoder(MotorConfig(num_joints=6, max_velocity=2.0, max_effort=100.0))

        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.ones(6),
            joint_efforts=np.zeros(6)
        )

        state_12d = encoder.encode(sensor_frame)
        raw_command = decoder.decode(state_12d)
        safe_command = safety_monitor.apply_safety(raw_command)

        # Command should be within limits
        assert np.all(np.abs(safe_command.joint_velocities) <= 2.0)

    def test_human_proximity_integration(self, human_proximity, safety_monitor):
        """Test human proximity integrates with safety monitor."""
        robot_position = np.array([0.0, 0.0, 0.0])
        human_positions = [np.array([0.5, 0.0, 0.0])]  # Human nearby

        speed_limit = human_proximity.compute_speed_limit(robot_position, human_positions)

        # Create command that exceeds human-safe speed
        command = ActuatorCommand(
            timestamp=time.time(),
            joint_velocities=np.ones(6) * 1.0,
            joint_efforts=np.zeros(6)
        )

        # Apply human-aware speed limit
        if speed_limit < float('inf'):
            scale = min(1.0, speed_limit / np.max(np.abs(command.joint_velocities)))
            command.joint_velocities *= scale

        safe_command = safety_monitor.apply_safety(command)

        # Should be within human-safe limits
        assert np.max(np.abs(safe_command.joint_velocities)) <= 0.5


class TestTierIntegration:
    """Test tier system integration."""

    @pytest.fixture
    def cascade(self):
        return TierCascade(num_joints=6)

    def test_tier_cascade_flow(self, cascade):
        """Test data flows through tier cascade."""
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6),
            proximity_sensors=np.ones(8) * 0.5
        )

        command = cascade.process(sensor_frame)

        assert command is not None
        assert hasattr(command, 'joint_velocities')

    def test_tier_priority(self, cascade):
        """Test lower tiers have priority over higher tiers."""
        # Set goal in deliberative tier
        goal = Goal(
            id="reach",
            type="reach",
            target_position=np.array([1.0, 0.0, 0.5]),
            priority=1.0
        )
        cascade.deliberative.set_goal(goal)

        # Process with collision detected (should trigger reflexive)
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.ones(6),
            joint_efforts=np.zeros(6),
            proximity_sensors=np.array([0.02, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        )

        command = cascade.process(sensor_frame)
        active_tier = cascade.get_active_tier()

        # Reflexive should have taken over
        assert active_tier == TierLevel.REFLEXIVE
        assert np.all(np.abs(command.joint_velocities) < 0.5)

    def test_tier_state_sharing(self, cascade):
        """Test tiers share state correctly."""
        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )

        cascade.process(sensor_frame)

        # All tiers should have consistent state
        r1_state = cascade.reflexive.get_state_12d()
        r2_state = cascade.reactive.get_state_12d()

        # States should be similar (same input)
        assert r1_state.shape == r2_state.shape == (12,)


class TestPlanningIntegration:
    """Test planning system integration."""

    @pytest.fixture
    def goal_stack(self):
        return GoalStack(max_depth=10)

    @pytest.fixture
    def action_library(self):
        return ActionLibrary()

    @pytest.fixture
    def world_model(self):
        return WorldModel(grid_resolution=0.1)

    @pytest.fixture
    def path_planner(self):
        return PathPlanner(grid_resolution=0.1, robot_radius=0.3)

    def test_goal_to_plan(self, goal_stack, action_library, world_model):
        """Test goal decomposition to plan."""
        goal = Goal(
            id="pick_object",
            type="pick",
            target_position=np.array([0.5, 0.0, 0.1]),
            object_id="cube_1",
            priority=1.0
        )

        goal_stack.push(goal)
        assert not goal_stack.is_empty()

        # Decompose to actions
        actions = action_library.plan_for_goal(goal, world_model)
        assert len(actions) > 0

    def test_path_planning(self, path_planner, world_model):
        """Test path planning in world model."""
        start = np.array([0.0, 0.0])
        goal = np.array([2.0, 2.0])

        # Add obstacle
        world_model.add_obstacle(
            position=np.array([1.0, 1.0, 0.0]),
            size=np.array([0.5, 0.5, 1.0])
        )

        path = path_planner.plan(start, goal, world_model)

        if path is not None:
            assert len(path) > 0
            # Path should avoid obstacle
            for point in path:
                dist = np.linalg.norm(point - np.array([1.0, 1.0]))
                assert dist > 0.3  # Robot radius

    def test_planning_with_tier(self):
        """Test planning integrates with deliberative tier."""
        tier = create_tier(TierLevel.DELIBERATIVE, num_joints=6)

        goal = Goal(
            id="navigate",
            type="navigate",
            target_position=np.array([2.0, 0.0, 0.0]),
            priority=1.0
        )
        tier.set_goal(goal)

        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )

        command = tier.process(sensor_frame)

        # Should produce command toward goal
        assert command is not None


class TestStateIntegration:
    """Test state estimation integration."""

    @pytest.fixture
    def robot_state(self):
        return RobotStateEstimator(num_joints=6)

    @pytest.fixture
    def world_state(self):
        return WorldState()

    def test_state_update_cycle(self, robot_state):
        """Test state estimation update cycle."""
        for i in range(10):
            sensor_frame = SensorFrame(
                timestamp=i * 0.01,
                joint_positions=np.ones(6) * i * 0.1,
                joint_velocities=np.ones(6) * 0.1,
                joint_efforts=np.ones(6) * 10.0
            )

            robot_state.update(sensor_frame)

        state = robot_state.get_state()
        assert state is not None
        assert state.timestamp == 0.09

    def test_world_state_with_objects(self, world_state):
        """Test world state with tracked objects."""
        # Add objects
        world_state.add_object(
            id="cube_1",
            position=np.array([0.5, 0.0, 0.1]),
            size=np.array([0.05, 0.05, 0.05])
        )
        world_state.add_object(
            id="cube_2",
            position=np.array([0.3, 0.2, 0.1]),
            size=np.array([0.05, 0.05, 0.05])
        )

        objects = world_state.get_objects()
        assert len(objects) == 2
        assert "cube_1" in [o.id for o in objects]

    def test_state_with_tier(self, robot_state, world_state):
        """Test state integrates with tier system."""
        cascade = TierCascade(num_joints=6)

        sensor_frame = SensorFrame(
            timestamp=time.time(),
            joint_positions=np.zeros(6),
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6)
        )

        # Update state
        robot_state.update(sensor_frame)

        # Process through tiers
        command = cascade.process(sensor_frame)

        # Both should work together
        assert robot_state.get_state() is not None
        assert command is not None


class TestEndToEndScenarios:
    """End-to-end scenario tests."""

    def test_pick_and_place_scenario(self):
        """Test complete pick and place scenario."""
        # Initialize system
        cascade = TierCascade(num_joints=6)
        safety = ConstraintMonitor(SafetyConfig(
            max_joint_velocity=2.0,
            max_joint_acceleration=10.0,
            max_joint_effort=100.0
        ))
        world = WorldModel(grid_resolution=0.1)

        # Add target object
        world.add_object(
            id="target",
            position=np.array([0.4, 0.0, 0.1]),
            size=np.array([0.05, 0.05, 0.05])
        )

        # Set pick goal
        pick_goal = Goal(
            id="pick",
            type="pick",
            target_position=np.array([0.4, 0.0, 0.1]),
            object_id="target",
            priority=1.0
        )
        cascade.deliberative.set_goal(pick_goal)

        # Simulate control loop
        for step in range(100):
            sensor_frame = SensorFrame(
                timestamp=step * 0.01,
                joint_positions=np.zeros(6),
                joint_velocities=np.zeros(6),
                joint_efforts=np.zeros(6),
                proximity_sensors=np.ones(8) * 0.5
            )

            command = cascade.process(sensor_frame)
            safe_command = safety.apply_safety(command)

            # Verify safe operation
            assert np.all(np.abs(safe_command.joint_velocities) <= 2.0)

    def test_navigation_with_obstacle_avoidance(self):
        """Test navigation with dynamic obstacle avoidance."""
        cascade = TierCascade(num_joints=6)

        # Set navigation goal
        nav_goal = Goal(
            id="navigate",
            type="navigate",
            target_position=np.array([2.0, 0.0, 0.0]),
            priority=1.0
        )
        cascade.deliberative.set_goal(nav_goal)

        # Simulate with obstacle appearing
        for step in range(50):
            # Obstacle appears at step 25
            if step >= 25:
                proximity = np.array([0.1, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
            else:
                proximity = np.ones(8) * 0.5

            sensor_frame = SensorFrame(
                timestamp=step * 0.01,
                joint_positions=np.zeros(6),
                joint_velocities=np.zeros(6),
                joint_efforts=np.zeros(6),
                proximity_sensors=proximity
            )

            command = cascade.process(sensor_frame)

            # After obstacle appears, should slow/stop
            if step >= 25:
                assert np.max(np.abs(command.joint_velocities)) < 1.0

    def test_human_collaboration_scenario(self):
        """Test human-robot collaboration scenario."""
        cascade = TierCascade(num_joints=6)
        human_proximity = HumanProximity(HumanProximityConfig(
            stop_distance=0.3,
            reduced_speed_distance=1.0,
            max_speed_near_human=0.25
        ))

        # Set task goal
        task_goal = Goal(
            id="handover",
            type="handover",
            target_position=np.array([0.5, 0.3, 0.5]),
            priority=1.0
        )
        cascade.deliberative.set_goal(task_goal)

        # Simulate with human approaching
        robot_pos = np.array([0.0, 0.0, 0.0])

        for step in range(50):
            # Human approaches
            human_distance = 2.0 - step * 0.04  # From 2m to 0m
            human_pos = [np.array([human_distance, 0.0, 0.0])]

            speed_limit = human_proximity.compute_speed_limit(robot_pos, human_pos)

            sensor_frame = SensorFrame(
                timestamp=step * 0.01,
                joint_positions=np.zeros(6),
                joint_velocities=np.zeros(6),
                joint_efforts=np.zeros(6)
            )

            command = cascade.process(sensor_frame)

            # Apply human-aware speed limit
            if speed_limit < float('inf'):
                max_vel = np.max(np.abs(command.joint_velocities))
                if max_vel > 0:
                    scale = min(1.0, speed_limit / max_vel)
                    command.joint_velocities *= scale

            # Verify speed is appropriate for human distance
            if human_distance < 0.3:  # Stop zone
                assert np.max(np.abs(command.joint_velocities)) < 0.1


class TestPerformance:
    """Performance tests."""

    def test_full_pipeline_latency(self):
        """Test full pipeline meets timing requirements."""
        encoder = FusionEncoder(FusionConfig(enable_proprioception=True))
        cascade = TierCascade(num_joints=6)
        safety = ConstraintMonitor(SafetyConfig(
            max_joint_velocity=2.0,
            max_joint_acceleration=10.0,
            max_joint_effort=100.0
        ))

        latencies = []

        for i in range(100):
            sensor_frame = SensorFrame(
                timestamp=i * 0.001,
                joint_positions=np.random.rand(6),
                joint_velocities=np.random.rand(6),
                joint_efforts=np.random.rand(6) * 50,
                proximity_sensors=np.random.rand(8) * 0.5
            )

            start = time.perf_counter()

            # Full pipeline
            cascade.process(sensor_frame)

            latencies.append((time.perf_counter() - start) * 1000)

        avg_latency = np.mean(latencies)
        max_latency = np.max(latencies)

        # Should meet real-time requirements
        print(f"Average latency: {avg_latency:.2f}ms, Max: {max_latency:.2f}ms")
        assert avg_latency < 50.0  # 50ms average
        assert max_latency < 200.0  # 200ms worst case


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
