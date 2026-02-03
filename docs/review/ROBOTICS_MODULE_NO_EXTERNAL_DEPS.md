# Robotics Module - No External Dependencies Analysis

**Date:** 2026-02-03
**Purpose:** Evaluate which upgrades can be implemented using only Python stdlib + numpy

---

## Current Dependency Baseline

The robotics module currently uses:

**Python Standard Library:**
- `abc`, `dataclasses`, `typing`, `enum` (type system)
- `copy`, `heapq`, `json`, `math`, `re`, `struct` (utilities)
- `threading`, `time` (concurrency)
- `logging`, `pickle` (available but not used)

**External:**
- `numpy` - Used throughout (mandatory)
- `torch` - Only in `vision/su_vit.py` (optional)
- `pytest` - Only for tests

---

## Executive Summary

| Area | Implementable w/o Deps? | Effort | Quality vs External |
|------|------------------------|--------|---------------------|
| **NN Training** | PARTIAL | 10 days | 60% (no GPU, limited algorithms) |
| **LLM Provider** | YES | 3 days | 40% (HTTP only, no streaming) |
| **MPC Planning** | YES | 6 days | 70% (scipy-style optimization) |
| **HTN Planning** | YES | 4 days | 90% (pyhop is pure Python anyway) |
| **Path Planning** | YES | 2 days | 95% (A* is straightforward) |
| **FK/Kinematics** | YES | 5 days | 80% (DH parameters, no IK solver) |
| **URDF Parsing** | YES | 3 days | 85% (XML parsing is stdlib) |
| **Serial Comm** | NO | - | Requires `pyserial` |
| **Persistence** | YES | 1 day | 95% (pickle is stdlib) |
| **Error Handling** | YES | 1 day | 100% (logging is stdlib) |

**Bottom Line:** 8 of 10 areas can be implemented without external dependencies, but with reduced functionality and increased effort.

---

## 1. Neural Network Training (PARTIAL - With Limitations)

### What's Possible with numpy

```python
# Pure numpy neural network for skill learning
import numpy as np

class NumpyMLP:
    """Simple MLP using only numpy."""

    def __init__(self, layer_sizes: list):
        self.weights = []
        self.biases = []
        for i in range(len(layer_sizes) - 1):
            # Xavier initialization
            w = np.random.randn(layer_sizes[i], layer_sizes[i+1]) * np.sqrt(2.0 / layer_sizes[i])
            b = np.zeros(layer_sizes[i+1])
            self.weights.append(w)
            self.biases.append(b)

    def forward(self, x: np.ndarray) -> np.ndarray:
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            x = x @ w + b
            if i < len(self.weights) - 1:
                x = np.maximum(0, x)  # ReLU
        return x

    def backward(self, x, y, lr=0.001):
        # Manual backprop implementation
        # ... (50-100 lines of gradient computation)
        pass
```

### What's NOT Possible

| Feature | Why Not Possible |
|---------|------------------|
| GPU acceleration | Requires CUDA bindings |
| Automatic differentiation | Would need to implement from scratch |
| Advanced optimizers (Adam) | Can implement, but 100+ lines each |
| Batch normalization | Can implement, but tricky to get right |
| Convolutional layers | Can implement, but very slow |

### Implementable RL Algorithms (numpy-only)

| Algorithm | Feasible | Notes |
|-----------|----------|-------|
| **Q-Learning (tabular)** | YES | Simple, works for discrete states |
| **DQN** | PARTIAL | No GPU, slow training |
| **REINFORCE** | YES | Policy gradient, simple |
| **PPO** | HARD | Complex, many hyperparameters |
| **SAC** | HARD | Requires auto-diff for entropy |

### Recommended numpy-only Approach

```python
# skill_learning.py - numpy-only implementation

class SkillLearner:
    def __init__(self, config):
        self._config = config
        # Simple policy network
        state_dim = 12  # 12D ontology
        action_dim = 7  # 7 DOF
        self._policy = NumpyMLP([state_dim, 256, 256, action_dim])
        self._value = NumpyMLP([state_dim, 256, 256, 1])

    def train_step(self) -> Dict[str, float]:
        batch = self._buffer.sample(self._config.batch_size)

        # REINFORCE with baseline
        states = np.array([e.state for e in batch])
        actions = np.array([e.action for e in batch])
        returns = self._compute_returns(batch)

        # Manual gradient computation
        values = self._value.forward(states)
        advantages = returns - values.flatten()

        # Policy gradient
        log_probs = self._compute_log_probs(states, actions)
        policy_loss = -np.mean(log_probs * advantages)

        # Update (manual SGD)
        self._update_policy(states, actions, advantages)
        self._update_value(states, returns)

        return {"policy_loss": policy_loss, "value_loss": np.mean((values - returns)**2)}
```

### Effort & Quality

| Aspect | With numpy | With PyTorch+SB3 |
|--------|------------|------------------|
| Implementation | 10 days | 2.5 days |
| Training speed | 10-100x slower | Baseline |
| GPU support | NO | YES |
| Algorithm variety | 2-3 basic | 10+ advanced |
| Stability | Manual tuning | Well-tested |

---

## 2. LLM Provider (YES - HTTP-based)

### What's Possible with urllib

```python
# human_interface.py - stdlib HTTP implementation
import urllib.request
import urllib.error
import json
import ssl

class StdlibLLMProvider(LLMProvider):
    """LLM provider using only Python stdlib."""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self._api_key = api_key
        self._base_url = base_url
        # SSL context for HTTPS
        self._ssl_context = ssl.create_default_context()

    def parse_command(self, text: str, context: Dict) -> Dict:
        url = f"{self._base_url}/chat/completions"

        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": f"Context: {json.dumps(context)}\nCommand: {text}"}
            ],
            "temperature": 0.3,
            "max_tokens": 256,
            "response_format": {"type": "json_object"}
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, context=self._ssl_context, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return json.loads(result['choices'][0]['message']['content'])
        except urllib.error.HTTPError as e:
            return {"error": str(e), "intent": "unknown", "confidence": 0.0}
        except urllib.error.URLError as e:
            return {"error": str(e), "intent": "unknown", "confidence": 0.0}
```

### What's NOT Possible

| Feature | Why Not Possible |
|---------|------------------|
| Streaming responses | urllib doesn't support SSE well |
| Async requests | Requires `asyncio` + `aiohttp` |
| Connection pooling | urllib creates new connection each time |
| Retry with backoff | Must implement manually |
| Multiple providers | Must implement each API manually |

### Effort & Quality

| Aspect | With urllib | With litellm |
|--------|-------------|--------------|
| Implementation | 3 days | 1.5 days |
| OpenAI support | YES | YES |
| Anthropic support | +1 day each | YES |
| Ollama support | +2 days | YES |
| Streaming | NO | YES |
| Error handling | Basic | Comprehensive |

---

## 3. MPC Planning (YES - Custom Optimization)

### What's Possible with numpy

```python
# mpc_planner.py - numpy-only optimization
import numpy as np

class NumpyMPCPlanner:
    """MPC with numpy-based optimization."""

    def __init__(self, config):
        self._config = config

    def plan(self, current_state, goal_state):
        """Gradient descent optimization."""

        # Initialize action sequence
        actions = np.zeros((self._config.horizon, 7))

        for iteration in range(self._config.max_iterations):
            # Compute cost and gradient numerically
            cost, gradient = self._compute_cost_and_gradient(
                current_state, actions, goal_state
            )

            # Gradient descent step
            actions -= self._config.learning_rate * gradient

            # Project to constraints
            actions = np.clip(actions, self._config.action_min, self._config.action_max)

            if cost < self._config.tolerance:
                break

        return actions[0]  # Receding horizon

    def _compute_cost_and_gradient(self, state, actions, goal):
        """Numerical gradient via finite differences."""
        eps = 1e-5
        cost = self._compute_cost(state, actions, goal)

        gradient = np.zeros_like(actions)
        for i in range(actions.shape[0]):
            for j in range(actions.shape[1]):
                actions[i, j] += eps
                cost_plus = self._compute_cost(state, actions, goal)
                actions[i, j] -= 2 * eps
                cost_minus = self._compute_cost(state, actions, goal)
                actions[i, j] += eps  # restore
                gradient[i, j] = (cost_plus - cost_minus) / (2 * eps)

        return cost, gradient

    def _compute_cost(self, state, actions, goal):
        """Quadratic cost with dynamics simulation."""
        total_cost = 0.0
        current = state.copy()

        for action in actions:
            # Simulate dynamics (simple Euler integration)
            current = self._dynamics(current, action)

            # State cost (distance to goal)
            total_cost += np.sum((current - goal) ** 2 * self._config.state_weights)

            # Control cost
            total_cost += np.sum(action ** 2 * self._config.control_weights)

        return total_cost
```

### Alternative: Implement scipy.optimize.minimize clone

```python
# Simplified BFGS implementation
class BFGSOptimizer:
    """Quasi-Newton optimization using BFGS."""

    def minimize(self, fun, x0, maxiter=100, tol=1e-6):
        x = x0.copy()
        n = len(x)
        H = np.eye(n)  # Approximate inverse Hessian

        for _ in range(maxiter):
            grad = self._numerical_gradient(fun, x)

            if np.linalg.norm(grad) < tol:
                break

            # Search direction
            p = -H @ grad

            # Line search (Armijo)
            alpha = self._line_search(fun, x, p, grad)

            # Update
            s = alpha * p
            x_new = x + s
            grad_new = self._numerical_gradient(fun, x_new)
            y = grad_new - grad

            # BFGS update
            if np.dot(y, s) > 1e-10:
                rho = 1.0 / np.dot(y, s)
                I = np.eye(n)
                H = (I - rho * np.outer(s, y)) @ H @ (I - rho * np.outer(y, s)) + rho * np.outer(s, s)

            x = x_new

        return x
```

### Effort & Quality

| Aspect | With numpy | With CasADi |
|--------|------------|-------------|
| Implementation | 6 days | 2 days |
| Optimization quality | Good (BFGS) | Excellent (IPOPT) |
| Speed | Slower (numerical grad) | Fast (auto-diff) |
| Constraint handling | Basic (projection) | Advanced (SQP) |

---

## 4. HTN Planning (YES - Pure Python)

### What's Possible

pyhop is already pure Python, so we can implement equivalent functionality:

```python
# htn_planner.py - pure Python HTN
from typing import Dict, List, Callable, Optional, Any

class PureHTNPlanner:
    """HTN planner without external dependencies."""

    def __init__(self):
        self._operators: Dict[str, Callable] = {}
        self._methods: Dict[str, List[Callable]] = {}

    def declare_operator(self, name: str, func: Callable):
        """Register primitive operator."""
        self._operators[name] = func

    def declare_method(self, task_name: str, method: Callable):
        """Register decomposition method."""
        if task_name not in self._methods:
            self._methods[task_name] = []
        self._methods[task_name].append(method)

    def plan(self, state: Dict, tasks: List[tuple], depth: int = 0) -> Optional[List]:
        """
        Plan using depth-first search through task decompositions.

        Returns list of (operator_name, args) tuples, or None if no plan found.
        """
        if not tasks:
            return []  # Success - all tasks done

        if depth > 100:
            return None  # Depth limit

        task = tasks[0]
        task_name = task[0]
        task_args = task[1:] if len(task) > 1 else ()

        # Try as primitive operator
        if task_name in self._operators:
            operator = self._operators[task_name]
            new_state = operator(state.copy(), *task_args)

            if new_state is not None:  # Operator succeeded
                rest_plan = self.plan(new_state, tasks[1:], depth + 1)
                if rest_plan is not None:
                    return [(task_name, task_args)] + rest_plan

        # Try as compound task (decompose with methods)
        if task_name in self._methods:
            for method in self._methods[task_name]:
                subtasks = method(state, *task_args)

                if subtasks is not None:  # Method applicable
                    plan = self.plan(state, subtasks + tasks[1:], depth + 1)
                    if plan is not None:
                        return plan

        return None  # No plan found

# Example operators and methods
def op_move_to(state, robot, location):
    """Primitive: move robot to location."""
    if state.get(f'{robot}_at') is not None:
        state[f'{robot}_at'] = location
        return state
    return None

def op_pick_up(state, robot, obj):
    """Primitive: pick up object."""
    robot_loc = state.get(f'{robot}_at')
    obj_loc = state.get(f'{obj}_at')
    if robot_loc == obj_loc and state.get(f'{robot}_holding') is None:
        state[f'{robot}_holding'] = obj
        state[f'{obj}_at'] = None
        return state
    return None

def method_transport(state, robot, obj, dest):
    """Method: decompose transport into subtasks."""
    obj_loc = state.get(f'{obj}_at')
    if obj_loc is not None:
        return [
            ('move_to', robot, obj_loc),
            ('pick_up', robot, obj),
            ('move_to', robot, dest),
            ('put_down', robot, obj),
        ]
    return None
```

### Effort & Quality

| Aspect | Pure Python | With pyhop3 |
|--------|-------------|-------------|
| Implementation | 4 days | 3 days |
| Functionality | Equivalent | Same |
| Testing | Must write | Already tested |
| Extensions | Manual | Community |

---

## 5. Path Planning (YES - A* from scratch)

### What's Possible

```python
# path_planner.py - pure Python A*
import heapq
from typing import List, Tuple, Set, Dict, Optional

class PurePathPlanner:
    """A* path planner without external dependencies."""

    def __init__(self, grid_size: int = 100):
        self._grid_size = grid_size

    def plan(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        obstacles: Set[Tuple[int, int]],
    ) -> Optional[List[Tuple[int, int]]]:
        """
        A* search on 2D grid.

        Returns path as list of (x, y) tuples, or None if no path.
        """
        if start == goal:
            return [start]

        if start in obstacles or goal in obstacles:
            return None

        # Priority queue: (f_score, counter, node)
        counter = 0
        open_set = [(self._heuristic(start, goal), counter, start)]

        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], float] = {start: 0}

        while open_set:
            _, _, current = heapq.heappop(open_set)

            if current == goal:
                return self._reconstruct_path(came_from, current)

            for neighbor in self._get_neighbors(current, obstacles):
                tentative_g = g_score[current] + self._distance(current, neighbor)

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + self._heuristic(neighbor, goal)
                    counter += 1
                    heapq.heappush(open_set, (f_score, counter, neighbor))

        return None  # No path found

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Euclidean distance heuristic."""
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    def _distance(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Actual distance (1 for cardinal, sqrt(2) for diagonal)."""
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        return 1.414 if dx + dy == 2 else 1.0

    def _get_neighbors(
        self,
        node: Tuple[int, int],
        obstacles: Set[Tuple[int, int]],
    ) -> List[Tuple[int, int]]:
        """Get valid 8-connected neighbors."""
        x, y = node
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self._grid_size and 0 <= ny < self._grid_size:
                    if (nx, ny) not in obstacles:
                        neighbors.append((nx, ny))
        return neighbors

    def _reconstruct_path(
        self,
        came_from: Dict,
        current: Tuple[int, int],
    ) -> List[Tuple[int, int]]:
        """Reconstruct path from came_from dict."""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        return list(reversed(path))
```

### Effort & Quality

| Aspect | Pure Python | With networkx |
|--------|-------------|---------------|
| Implementation | 2 days | 1 day |
| A* quality | Equivalent | Same |
| Other algorithms | +1 day each | Built-in |
| Graph operations | Manual | Rich API |

---

## 6. Forward Kinematics (YES - DH Parameters)

### What's Possible

```python
# kinematics.py - pure numpy FK
import numpy as np
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class DHParams:
    """Denavit-Hartenberg parameters for one joint."""
    a: float      # Link length
    alpha: float  # Link twist
    d: float      # Link offset
    theta: float  # Joint angle (variable for revolute)
    joint_type: str = 'revolute'  # 'revolute' or 'prismatic'

class PureKinematics:
    """Forward kinematics using DH convention."""

    def __init__(self, dh_params: List[DHParams]):
        self._dh_params = dh_params
        self._n_joints = len(dh_params)

    def forward_kinematics(self, joint_values: np.ndarray) -> np.ndarray:
        """
        Compute end-effector pose from joint values.

        Args:
            joint_values: Array of joint values (angles for revolute, offsets for prismatic)

        Returns:
            4x4 homogeneous transformation matrix
        """
        T = np.eye(4)

        for i, (dh, q) in enumerate(zip(self._dh_params, joint_values)):
            # Apply joint value
            if dh.joint_type == 'revolute':
                theta = dh.theta + q
                d = dh.d
            else:  # prismatic
                theta = dh.theta
                d = dh.d + q

            # DH transformation matrix
            T_i = self._dh_matrix(dh.a, dh.alpha, d, theta)
            T = T @ T_i

        return T

    def _dh_matrix(self, a: float, alpha: float, d: float, theta: float) -> np.ndarray:
        """Compute DH transformation matrix."""
        ct = np.cos(theta)
        st = np.sin(theta)
        ca = np.cos(alpha)
        sa = np.sin(alpha)

        return np.array([
            [ct, -st * ca,  st * sa, a * ct],
            [st,  ct * ca, -ct * sa, a * st],
            [0,   sa,       ca,      d     ],
            [0,   0,        0,       1     ],
        ])

    def jacobian(self, joint_values: np.ndarray) -> np.ndarray:
        """
        Compute geometric Jacobian.

        Returns:
            6 x n_joints Jacobian matrix [linear; angular]
        """
        J = np.zeros((6, self._n_joints))

        # Compute all transforms
        T = [np.eye(4)]
        for i, (dh, q) in enumerate(zip(self._dh_params, joint_values)):
            if dh.joint_type == 'revolute':
                T_i = self._dh_matrix(dh.a, dh.alpha, dh.d, dh.theta + q)
            else:
                T_i = self._dh_matrix(dh.a, dh.alpha, dh.d + q, dh.theta)
            T.append(T[i] @ T_i)

        # End-effector position
        p_e = T[-1][:3, 3]

        for i in range(self._n_joints):
            # z-axis of frame i
            z_i = T[i][:3, 2]
            # Origin of frame i
            p_i = T[i][:3, 3]

            if self._dh_params[i].joint_type == 'revolute':
                # Linear velocity: z_i x (p_e - p_i)
                J[:3, i] = np.cross(z_i, p_e - p_i)
                # Angular velocity: z_i
                J[3:, i] = z_i
            else:  # prismatic
                # Linear velocity: z_i
                J[:3, i] = z_i
                # Angular velocity: 0
                J[3:, i] = 0

        return J

# Example: 6-DOF robot (UR5-like)
UR5_DH = [
    DHParams(a=0,      alpha=np.pi/2,  d=0.089159, theta=0),
    DHParams(a=-0.425, alpha=0,        d=0,        theta=0),
    DHParams(a=-0.392, alpha=0,        d=0,        theta=0),
    DHParams(a=0,      alpha=np.pi/2,  d=0.10915,  theta=0),
    DHParams(a=0,      alpha=-np.pi/2, d=0.09465,  theta=0),
    DHParams(a=0,      alpha=0,        d=0.0823,   theta=0),
]
```

### Effort & Quality

| Aspect | Pure numpy | With roboticstoolbox |
|--------|------------|----------------------|
| Implementation | 5 days | 1 day |
| FK accuracy | Equivalent | Same |
| IK solver | +5 days (iterative) | Built-in |
| Dynamics | +10 days | Built-in |
| Visualization | NO | YES |

---

## 7. URDF Parsing (YES - XML is stdlib)

### What's Possible

```python
# urdf_parser.py - pure Python URDF parsing
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Dict, Optional
import numpy as np

@dataclass
class URDFJoint:
    name: str
    joint_type: str  # 'revolute', 'prismatic', 'fixed'
    parent: str
    child: str
    origin_xyz: np.ndarray
    origin_rpy: np.ndarray
    axis: np.ndarray
    limit_lower: Optional[float] = None
    limit_upper: Optional[float] = None

@dataclass
class URDFLink:
    name: str
    mass: float = 0.0
    inertia: Optional[np.ndarray] = None

class PureURDFParser:
    """URDF parser using only Python stdlib."""

    def __init__(self):
        self.links: Dict[str, URDFLink] = {}
        self.joints: Dict[str, URDFJoint] = {}
        self.root_link: Optional[str] = None

    def parse(self, urdf_path: str):
        """Parse URDF file."""
        tree = ET.parse(urdf_path)
        root = tree.getroot()

        # Parse links
        for link_elem in root.findall('link'):
            link = self._parse_link(link_elem)
            self.links[link.name] = link

        # Parse joints
        parent_links = set()
        child_links = set()
        for joint_elem in root.findall('joint'):
            joint = self._parse_joint(joint_elem)
            self.joints[joint.name] = joint
            parent_links.add(joint.parent)
            child_links.add(joint.child)

        # Find root link (parent but never child)
        roots = parent_links - child_links
        if roots:
            self.root_link = list(roots)[0]

    def _parse_link(self, elem) -> URDFLink:
        name = elem.get('name')
        mass = 0.0
        inertia = None

        inertial = elem.find('inertial')
        if inertial is not None:
            mass_elem = inertial.find('mass')
            if mass_elem is not None:
                mass = float(mass_elem.get('value', 0))

        return URDFLink(name=name, mass=mass, inertia=inertia)

    def _parse_joint(self, elem) -> URDFJoint:
        name = elem.get('name')
        joint_type = elem.get('type')

        parent = elem.find('parent').get('link')
        child = elem.find('child').get('link')

        # Origin
        origin = elem.find('origin')
        if origin is not None:
            xyz = np.array([float(x) for x in origin.get('xyz', '0 0 0').split()])
            rpy = np.array([float(x) for x in origin.get('rpy', '0 0 0').split()])
        else:
            xyz = np.zeros(3)
            rpy = np.zeros(3)

        # Axis
        axis_elem = elem.find('axis')
        if axis_elem is not None:
            axis = np.array([float(x) for x in axis_elem.get('xyz', '0 0 1').split()])
        else:
            axis = np.array([0, 0, 1])

        # Limits
        limit = elem.find('limit')
        lower, upper = None, None
        if limit is not None:
            lower = float(limit.get('lower', 0))
            upper = float(limit.get('upper', 0))

        return URDFJoint(
            name=name,
            joint_type=joint_type,
            parent=parent,
            child=child,
            origin_xyz=xyz,
            origin_rpy=rpy,
            axis=axis,
            limit_lower=lower,
            limit_upper=upper,
        )

    def to_dh_params(self) -> List[DHParams]:
        """Convert URDF to DH parameters (approximate)."""
        # This is non-trivial - URDF uses different convention
        # Would need geometric analysis
        pass
```

### Effort & Quality

| Aspect | Pure Python | With yourdfpy |
|--------|-------------|---------------|
| Implementation | 3 days | 0.5 days |
| Basic parsing | YES | YES |
| DH conversion | +2 days | Built-in |
| Mesh loading | NO | YES |
| Validation | Manual | Built-in |

---

## 8. Serial Communication (NO - Requires pyserial)

### Why Not Possible

Python's standard library does not include serial port access. The alternatives:

| Approach | Problem |
|----------|---------|
| `os.open('/dev/ttyUSB0')` | Works on Linux only, no baud rate control |
| `ctypes` + system calls | OS-specific, complex |
| Subprocess + `stty` | Fragile, slow |

### Minimum External Dependency

```
pyserial>=3.5  # ~100KB, pure Python
```

This is the one area where an external dependency is effectively **mandatory** for cross-platform support.

---

## 9. Persistence (YES - pickle is stdlib)

### What's Possible

```python
# skill_learning.py - stdlib persistence
import pickle
import json
from pathlib import Path

class SkillLearner:
    def save(self, path: str) -> None:
        """Save using pickle (stdlib)."""
        data = {
            'version': 1,
            'config': self._config.__dict__,
            'skills': {
                name: {
                    'name': skill.name,
                    'description': skill.description,
                    'policy_weights': skill.policy_weights,
                    'value_weights': skill.value_weights,
                    'success_rate': skill.success_rate,
                    'training_episodes': skill.training_episodes,
                }
                for name, skill in self._skills.items()
            },
            'metrics': {
                'total_experiences': self._total_experiences,
                'episode_count': self._episode_count,
            }
        }

        with open(path, 'wb') as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, path: str) -> None:
        """Load from pickle."""
        with open(path, 'rb') as f:
            data = pickle.load(f)

        # Version check
        if data.get('version', 0) < 1:
            raise ValueError("Incompatible save format")

        # Restore state
        self._skills = {
            name: LearnedSkill(**skill_data)
            for name, skill_data in data['skills'].items()
        }
        self._total_experiences = data['metrics']['total_experiences']
        self._episode_count = data['metrics']['episode_count']
```

### Effort & Quality

| Aspect | stdlib pickle | With safetensors |
|--------|---------------|------------------|
| Implementation | 1 day | 0.5 days |
| Speed | Good | Excellent |
| Security | Pickle vulnerabilities | Safe |
| Cross-platform | YES | YES |

---

## 10. Error Handling (YES - logging is stdlib)

### What's Possible

```python
# Throughout codebase - stdlib logging
import logging
import sys
from typing import Optional

def setup_robotics_logging(level: int = logging.INFO, log_file: Optional[str] = None):
    """Configure logging for robotics module."""

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    # File handler (optional)
    handlers = [console]
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Configure root logger for symbolu_robotics
    logger = logging.getLogger('symbolu_robotics')
    logger.setLevel(level)
    for handler in handlers:
        logger.addHandler(handler)

# Usage in modules
logger = logging.getLogger(__name__)

try:
    # ... operation
except ConnectionError as e:
    logger.warning(f"Connection failed: {e}, using fallback")
except Exception as e:
    logger.exception(f"Unexpected error in {__name__}")
    raise
```

### Effort & Quality: 100% equivalent to external libraries for basic needs.

---

## 11. Summary: No-External-Deps Implementation

### What CAN be done (8 of 10 areas)

| Area | Effort | Quality | Notes |
|------|--------|---------|-------|
| NN Training | 10 days | 60% | CPU only, basic algorithms |
| LLM Provider | 3 days | 40% | HTTP only, no streaming |
| MPC Planning | 6 days | 70% | Numerical gradients |
| HTN Planning | 4 days | 90% | Full functionality |
| Path Planning | 2 days | 95% | A* works great |
| FK/Kinematics | 5 days | 80% | FK yes, IK limited |
| URDF Parsing | 3 days | 85% | Basic parsing |
| Persistence | 1 day | 95% | pickle works |
| Error Handling | 1 day | 100% | logging is stdlib |

### What CANNOT be done

| Area | Reason | Minimum Dependency |
|------|--------|-------------------|
| Serial Communication | No stdlib serial | `pyserial` (100KB) |
| GPU Acceleration | Requires bindings | `torch` or `cupy` |
| Streaming LLM | urllib limitations | `httpx` or `aiohttp` |

### Total Effort Without External Deps

| Phase | Duration |
|-------|----------|
| Phase 1: NN + LLM | 13 days |
| Phase 2: Planning + FK | 17 days |
| Phase 3: Utils | 3 days |
| Phase 4: Testing | 5 days |
| **Total** | **38 days (~8 weeks)** |

### Comparison

| Approach | Duration | Package Size | Quality |
|----------|----------|--------------|---------|
| No external deps | 8 weeks | ~50 MB | 70% |
| With external deps | 3.5 weeks | ~2.3 GB | 95% |
| Hybrid (minimal deps) | 5 weeks | ~200 MB | 85% |

---

## 12. Recommended Hybrid Approach

If minimizing dependencies is important, consider this hybrid:

### Minimal Dependencies (200 MB total)

```toml
[project.dependencies]
numpy = ">=1.24.0"      # Already required
pyserial = ">=3.5"      # 100KB, essential for hardware

[project.optional-dependencies]
ml = ["torch>=2.0.0"]   # Only if training needed
llm = ["httpx>=0.24.0"] # Only if streaming needed
```

### Implementation Mix

| Area | Approach | Why |
|------|----------|-----|
| NN Training | Pure numpy REINFORCE | Simple, works |
| LLM Provider | stdlib urllib | Basic but functional |
| MPC Planning | Pure numpy BFGS | Good enough |
| HTN Planning | Pure Python | pyhop is pure Python anyway |
| Path Planning | Pure Python A* | Standard algorithm |
| FK/Kinematics | Pure numpy DH | Well-understood |
| URDF Parsing | stdlib xml.etree | XML is stdlib |
| Serial | pyserial (required) | No alternative |
| Persistence | stdlib pickle | Works fine |
| Logging | stdlib logging | Perfect |

**Result:** 5 weeks, 200 MB, 85% functionality

---

## 13. Conclusion

**8 of 10 upgrade areas can be implemented without external dependencies**, but with trade-offs:

- **Training:** 60% quality (no GPU, limited algorithms)
- **LLM:** 40% quality (no streaming, basic error handling)
- **Planning:** 70-95% quality (good for most cases)
- **Kinematics:** 80% quality (FK good, IK limited)

**Recommendation:**

1. If deployment size matters: Use hybrid approach (pyserial only)
2. If training quality matters: Add PyTorch
3. If LLM reliability matters: Add litellm
4. If planning performance matters: Add CasADi

The only **truly mandatory** external dependency is `pyserial` for hardware communication.
