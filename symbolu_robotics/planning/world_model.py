"""
World Model for Robotics
=========================

O9_WITNESSES state representation.

Tracks environment state for planning and reasoning.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import time


@dataclass
class WorldObject:
    """
    Object in the world model.

    Represents detected/tracked objects.
    """
    id: str
    object_type: str = "unknown"
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    orientation: np.ndarray = field(default_factory=lambda: np.zeros(4))  # quaternion
    dimensions: np.ndarray = field(default_factory=lambda: np.ones(3) * 0.1)  # x, y, z
    confidence: float = 1.0
    last_seen: float = 0.0
    velocity: Optional[np.ndarray] = None  # If tracked
    properties: Dict = field(default_factory=dict)

    def is_stale(self, timeout: float = 5.0) -> bool:
        """Check if object hasn't been observed recently."""
        return (time.time() - self.last_seen) > timeout

    def distance_to(self, point: np.ndarray) -> float:
        """Distance from object center to point."""
        return float(np.linalg.norm(self.position - point))

    def bounding_box(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get axis-aligned bounding box (min, max)."""
        half = self.dimensions / 2
        return (self.position - half, self.position + half)


@dataclass
class Obstacle:
    """Obstacle representation."""
    position: np.ndarray
    radius: float = 0.1
    is_dynamic: bool = False
    velocity: Optional[np.ndarray] = None


class WorldModel:
    """
    World model for robotics planning.

    Maintains spatial representation of the environment.
    """

    def __init__(self, grid_resolution: float = 0.1):
        self.grid_resolution = grid_resolution
        self._objects: Dict[str, WorldObject] = {}
        self._obstacles: List[Obstacle] = []
        self._free_space: np.ndarray = None
        self._last_update = 0.0

        # Robot state in world
        self.robot_position = np.zeros(3)
        self.robot_orientation = np.array([0, 0, 0, 1])  # quaternion

    def update_from_sensors(
        self,
        depth_points: Optional[np.ndarray] = None,
        detected_objects: Optional[List[dict]] = None,
        robot_pose: Optional[Tuple] = None
    ) -> None:
        """
        Update world model from sensor data.

        Args:
            depth_points: Point cloud from depth sensor
            detected_objects: List of detected object dicts
            robot_pose: Current robot pose (x, y, z, qx, qy, qz, qw)
        """
        self._last_update = time.time()

        # Update robot pose
        if robot_pose is not None:
            self.robot_position = np.array(robot_pose[:3])
            self.robot_orientation = np.array(robot_pose[3:])

        # Update obstacles from depth
        if depth_points is not None:
            self._update_obstacles(depth_points)

        # Update tracked objects
        if detected_objects:
            for obj_dict in detected_objects:
                self._update_object(obj_dict)

        # Cleanup stale objects
        self._cleanup_stale()

    def _update_obstacles(self, points: np.ndarray) -> None:
        """Update obstacles from point cloud."""
        self._obstacles = []

        if len(points) == 0:
            return

        # Simple clustering: group nearby points
        # (In production, use proper clustering like DBSCAN)
        for point in points:
            # Transform to world frame (simplified)
            world_point = self.robot_position + point

            # Check if near existing obstacle
            merged = False
            for obs in self._obstacles:
                if np.linalg.norm(obs.position - world_point) < obs.radius * 2:
                    # Merge
                    obs.position = (obs.position + world_point) / 2
                    obs.radius = max(obs.radius, np.linalg.norm(obs.position - world_point))
                    merged = True
                    break

            if not merged and len(self._obstacles) < 100:  # Limit
                self._obstacles.append(Obstacle(
                    position=world_point,
                    radius=0.1
                ))

    def _update_object(self, obj_dict: dict) -> None:
        """Update or add tracked object."""
        obj_id = obj_dict.get("id", str(len(self._objects)))

        if obj_id in self._objects:
            obj = self._objects[obj_id]
            if "position" in obj_dict:
                obj.position = np.array(obj_dict["position"])
            if "confidence" in obj_dict:
                obj.confidence = obj_dict["confidence"]
            obj.last_seen = time.time()
        else:
            self._objects[obj_id] = WorldObject(
                id=obj_id,
                object_type=obj_dict.get("type", "unknown"),
                position=np.array(obj_dict.get("position", [0, 0, 0])),
                confidence=obj_dict.get("confidence", 1.0),
                last_seen=time.time()
            )

    def _cleanup_stale(self, timeout: float = 10.0) -> None:
        """Remove stale objects."""
        stale_ids = [
            oid for oid, obj in self._objects.items()
            if obj.is_stale(timeout)
        ]
        for oid in stale_ids:
            del self._objects[oid]

    def get_objects(self, object_type: Optional[str] = None) -> List[WorldObject]:
        """Get all objects, optionally filtered by type."""
        objs = list(self._objects.values())
        if object_type:
            objs = [o for o in objs if o.object_type == object_type]
        return objs

    def get_nearest_object(self, point: np.ndarray) -> Optional[WorldObject]:
        """Get nearest object to a point."""
        if not self._objects:
            return None

        return min(self._objects.values(), key=lambda o: o.distance_to(point))

    def get_obstacles(self) -> List[Obstacle]:
        """Get all obstacles."""
        return self._obstacles

    def is_collision_free(self, point: np.ndarray, radius: float = 0.1) -> bool:
        """Check if a point is collision-free."""
        for obs in self._obstacles:
            if np.linalg.norm(obs.position - point) < (obs.radius + radius):
                return False
        return True

    def get_clearance(self, point: np.ndarray) -> float:
        """Get minimum clearance from obstacles."""
        if not self._obstacles:
            return float('inf')

        min_dist = float('inf')
        for obs in self._obstacles:
            dist = np.linalg.norm(obs.position - point) - obs.radius
            min_dist = min(min_dist, dist)

        return max(0.0, min_dist)

    def compute_witnesses_level(self) -> float:
        """
        Compute O9_WITNESSES layer activation.

        Based on world model richness and confidence.
        """
        if not self._objects and not self._obstacles:
            return 0.1  # Minimal awareness

        # Object confidence average
        obj_confidence = 0.0
        if self._objects:
            obj_confidence = sum(o.confidence for o in self._objects.values()) / len(self._objects)

        # Obstacle awareness
        obstacle_awareness = min(1.0, len(self._obstacles) / 10.0)

        # Recency factor
        if self._last_update > 0:
            age = time.time() - self._last_update
            recency = max(0.0, 1.0 - age / 5.0)  # Decay over 5 seconds
        else:
            recency = 0.0

        return (obj_confidence * 0.4 + obstacle_awareness * 0.3 + recency * 0.3)
