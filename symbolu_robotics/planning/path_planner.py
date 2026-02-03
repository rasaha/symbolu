"""
Path Planner for Robotics
==========================

Spatial planning using O7_REASONING.

Implementation: A* algorithm using only Python stdlib (heapq)
No external path planning libraries required.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Set, Dict
import numpy as np
import heapq
import logging

logger = logging.getLogger(__name__)


@dataclass
class PathPoint:
    """Point along a path."""
    position: np.ndarray
    orientation: Optional[np.ndarray] = None
    velocity: Optional[float] = None


@dataclass
class Path:
    """Planned path."""
    points: List[PathPoint]
    length: float = 0.0
    estimated_time: float = 0.0
    is_valid: bool = True

    def is_empty(self) -> bool:
        return len(self.points) == 0


class PathPlanner:
    """
    Path planner using A* algorithm.

    Maps to O7_REASONING for spatial planning.
    """

    def __init__(
        self,
        grid_resolution: float = 0.1,
        robot_radius: float = 0.3,
        max_velocity: float = 1.0
    ):
        self.grid_resolution = grid_resolution
        self.robot_radius = robot_radius
        self.max_velocity = max_velocity

    def plan(
        self,
        start: np.ndarray,
        goal: np.ndarray,
        obstacles: List = None
    ) -> Path:
        """
        Plan path from start to goal.

        Args:
            start: Start position (x, y, z) or (x, y)
            goal: Goal position
            obstacles: List of obstacles

        Returns:
            Planned path
        """
        obstacles = obstacles or []

        # Convert to 2D for ground robot
        start_2d = start[:2] if len(start) > 2 else start
        goal_2d = goal[:2] if len(goal) > 2 else goal

        # Simple direct path check
        if self._is_path_clear(start_2d, goal_2d, obstacles):
            return self._create_direct_path(start, goal)

        # A* search
        path_points = self._astar(start_2d, goal_2d, obstacles)

        if not path_points:
            return Path(points=[], is_valid=False)

        # Convert to Path
        points = [
            PathPoint(
                position=np.array([p[0], p[1], start[2] if len(start) > 2 else 0.0])
            )
            for p in path_points
        ]

        length = sum(
            np.linalg.norm(points[i+1].position - points[i].position)
            for i in range(len(points) - 1)
        )

        return Path(
            points=points,
            length=length,
            estimated_time=length / self.max_velocity,
            is_valid=True
        )

    def _is_path_clear(
        self,
        start: np.ndarray,
        goal: np.ndarray,
        obstacles: List
    ) -> bool:
        """Check if direct path is obstacle-free."""
        direction = goal - start
        distance = np.linalg.norm(direction)

        if distance < 0.01:
            return True

        direction = direction / distance

        # Check along path
        num_checks = int(distance / self.grid_resolution) + 1
        for i in range(num_checks):
            point = start + direction * (i * self.grid_resolution)
            for obs in obstacles:
                if hasattr(obs, 'position') and hasattr(obs, 'radius'):
                    if np.linalg.norm(point - obs.position[:2]) < (obs.radius + self.robot_radius):
                        return False

        return True

    def _create_direct_path(self, start: np.ndarray, goal: np.ndarray) -> Path:
        """Create direct path when no obstacles."""
        points = [
            PathPoint(position=start.copy()),
            PathPoint(position=goal.copy())
        ]
        length = np.linalg.norm(goal - start)
        return Path(
            points=points,
            length=length,
            estimated_time=length / self.max_velocity,
            is_valid=True
        )

    def _astar(
        self,
        start: np.ndarray,
        goal: np.ndarray,
        obstacles: List
    ) -> List[Tuple[float, float]]:
        """A* path search."""
        # Grid-based A*
        def to_grid(pos):
            return (
                int(pos[0] / self.grid_resolution),
                int(pos[1] / self.grid_resolution)
            )

        def from_grid(cell):
            return np.array([
                cell[0] * self.grid_resolution,
                cell[1] * self.grid_resolution
            ])

        def heuristic(cell, goal_cell):
            return abs(cell[0] - goal_cell[0]) + abs(cell[1] - goal_cell[1])

        def is_free(cell):
            pos = from_grid(cell)
            for obs in obstacles:
                if hasattr(obs, 'position') and hasattr(obs, 'radius'):
                    if np.linalg.norm(pos - obs.position[:2]) < (obs.radius + self.robot_radius):
                        return False
            return True

        start_cell = to_grid(start)
        goal_cell = to_grid(goal)

        # Priority queue: (f_score, cell)
        open_set = [(0, start_cell)]
        came_from = {}
        g_score = {start_cell: 0}

        neighbors = [(0, 1), (1, 0), (0, -1), (-1, 0),
                     (1, 1), (1, -1), (-1, 1), (-1, -1)]

        iterations = 0
        max_iterations = 10000

        while open_set and iterations < max_iterations:
            iterations += 1
            _, current = heapq.heappop(open_set)

            if current == goal_cell:
                # Reconstruct path
                path = [from_grid(current)]
                while current in came_from:
                    current = came_from[current]
                    path.append(from_grid(current))
                path.reverse()
                return [(p[0], p[1]) for p in path]

            for dx, dy in neighbors:
                neighbor = (current[0] + dx, current[1] + dy)

                if not is_free(neighbor):
                    continue

                # Diagonal cost
                move_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
                tentative_g = g_score[current] + move_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + heuristic(neighbor, goal_cell)
                    heapq.heappush(open_set, (f_score, neighbor))

        return []  # No path found

    def smooth_path(self, path: Path, iterations: int = 3) -> Path:
        """Smooth path using simple averaging."""
        if len(path.points) < 3:
            return path

        for _ in range(iterations):
            new_points = [path.points[0]]
            for i in range(1, len(path.points) - 1):
                prev_pos = path.points[i-1].position
                curr_pos = path.points[i].position
                next_pos = path.points[i+1].position
                smoothed = (prev_pos + curr_pos + next_pos) / 3.0
                new_points.append(PathPoint(position=smoothed))
            new_points.append(path.points[-1])
            path = Path(points=new_points, is_valid=path.is_valid)

        # Recalculate length
        length = sum(
            np.linalg.norm(path.points[i+1].position - path.points[i].position)
            for i in range(len(path.points) - 1)
        )
        path.length = length
        path.estimated_time = length / self.max_velocity

        return path
