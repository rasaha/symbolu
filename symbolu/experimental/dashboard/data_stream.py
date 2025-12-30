"""
SymbolU12 Dashboard Data Stream
================================

Real-time streaming of 124-dim cognitive state to dashboard.

Provides:
    - Queue-based async data transfer
    - State snapshots with full metrics
    - WebSocket-ready data formatting
    - Historical buffer for trend analysis

The stream is the "nervous system" connecting the model
to the Pratyaksha dashboard.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque
import queue
import threading
import time
import json

import torch


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class AlertLevel(Enum):
    """Alert severity levels."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AxiomType(Enum):
    """Type of axiomatic violation."""
    NONE = "none"
    IDENTITY = "identity"       # A ≠ A detected
    CAUSALITY = "causality"     # Grounding failure
    CATEGORY = "category"       # Boundary collision
    PHASE_LOCK = "phase_lock"   # Trace violation


@dataclass
class BhavaSnapshot:
    """Snapshot of 12-dim Bhava distribution."""
    factual: float = 0.0           # Nirṇayātmaka
    analytical: float = 0.0        # Viśleṣaṇātmaka
    instructive: float = 0.0       # Upadeśātmaka
    questioning: float = 0.0       # Praśnārthaka
    speculative: float = 0.0       # Avasthātmaka
    argumentative: float = 0.0     # Tārkika
    narrative: float = 0.0         # Ākhyānātmaka
    emotive: float = 0.0           # Bhāvātmaka
    imperative: float = 0.0        # Ādeśātmaka
    uncertain: float = 0.0         # Sandigdhātmaka
    metalinguistic: float = 0.0    # Metābhāṣika
    sattvic: float = 0.0           # Sāttvika

    def to_list(self) -> List[float]:
        """Convert to list for radar chart."""
        return [
            self.factual, self.analytical, self.instructive,
            self.questioning, self.speculative, self.argumentative,
            self.narrative, self.emotive, self.imperative,
            self.uncertain, self.metalinguistic, self.sattvic,
        ]

    @staticmethod
    def from_tensor(tensor: torch.Tensor) -> 'BhavaSnapshot':
        """Create from 12-dim tensor."""
        if tensor.dim() > 1:
            tensor = tensor.squeeze()
        values = tensor.tolist()
        return BhavaSnapshot(
            factual=values[0] if len(values) > 0 else 0.0,
            analytical=values[1] if len(values) > 1 else 0.0,
            instructive=values[2] if len(values) > 2 else 0.0,
            questioning=values[3] if len(values) > 3 else 0.0,
            speculative=values[4] if len(values) > 4 else 0.0,
            argumentative=values[5] if len(values) > 5 else 0.0,
            narrative=values[6] if len(values) > 6 else 0.0,
            emotive=values[7] if len(values) > 7 else 0.0,
            imperative=values[8] if len(values) > 8 else 0.0,
            uncertain=values[9] if len(values) > 9 else 0.0,
            metalinguistic=values[10] if len(values) > 10 else 0.0,
            sattvic=values[11] if len(values) > 11 else 0.0,
        )


@dataclass
class DynamicsSnapshot:
    """Snapshot of 4-dim dynamics."""
    momentum: float = 0.5      # d[0] - Inertia toward current state
    entropy: float = 0.5       # d[1] - Cognitive noise level
    confidence: float = 0.5    # d[2] - Self-certainty
    coherence: float = 0.5     # d[3] - Internal consistency

    @staticmethod
    def from_tensor(tensor: torch.Tensor) -> 'DynamicsSnapshot':
        """Create from 4-dim tensor."""
        if tensor.dim() > 1:
            tensor = tensor.squeeze()
        values = tensor.tolist()
        return DynamicsSnapshot(
            momentum=values[0] if len(values) > 0 else 0.5,
            entropy=values[1] if len(values) > 1 else 0.5,
            confidence=values[2] if len(values) > 2 else 0.5,
            coherence=values[3] if len(values) > 3 else 0.5,
        )


@dataclass
class AlertSnapshot:
    """Snapshot of active alerts."""
    level: AlertLevel = AlertLevel.NORMAL
    axiom_type: AxiomType = AxiomType.NONE
    message: str = ""
    trace_at_trigger: float = 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class StateSnapshot:
    """
    Complete snapshot of model state for dashboard.

    This is the "packet" sent to the dashboard every token.
    """
    # Timing
    timestamp: float = field(default_factory=time.time)
    step: int = 0
    token_id: int = 0
    token_text: str = ""

    # Core metrics
    trace: float = 1.0                    # Phase-Lock trace (τ)
    trace_threshold: float = 0.75         # Current threshold
    determinant: float = 1.0              # det(R_internal)

    # Cognitive state
    bhava: BhavaSnapshot = field(default_factory=BhavaSnapshot)
    dynamics: DynamicsSnapshot = field(default_factory=DynamicsSnapshot)

    # Derived metrics
    dominant_bhava: str = "sattvic"
    vritti_mode: str = "Pramāṇa"

    # Alerts
    alert: AlertSnapshot = field(default_factory=AlertSnapshot)

    # Phase info
    training_phase: str = "inference"
    meta_triggered: bool = False

    # Latency
    meta_latency_us: float = 0.0  # Microseconds for META transition

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp,
            'step': self.step,
            'token_id': self.token_id,
            'token_text': self.token_text,
            'trace': self.trace,
            'trace_threshold': self.trace_threshold,
            'determinant': self.determinant,
            'bhava': asdict(self.bhava),
            'dynamics': asdict(self.dynamics),
            'dominant_bhava': self.dominant_bhava,
            'vritti_mode': self.vritti_mode,
            'alert': {
                'level': self.alert.level.value,
                'axiom_type': self.alert.axiom_type.value,
                'message': self.alert.message,
                'trace_at_trigger': self.alert.trace_at_trigger,
            },
            'training_phase': self.training_phase,
            'meta_triggered': self.meta_triggered,
            'meta_latency_us': self.meta_latency_us,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


# =============================================================================
# DATA STREAM
# =============================================================================

class DashboardStream:
    """
    Real-time data stream for Pratyaksha dashboard.

    Provides thread-safe queue for async communication between
    model inference and dashboard visualization.
    """

    def __init__(
        self,
        buffer_size: int = 1000,
        history_size: int = 500,
    ):
        """
        Initialize dashboard stream.

        Args:
            buffer_size: Max pending snapshots in queue
            history_size: Rolling history for trend analysis
        """
        self.buffer_size = buffer_size
        self.history_size = history_size

        # Thread-safe queue for snapshots
        self.queue: queue.Queue = queue.Queue(maxsize=buffer_size)

        # Rolling history buffer
        self.history: deque = deque(maxlen=history_size)

        # Trace history for EKG
        self.trace_history: deque = deque(maxlen=history_size)

        # Subscribers for push-based updates
        self.subscribers: List[Callable[[StateSnapshot], None]] = []

        # State
        self.running = False
        self.step_counter = 0

        # Lock for thread safety
        self._lock = threading.Lock()

    def push(self, snapshot: StateSnapshot):
        """
        Push a snapshot to the stream.

        Called by model/trainer after each token generation.
        """
        with self._lock:
            self.step_counter += 1
            snapshot.step = self.step_counter

            # Add to history
            self.history.append(snapshot)
            self.trace_history.append(snapshot.trace)

            # Try to add to queue (non-blocking)
            try:
                self.queue.put_nowait(snapshot)
            except queue.Full:
                # Drop oldest if full
                try:
                    self.queue.get_nowait()
                    self.queue.put_nowait(snapshot)
                except queue.Empty:
                    pass

            # Notify subscribers
            for subscriber in self.subscribers:
                try:
                    subscriber(snapshot)
                except Exception:
                    pass  # Don't let subscriber errors break the stream

    def pop(self, timeout: float = 0.1) -> Optional[StateSnapshot]:
        """
        Pop a snapshot from the stream.

        Called by dashboard to get next snapshot.
        """
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def pop_all(self) -> List[StateSnapshot]:
        """Pop all available snapshots."""
        snapshots = []
        while True:
            try:
                snapshots.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return snapshots

    def subscribe(self, callback: Callable[[StateSnapshot], None]):
        """Add a subscriber for push-based updates."""
        with self._lock:
            self.subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[StateSnapshot], None]):
        """Remove a subscriber."""
        with self._lock:
            if callback in self.subscribers:
                self.subscribers.remove(callback)

    def get_trace_history(self) -> List[float]:
        """Get rolling trace history for EKG."""
        with self._lock:
            return list(self.trace_history)

    def get_history(self, n: Optional[int] = None) -> List[StateSnapshot]:
        """Get recent history snapshots."""
        with self._lock:
            if n is None:
                return list(self.history)
            return list(self.history)[-n:]

    def get_latest(self) -> Optional[StateSnapshot]:
        """Get most recent snapshot."""
        with self._lock:
            if self.history:
                return self.history[-1]
            return None

    def clear(self):
        """Clear all buffers."""
        with self._lock:
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break
            self.history.clear()
            self.trace_history.clear()
            self.step_counter = 0


# =============================================================================
# STATE BUILDER
# =============================================================================

class StateSnapshotBuilder:
    """
    Helper to build StateSnapshots from model outputs.

    Extracts relevant metrics from model state and formats
    for dashboard consumption.
    """

    BHAVA_NAMES = [
        'factual', 'analytical', 'instructive', 'questioning',
        'speculative', 'argumentative', 'narrative', 'emotive',
        'imperative', 'uncertain', 'metalinguistic', 'sattvic',
    ]

    VRITTI_MODES = ['Pramāṇa', 'Viparyaya', 'Vikalpa', 'Smṛti', 'Nidrā']

    def __init__(self, trace_threshold: float = 0.75):
        self.trace_threshold = trace_threshold
        self.last_meta_check_time: Optional[float] = None

    def build(
        self,
        trace: float,
        bhava_tensor: torch.Tensor,
        dynamics_tensor: torch.Tensor,
        determinant: float = 1.0,
        token_id: int = 0,
        token_text: str = "",
        training_phase: str = "inference",
        alert: Optional[AlertSnapshot] = None,
    ) -> StateSnapshot:
        """
        Build a StateSnapshot from model outputs.

        Args:
            trace: Phase-Lock trace value
            bhava_tensor: 12-dim Bhava distribution
            dynamics_tensor: 4-dim dynamics [momentum, entropy, confidence, coherence]
            determinant: det(R_internal)
            token_id: Current token ID
            token_text: Current token text
            training_phase: Current training phase
            alert: Active alert if any

        Returns:
            Complete StateSnapshot for dashboard
        """
        # Extract Bhava
        bhava = BhavaSnapshot.from_tensor(bhava_tensor)

        # Extract dynamics
        dynamics = DynamicsSnapshot.from_tensor(dynamics_tensor)

        # Find dominant Bhava
        bhava_values = bhava.to_list()
        dominant_idx = bhava_values.index(max(bhava_values))
        dominant_bhava = self.BHAVA_NAMES[dominant_idx]

        # Determine Vritti mode based on confidence and dominant Bhava
        vritti_mode = self._determine_vritti(dynamics.confidence, dominant_bhava)

        # Check for META trigger
        meta_triggered = trace < self.trace_threshold

        # Compute META latency
        meta_latency_us = 0.0
        if meta_triggered:
            if self.last_meta_check_time is not None:
                meta_latency_us = (time.time() - self.last_meta_check_time) * 1_000_000
            self.last_meta_check_time = time.time()
        else:
            self.last_meta_check_time = None

        # Default alert if none provided
        if alert is None:
            alert = AlertSnapshot()

        return StateSnapshot(
            timestamp=time.time(),
            token_id=token_id,
            token_text=token_text,
            trace=trace,
            trace_threshold=self.trace_threshold,
            determinant=determinant,
            bhava=bhava,
            dynamics=dynamics,
            dominant_bhava=dominant_bhava,
            vritti_mode=vritti_mode,
            alert=alert,
            training_phase=training_phase,
            meta_triggered=meta_triggered,
            meta_latency_us=meta_latency_us,
        )

    def _determine_vritti(self, confidence: float, dominant_bhava: str) -> str:
        """Determine Vritti mode from confidence and Bhava."""
        if dominant_bhava in ['factual', 'analytical', 'instructive']:
            if confidence > 0.8:
                return 'Pramāṇa'
            elif confidence > 0.5:
                return 'Anumāna'
            else:
                return 'Vikalpa'
        elif dominant_bhava in ['speculative', 'uncertain']:
            return 'Vikalpa'
        elif dominant_bhava == 'metalinguistic':
            return 'Nidrā'
        elif confidence < 0.4:
            return 'Viparyaya'
        else:
            return 'Smṛti'


# =============================================================================
# GLOBAL STREAM INSTANCE
# =============================================================================

# Singleton stream for easy access
_global_stream: Optional[DashboardStream] = None


def get_dashboard_stream() -> DashboardStream:
    """Get or create global dashboard stream."""
    global _global_stream
    if _global_stream is None:
        _global_stream = DashboardStream()
    return _global_stream


def reset_dashboard_stream():
    """Reset global dashboard stream."""
    global _global_stream
    if _global_stream is not None:
        _global_stream.clear()
    _global_stream = DashboardStream()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'AlertLevel',
    'AxiomType',
    'BhavaSnapshot',
    'DynamicsSnapshot',
    'AlertSnapshot',
    'StateSnapshot',
    'DashboardStream',
    'StateSnapshotBuilder',
    'get_dashboard_stream',
    'reset_dashboard_stream',
]
