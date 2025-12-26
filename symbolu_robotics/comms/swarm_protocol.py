"""
Swarm Protocol for Multi-Robot Coordination
=============================================

O10_UNIFYING: Multi-agent coordination.

Simple protocol for robot-to-robot communication.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
import time
import json


class MessageType(Enum):
    """Types of swarm messages."""
    HEARTBEAT = "heartbeat"
    STATE_SHARE = "state_share"
    TASK_ANNOUNCE = "task_announce"
    TASK_CLAIM = "task_claim"
    TASK_COMPLETE = "task_complete"
    HELP_REQUEST = "help_request"
    COLLISION_WARN = "collision_warn"
    FORMATION_UPDATE = "formation_update"


@dataclass
class SwarmMessage:
    """Message for swarm communication."""
    type: MessageType
    sender_id: str
    timestamp: float = field(default_factory=time.time)
    data: Dict = field(default_factory=dict)
    target_id: Optional[str] = None  # None = broadcast

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "data": self.data,
            "target_id": self.target_id
        })

    @classmethod
    def from_json(cls, json_str: str) -> "SwarmMessage":
        d = json.loads(json_str)
        return cls(
            type=MessageType(d["type"]),
            sender_id=d["sender_id"],
            timestamp=d["timestamp"],
            data=d["data"],
            target_id=d.get("target_id")
        )


@dataclass
class RobotInfo:
    """Information about a robot in the swarm."""
    robot_id: str
    position: tuple = (0.0, 0.0, 0.0)
    velocity: tuple = (0.0, 0.0, 0.0)
    status: str = "idle"
    last_seen: float = 0.0
    capabilities: List[str] = field(default_factory=list)


class SwarmProtocol:
    """
    Protocol for multi-robot coordination.

    Handles:
    - Peer discovery
    - State sharing
    - Task allocation
    - Collision avoidance
    """

    def __init__(
        self,
        robot_id: str,
        broadcast_fn: Optional[Callable[[str], None]] = None,
        unicast_fn: Optional[Callable[[str, str], None]] = None
    ):
        self.robot_id = robot_id
        self._broadcast = broadcast_fn
        self._unicast = unicast_fn

        # Known robots
        self._peers: Dict[str, RobotInfo] = {}

        # Message handlers
        self._handlers: Dict[MessageType, List[Callable]] = {}

        # Pending tasks
        self._available_tasks: List[Dict] = []
        self._claimed_tasks: List[str] = []

        # Register default handlers
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default message handlers."""
        self.on(MessageType.HEARTBEAT, self._handle_heartbeat)
        self.on(MessageType.STATE_SHARE, self._handle_state_share)
        self.on(MessageType.COLLISION_WARN, self._handle_collision_warn)

    def on(self, msg_type: MessageType, handler: Callable) -> None:
        """Register message handler."""
        if msg_type not in self._handlers:
            self._handlers[msg_type] = []
        self._handlers[msg_type].append(handler)

    def send(self, message: SwarmMessage) -> None:
        """Send a message."""
        json_msg = message.to_json()

        if message.target_id is None:
            # Broadcast
            if self._broadcast:
                self._broadcast(json_msg)
        else:
            # Unicast
            if self._unicast:
                self._unicast(message.target_id, json_msg)

    def receive(self, json_msg: str) -> None:
        """Receive and process a message."""
        try:
            msg = SwarmMessage.from_json(json_msg)

            # Ignore own messages
            if msg.sender_id == self.robot_id:
                return

            # Call handlers
            handlers = self._handlers.get(msg.type, [])
            for handler in handlers:
                handler(msg)

        except (json.JSONDecodeError, KeyError):
            pass  # Invalid message

    def _handle_heartbeat(self, msg: SwarmMessage) -> None:
        """Handle heartbeat message."""
        if msg.sender_id not in self._peers:
            self._peers[msg.sender_id] = RobotInfo(robot_id=msg.sender_id)

        peer = self._peers[msg.sender_id]
        peer.last_seen = msg.timestamp
        peer.status = msg.data.get("status", "unknown")
        if "position" in msg.data:
            peer.position = tuple(msg.data["position"])

    def _handle_state_share(self, msg: SwarmMessage) -> None:
        """Handle state share message."""
        if msg.sender_id in self._peers:
            peer = self._peers[msg.sender_id]
            peer.position = tuple(msg.data.get("position", peer.position))
            peer.velocity = tuple(msg.data.get("velocity", peer.velocity))
            peer.status = msg.data.get("status", peer.status)
            peer.last_seen = msg.timestamp

    def _handle_collision_warn(self, msg: SwarmMessage) -> None:
        """Handle collision warning."""
        # Trigger collision avoidance behavior
        pass

    # Public API

    def heartbeat(self, status: str = "active", position: tuple = None) -> None:
        """Send heartbeat."""
        self.send(SwarmMessage(
            type=MessageType.HEARTBEAT,
            sender_id=self.robot_id,
            data={
                "status": status,
                "position": list(position) if position else [0, 0, 0]
            }
        ))

    def share_state(
        self,
        position: tuple,
        velocity: tuple = (0, 0, 0),
        status: str = "active"
    ) -> None:
        """Share state with swarm."""
        self.send(SwarmMessage(
            type=MessageType.STATE_SHARE,
            sender_id=self.robot_id,
            data={
                "position": list(position),
                "velocity": list(velocity),
                "status": status
            }
        ))

    def announce_task(self, task_id: str, task_data: Dict) -> None:
        """Announce available task."""
        self.send(SwarmMessage(
            type=MessageType.TASK_ANNOUNCE,
            sender_id=self.robot_id,
            data={"task_id": task_id, **task_data}
        ))

    def claim_task(self, task_id: str) -> None:
        """Claim a task."""
        self._claimed_tasks.append(task_id)
        self.send(SwarmMessage(
            type=MessageType.TASK_CLAIM,
            sender_id=self.robot_id,
            data={"task_id": task_id}
        ))

    def warn_collision(self, target_id: str, data: Dict = None) -> None:
        """Warn another robot of potential collision."""
        self.send(SwarmMessage(
            type=MessageType.COLLISION_WARN,
            sender_id=self.robot_id,
            target_id=target_id,
            data=data or {}
        ))

    def get_peers(self) -> List[RobotInfo]:
        """Get list of known peers."""
        return list(self._peers.values())

    def get_peer(self, robot_id: str) -> Optional[RobotInfo]:
        """Get specific peer info."""
        return self._peers.get(robot_id)

    def cleanup_stale(self, timeout: float = 10.0) -> None:
        """Remove stale peers."""
        now = time.time()
        stale = [
            rid for rid, info in self._peers.items()
            if now - info.last_seen > timeout
        ]
        for rid in stale:
            del self._peers[rid]

    def compute_unifying_level(self) -> float:
        """
        Compute O10_UNIFYING layer activation.

        Based on swarm connectivity.
        """
        if not self._peers:
            return 0.1  # Solo operation

        # Active peers
        now = time.time()
        active = sum(1 for p in self._peers.values() if now - p.last_seen < 5.0)

        # More active peers = higher unifying
        return min(1.0, active / 5.0)
