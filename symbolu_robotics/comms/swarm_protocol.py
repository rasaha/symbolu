"""
Swarm Protocol for Multi-Robot Coordination
=============================================

O10_UNIFYING: Multi-agent coordination.

Protocol for robot-to-robot communication with full message handling.

Enhanced with coordination module integration:
- Task allocation messages (announce, bid, assign)
- Formation control messages
- Conflict resolution messages
- Shared world model updates

Uses SCC for swarm health monitoring.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum
import time
import json
import numpy as np


class MessageType(Enum):
    """Types of swarm messages."""
    # Core messages
    HEARTBEAT = "heartbeat"
    STATE_SHARE = "state_share"

    # Task allocation
    TASK_ANNOUNCE = "task_announce"
    TASK_BID = "task_bid"
    TASK_CLAIM = "task_claim"
    TASK_ASSIGN = "task_assign"
    TASK_COMPLETE = "task_complete"
    TASK_CANCEL = "task_cancel"

    # Formation control
    FORMATION_UPDATE = "formation_update"
    FORMATION_JOIN = "formation_join"
    FORMATION_LEAVE = "formation_leave"

    # Conflict resolution
    COLLISION_WARN = "collision_warn"
    CONFLICT_DETECTED = "conflict_detected"
    RESOLUTION_PROPOSE = "resolution_propose"
    RESOLUTION_ACCEPT = "resolution_accept"

    # Shared world
    WORLD_OBSERVATION = "world_observation"
    WORLD_SYNC_REQUEST = "world_sync_request"
    WORLD_SYNC_RESPONSE = "world_sync_response"

    # Misc
    HELP_REQUEST = "help_request"


@dataclass
class SwarmMessage:
    """Message for swarm communication."""
    type: MessageType
    sender_id: str
    timestamp: float = field(default_factory=time.time)
    data: Dict = field(default_factory=dict)
    target_id: Optional[str] = None  # None = broadcast
    sequence: int = 0  # Message sequence number

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "data": self.data,
            "target_id": self.target_id,
            "sequence": self.sequence,
        })

    @classmethod
    def from_json(cls, json_str: str) -> "SwarmMessage":
        d = json.loads(json_str)
        return cls(
            type=MessageType(d["type"]),
            sender_id=d["sender_id"],
            timestamp=d["timestamp"],
            data=d["data"],
            target_id=d.get("target_id"),
            sequence=d.get("sequence", 0),
        )


@dataclass
class RobotInfo:
    """Information about a robot in the swarm."""
    robot_id: str
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    status: str = "idle"
    last_seen: float = 0.0
    capabilities: List[str] = field(default_factory=list)
    coherence: float = 1.0
    priority: float = 0.5
    formation_id: Optional[str] = None


@dataclass
class TaskInfo:
    """Information about a swarm task."""
    task_id: str
    announcer_id: str
    task_type: str = "generic"
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    priority: int = 2
    status: str = "announced"
    assigned_to: Optional[str] = None
    bids: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None


@dataclass
class FormationInfo:
    """Information about a formation."""
    formation_id: str
    leader_id: str
    formation_type: str = "line"
    members: List[str] = field(default_factory=list)
    center: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    heading: float = 0.0
    coherence: float = 1.0


class SwarmProtocol:
    """
    Protocol for multi-robot coordination.

    Handles:
    - Peer discovery and health monitoring
    - Task allocation with bidding
    - Formation control
    - Conflict detection and resolution
    - Shared world model synchronization

    Integrates with coordination module components.
    """

    def __init__(
        self,
        robot_id: str,
        broadcast_fn: Optional[Callable[[str], None]] = None,
        unicast_fn: Optional[Callable[[str, str], None]] = None,
    ):
        self.robot_id = robot_id
        self._broadcast = broadcast_fn
        self._unicast = unicast_fn

        # Sequence counter
        self._sequence = 0

        # Known robots
        self._peers: Dict[str, RobotInfo] = {}

        # Message handlers
        self._handlers: Dict[MessageType, List[Callable]] = {}

        # Task tracking
        self._tasks: Dict[str, TaskInfo] = {}
        self._my_bids: Dict[str, Dict] = {}
        self._assigned_tasks: List[str] = []

        # Formation tracking
        self._formations: Dict[str, FormationInfo] = {}
        self._my_formation: Optional[str] = None

        # Conflict tracking
        self._active_conflicts: Dict[str, Dict] = {}
        self._pending_resolutions: Dict[str, Dict] = {}

        # Callbacks for coordination module integration
        self._on_task_announce: Optional[Callable] = None
        self._on_task_assign: Optional[Callable] = None
        self._on_formation_update: Optional[Callable] = None
        self._on_conflict: Optional[Callable] = None
        self._on_world_observation: Optional[Callable] = None

        # Register default handlers
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default message handlers."""
        # Core
        self.on(MessageType.HEARTBEAT, self._handle_heartbeat)
        self.on(MessageType.STATE_SHARE, self._handle_state_share)

        # Task allocation
        self.on(MessageType.TASK_ANNOUNCE, self._handle_task_announce)
        self.on(MessageType.TASK_BID, self._handle_task_bid)
        self.on(MessageType.TASK_ASSIGN, self._handle_task_assign)
        self.on(MessageType.TASK_COMPLETE, self._handle_task_complete)
        self.on(MessageType.TASK_CANCEL, self._handle_task_cancel)

        # Formation
        self.on(MessageType.FORMATION_UPDATE, self._handle_formation_update)
        self.on(MessageType.FORMATION_JOIN, self._handle_formation_join)
        self.on(MessageType.FORMATION_LEAVE, self._handle_formation_leave)

        # Conflict
        self.on(MessageType.COLLISION_WARN, self._handle_collision_warn)
        self.on(MessageType.CONFLICT_DETECTED, self._handle_conflict_detected)
        self.on(MessageType.RESOLUTION_PROPOSE, self._handle_resolution_propose)
        self.on(MessageType.RESOLUTION_ACCEPT, self._handle_resolution_accept)

        # World
        self.on(MessageType.WORLD_OBSERVATION, self._handle_world_observation)

    def on(self, msg_type: MessageType, handler: Callable) -> None:
        """Register message handler."""
        if msg_type not in self._handlers:
            self._handlers[msg_type] = []
        self._handlers[msg_type].append(handler)

    def set_callback(
        self,
        event: str,
        callback: Callable,
    ) -> None:
        """Set callback for coordination events."""
        if event == "task_announce":
            self._on_task_announce = callback
        elif event == "task_assign":
            self._on_task_assign = callback
        elif event == "formation_update":
            self._on_formation_update = callback
        elif event == "conflict":
            self._on_conflict = callback
        elif event == "world_observation":
            self._on_world_observation = callback

    def send(self, message: SwarmMessage) -> None:
        """Send a message."""
        message.sequence = self._sequence
        self._sequence += 1

        json_msg = message.to_json()

        if message.target_id is None:
            if self._broadcast:
                self._broadcast(json_msg)
        else:
            if self._unicast:
                self._unicast(message.target_id, json_msg)

    def receive(self, json_msg: str) -> Optional[SwarmMessage]:
        """Receive and process a message. Returns the message if valid."""
        try:
            msg = SwarmMessage.from_json(json_msg)

            # Ignore own messages
            if msg.sender_id == self.robot_id:
                return None

            # Call handlers
            handlers = self._handlers.get(msg.type, [])
            for handler in handlers:
                handler(msg)

            return msg

        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    # =========================================================================
    # Core Message Handlers
    # =========================================================================

    def _handle_heartbeat(self, msg: SwarmMessage) -> None:
        """Handle heartbeat message."""
        if msg.sender_id not in self._peers:
            self._peers[msg.sender_id] = RobotInfo(robot_id=msg.sender_id)

        peer = self._peers[msg.sender_id]
        peer.last_seen = msg.timestamp
        peer.status = msg.data.get("status", "unknown")
        if "position" in msg.data:
            peer.position = tuple(msg.data["position"])
        if "coherence" in msg.data:
            peer.coherence = msg.data["coherence"]
        if "capabilities" in msg.data:
            peer.capabilities = msg.data["capabilities"]

    def _handle_state_share(self, msg: SwarmMessage) -> None:
        """Handle state share message."""
        if msg.sender_id not in self._peers:
            self._peers[msg.sender_id] = RobotInfo(robot_id=msg.sender_id)

        peer = self._peers[msg.sender_id]
        peer.position = tuple(msg.data.get("position", peer.position))
        peer.velocity = tuple(msg.data.get("velocity", peer.velocity))
        peer.status = msg.data.get("status", peer.status)
        peer.coherence = msg.data.get("coherence", peer.coherence)
        peer.last_seen = msg.timestamp

    # =========================================================================
    # Task Allocation Handlers
    # =========================================================================

    def _handle_task_announce(self, msg: SwarmMessage) -> None:
        """Handle task announcement."""
        task_id = msg.data.get("task_id")
        if not task_id:
            return

        task = TaskInfo(
            task_id=task_id,
            announcer_id=msg.sender_id,
            task_type=msg.data.get("task_type", "generic"),
            position=tuple(msg.data.get("position", (0, 0, 0))),
            priority=msg.data.get("priority", 2),
            deadline=msg.data.get("deadline"),
        )
        self._tasks[task_id] = task

        if self._on_task_announce:
            self._on_task_announce(task)

    def _handle_task_bid(self, msg: SwarmMessage) -> None:
        """Handle task bid."""
        task_id = msg.data.get("task_id")
        if task_id not in self._tasks:
            return

        task = self._tasks[task_id]
        if task.announcer_id != self.robot_id:
            return  # Only announcer processes bids

        bid = {
            "robot_id": msg.sender_id,
            "score": msg.data.get("score", 0.0),
            "forward_score": msg.data.get("forward_score", 0.0),
            "backward_score": msg.data.get("backward_score", 0.0),
            "coherence": msg.data.get("coherence", 1.0),
            "timestamp": msg.timestamp,
        }
        task.bids.append(bid)

    def _handle_task_assign(self, msg: SwarmMessage) -> None:
        """Handle task assignment."""
        task_id = msg.data.get("task_id")
        assigned_to = msg.data.get("assigned_to")

        if task_id in self._tasks:
            self._tasks[task_id].status = "assigned"
            self._tasks[task_id].assigned_to = assigned_to

        if assigned_to == self.robot_id:
            self._assigned_tasks.append(task_id)
            if self._on_task_assign:
                self._on_task_assign(task_id, msg.data)

    def _handle_task_complete(self, msg: SwarmMessage) -> None:
        """Handle task completion."""
        task_id = msg.data.get("task_id")
        if task_id in self._tasks:
            self._tasks[task_id].status = "completed"
        if task_id in self._assigned_tasks:
            self._assigned_tasks.remove(task_id)

    def _handle_task_cancel(self, msg: SwarmMessage) -> None:
        """Handle task cancellation."""
        task_id = msg.data.get("task_id")
        if task_id in self._tasks:
            self._tasks[task_id].status = "cancelled"

    # =========================================================================
    # Formation Handlers
    # =========================================================================

    def _handle_formation_update(self, msg: SwarmMessage) -> None:
        """Handle formation update."""
        formation_id = msg.data.get("formation_id")
        if not formation_id:
            return

        if formation_id not in self._formations:
            self._formations[formation_id] = FormationInfo(
                formation_id=formation_id,
                leader_id=msg.data.get("leader_id", msg.sender_id),
            )

        formation = self._formations[formation_id]
        formation.formation_type = msg.data.get("formation_type", formation.formation_type)
        formation.center = tuple(msg.data.get("center", formation.center))
        formation.heading = msg.data.get("heading", formation.heading)
        formation.coherence = msg.data.get("coherence", formation.coherence)
        if "members" in msg.data:
            formation.members = msg.data["members"]

        if self._on_formation_update:
            self._on_formation_update(formation)

    def _handle_formation_join(self, msg: SwarmMessage) -> None:
        """Handle formation join request."""
        formation_id = msg.data.get("formation_id")
        if formation_id in self._formations:
            formation = self._formations[formation_id]
            if msg.sender_id not in formation.members:
                formation.members.append(msg.sender_id)

    def _handle_formation_leave(self, msg: SwarmMessage) -> None:
        """Handle formation leave."""
        formation_id = msg.data.get("formation_id")
        if formation_id in self._formations:
            formation = self._formations[formation_id]
            if msg.sender_id in formation.members:
                formation.members.remove(msg.sender_id)

    # =========================================================================
    # Conflict Resolution Handlers
    # =========================================================================

    def _handle_collision_warn(self, msg: SwarmMessage) -> None:
        """Handle collision warning."""
        conflict_id = f"{msg.sender_id}_{self.robot_id}_{int(msg.timestamp)}"
        self._active_conflicts[conflict_id] = {
            "type": "collision",
            "other_robot": msg.sender_id,
            "position": msg.data.get("position"),
            "time_to_collision": msg.data.get("time_to_collision", 0),
            "severity": msg.data.get("severity", "medium"),
        }

        if self._on_conflict:
            self._on_conflict(self._active_conflicts[conflict_id])

    def _handle_conflict_detected(self, msg: SwarmMessage) -> None:
        """Handle conflict detection notification."""
        conflict_id = msg.data.get("conflict_id")
        self._active_conflicts[conflict_id] = {
            "type": msg.data.get("conflict_type", "unknown"),
            "other_robot": msg.sender_id,
            "position": msg.data.get("position"),
            "severity": msg.data.get("severity", "medium"),
        }

        if self._on_conflict:
            self._on_conflict(self._active_conflicts[conflict_id])

    def _handle_resolution_propose(self, msg: SwarmMessage) -> None:
        """Handle resolution proposal."""
        conflict_id = msg.data.get("conflict_id")
        self._pending_resolutions[conflict_id] = {
            "strategy": msg.data.get("strategy"),
            "proposer": msg.sender_id,
            "my_action": msg.data.get("your_action", {}),
            "their_action": msg.data.get("my_action", {}),
        }

    def _handle_resolution_accept(self, msg: SwarmMessage) -> None:
        """Handle resolution acceptance."""
        conflict_id = msg.data.get("conflict_id")
        if conflict_id in self._active_conflicts:
            del self._active_conflicts[conflict_id]
        if conflict_id in self._pending_resolutions:
            del self._pending_resolutions[conflict_id]

    # =========================================================================
    # World Model Handlers
    # =========================================================================

    def _handle_world_observation(self, msg: SwarmMessage) -> None:
        """Handle world observation from another robot."""
        if self._on_world_observation:
            self._on_world_observation(msg.sender_id, msg.data)

    # =========================================================================
    # Public API - Core
    # =========================================================================

    def heartbeat(
        self,
        status: str = "active",
        position: Tuple[float, float, float] = None,
        coherence: float = 1.0,
        capabilities: List[str] = None,
    ) -> None:
        """Send heartbeat."""
        self.send(SwarmMessage(
            type=MessageType.HEARTBEAT,
            sender_id=self.robot_id,
            data={
                "status": status,
                "position": list(position) if position else [0, 0, 0],
                "coherence": coherence,
                "capabilities": capabilities or [],
            }
        ))

    def share_state(
        self,
        position: Tuple[float, float, float],
        velocity: Tuple[float, float, float] = (0, 0, 0),
        status: str = "active",
        coherence: float = 1.0,
    ) -> None:
        """Share state with swarm."""
        self.send(SwarmMessage(
            type=MessageType.STATE_SHARE,
            sender_id=self.robot_id,
            data={
                "position": list(position),
                "velocity": list(velocity),
                "status": status,
                "coherence": coherence,
            }
        ))

    # =========================================================================
    # Public API - Task Allocation
    # =========================================================================

    def announce_task(
        self,
        task_id: str,
        task_type: str = "generic",
        position: Tuple[float, float, float] = (0, 0, 0),
        priority: int = 2,
        deadline: Optional[float] = None,
        **kwargs,
    ) -> None:
        """Announce a task for bidding."""
        self.send(SwarmMessage(
            type=MessageType.TASK_ANNOUNCE,
            sender_id=self.robot_id,
            data={
                "task_id": task_id,
                "task_type": task_type,
                "position": list(position),
                "priority": priority,
                "deadline": deadline,
                **kwargs,
            }
        ))

    def bid_task(
        self,
        task_id: str,
        score: float,
        forward_score: float = 0.0,
        backward_score: float = 0.0,
        coherence: float = 1.0,
    ) -> None:
        """Submit bid for a task."""
        self._my_bids[task_id] = {"score": score, "timestamp": time.time()}
        self.send(SwarmMessage(
            type=MessageType.TASK_BID,
            sender_id=self.robot_id,
            data={
                "task_id": task_id,
                "score": score,
                "forward_score": forward_score,
                "backward_score": backward_score,
                "coherence": coherence,
            }
        ))

    def assign_task(self, task_id: str, robot_id: str, **kwargs) -> None:
        """Assign task to a robot."""
        self.send(SwarmMessage(
            type=MessageType.TASK_ASSIGN,
            sender_id=self.robot_id,
            data={
                "task_id": task_id,
                "assigned_to": robot_id,
                **kwargs,
            }
        ))

    def complete_task(self, task_id: str, success: bool = True) -> None:
        """Mark task as complete."""
        self.send(SwarmMessage(
            type=MessageType.TASK_COMPLETE,
            sender_id=self.robot_id,
            data={
                "task_id": task_id,
                "success": success,
            }
        ))

    # =========================================================================
    # Public API - Formation
    # =========================================================================

    def update_formation(
        self,
        formation_id: str,
        formation_type: str,
        center: Tuple[float, float, float],
        heading: float = 0.0,
        members: List[str] = None,
        coherence: float = 1.0,
    ) -> None:
        """Broadcast formation update."""
        self.send(SwarmMessage(
            type=MessageType.FORMATION_UPDATE,
            sender_id=self.robot_id,
            data={
                "formation_id": formation_id,
                "formation_type": formation_type,
                "center": list(center),
                "heading": heading,
                "members": members or [],
                "coherence": coherence,
            }
        ))

    def join_formation(self, formation_id: str) -> None:
        """Request to join a formation."""
        self._my_formation = formation_id
        self.send(SwarmMessage(
            type=MessageType.FORMATION_JOIN,
            sender_id=self.robot_id,
            data={"formation_id": formation_id}
        ))

    def leave_formation(self, formation_id: str) -> None:
        """Leave a formation."""
        self._my_formation = None
        self.send(SwarmMessage(
            type=MessageType.FORMATION_LEAVE,
            sender_id=self.robot_id,
            data={"formation_id": formation_id}
        ))

    # =========================================================================
    # Public API - Conflict Resolution
    # =========================================================================

    def warn_collision(
        self,
        target_id: str,
        position: Tuple[float, float, float] = None,
        time_to_collision: float = 0.0,
        severity: str = "medium",
    ) -> None:
        """Warn another robot of potential collision."""
        self.send(SwarmMessage(
            type=MessageType.COLLISION_WARN,
            sender_id=self.robot_id,
            target_id=target_id,
            data={
                "position": list(position) if position else None,
                "time_to_collision": time_to_collision,
                "severity": severity,
            }
        ))

    def report_conflict(
        self,
        conflict_id: str,
        conflict_type: str,
        other_robot: str,
        position: Tuple[float, float, float] = None,
        severity: str = "medium",
    ) -> None:
        """Report detected conflict."""
        self.send(SwarmMessage(
            type=MessageType.CONFLICT_DETECTED,
            sender_id=self.robot_id,
            target_id=other_robot,
            data={
                "conflict_id": conflict_id,
                "conflict_type": conflict_type,
                "position": list(position) if position else None,
                "severity": severity,
            }
        ))

    def propose_resolution(
        self,
        conflict_id: str,
        target_id: str,
        strategy: str,
        my_action: Dict,
        your_action: Dict,
    ) -> None:
        """Propose conflict resolution."""
        self.send(SwarmMessage(
            type=MessageType.RESOLUTION_PROPOSE,
            sender_id=self.robot_id,
            target_id=target_id,
            data={
                "conflict_id": conflict_id,
                "strategy": strategy,
                "my_action": my_action,
                "your_action": your_action,
            }
        ))

    def accept_resolution(self, conflict_id: str, target_id: str) -> None:
        """Accept proposed resolution."""
        self.send(SwarmMessage(
            type=MessageType.RESOLUTION_ACCEPT,
            sender_id=self.robot_id,
            target_id=target_id,
            data={"conflict_id": conflict_id}
        ))

    # =========================================================================
    # Public API - World Model
    # =========================================================================

    def share_observation(
        self,
        position: Tuple[float, float],
        cell_state: str,
        confidence: float = 1.0,
        object_class: Optional[str] = None,
    ) -> None:
        """Share world observation."""
        self.send(SwarmMessage(
            type=MessageType.WORLD_OBSERVATION,
            sender_id=self.robot_id,
            data={
                "position": list(position),
                "cell_state": cell_state,
                "confidence": confidence,
                "object_class": object_class,
            }
        ))

    # =========================================================================
    # Queries
    # =========================================================================

    def get_peers(self) -> List[RobotInfo]:
        """Get list of known peers."""
        return list(self._peers.values())

    def get_peer(self, robot_id: str) -> Optional[RobotInfo]:
        """Get specific peer info."""
        return self._peers.get(robot_id)

    def get_active_peers(self, timeout: float = 5.0) -> List[RobotInfo]:
        """Get peers seen within timeout."""
        now = time.time()
        return [p for p in self._peers.values() if now - p.last_seen < timeout]

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """Get task info."""
        return self._tasks.get(task_id)

    def get_formation(self, formation_id: str) -> Optional[FormationInfo]:
        """Get formation info."""
        return self._formations.get(formation_id)

    def get_active_conflicts(self) -> Dict[str, Dict]:
        """Get active conflicts."""
        return self._active_conflicts.copy()

    def cleanup_stale(self, timeout: float = 10.0) -> int:
        """Remove stale peers. Returns count removed."""
        now = time.time()
        stale = [
            rid for rid, info in self._peers.items()
            if now - info.last_seen > timeout
        ]
        for rid in stale:
            del self._peers[rid]
        return len(stale)

    def compute_unifying_level(self) -> float:
        """
        Compute O10_UNIFYING layer activation.

        Based on swarm connectivity and coordination.
        """
        if not self._peers:
            return 0.1  # Solo operation

        now = time.time()

        # Active peers factor
        active = sum(1 for p in self._peers.values() if now - p.last_seen < 5.0)
        peer_score = min(1.0, active / 5.0)

        # Average coherence
        coherences = [p.coherence for p in self._peers.values()]
        avg_coherence = np.mean(coherences) if coherences else 0.5

        # Task coordination
        active_tasks = sum(1 for t in self._tasks.values() if t.status == "assigned")
        task_score = min(1.0, active_tasks / 3.0)

        # Formation score
        formation_score = 0.0
        if self._my_formation and self._my_formation in self._formations:
            formation = self._formations[self._my_formation]
            formation_score = formation.coherence * (len(formation.members) / 5.0)
            formation_score = min(1.0, formation_score)

        # Combine
        o10 = (
            0.3 * peer_score +
            0.2 * avg_coherence +
            0.25 * task_score +
            0.25 * formation_score
        )

        return float(np.clip(o10, 0.0, 1.0))
