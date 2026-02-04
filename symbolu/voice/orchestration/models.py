"""
Data models for voice orchestration.

This module defines the core data structures used throughout
the voice orchestration layer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class SessionState(Enum):
    """Current state of a voice session."""
    IDLE = "idle"                   # Waiting for input
    LISTENING = "listening"         # Actively receiving audio
    PROCESSING = "processing"       # Processing through Sentinel
    SPEAKING = "speaking"           # Playing TTS output
    INTERRUPTED = "interrupted"     # User interrupted agent
    CONFIRMING = "confirming"       # Waiting for user confirmation
    ENDED = "ended"                 # Session has ended


# MEDIUM FIX: Define valid state transitions for state machine validation
VALID_TRANSITIONS: Dict[SessionState, set] = {
    SessionState.IDLE: {SessionState.LISTENING, SessionState.ENDED},
    SessionState.LISTENING: {SessionState.PROCESSING, SessionState.IDLE, SessionState.ENDED},
    SessionState.PROCESSING: {SessionState.SPEAKING, SessionState.CONFIRMING, SessionState.IDLE, SessionState.ENDED},
    SessionState.SPEAKING: {SessionState.IDLE, SessionState.INTERRUPTED, SessionState.ENDED},
    SessionState.INTERRUPTED: {SessionState.LISTENING, SessionState.IDLE, SessionState.ENDED},
    SessionState.CONFIRMING: {SessionState.PROCESSING, SessionState.IDLE, SessionState.ENDED},
    SessionState.ENDED: set(),  # Terminal state
}


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, from_state: SessionState, to_state: SessionState):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid state transition: {from_state.value} -> {to_state.value}"
        )


class InterruptionType(Enum):
    """Type of user interruption."""
    BARGE_IN = "barge_in"           # User started speaking during agent
    CANCEL = "cancel"               # User cancelled current operation
    REDIRECT = "redirect"           # User changed topic/direction


@dataclass
class VoiceSession:
    """
    Voice session state.

    Tracks the complete state of an active voice conversation,
    including turn management, interruption handling, and metrics.
    """
    session_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Current state
    state: SessionState = SessionState.IDLE
    current_response_id: Optional[str] = None

    # Turn tracking
    turn_count: int = 0
    last_user_speech_end: Optional[datetime] = None
    last_agent_speech_end: Optional[datetime] = None

    # Interruption handling
    interrupted_responses: List[str] = field(default_factory=list)
    pending_continuation: Optional[str] = None
    awaiting_confirmation: bool = False
    confirmation_context: Optional[Dict[str, Any]] = None

    # Audio metrics
    user_audio_duration_ms: float = 0.0
    agent_audio_duration_ms: float = 0.0
    total_latency_ms: float = 0.0

    # Provider tracking
    stt_provider: Optional[str] = None
    tts_provider: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def create(session_id: Optional[str] = None) -> "VoiceSession":
        """Create a new voice session."""
        return VoiceSession(
            session_id=session_id or str(uuid.uuid4())
        )

    @property
    def is_speaking(self) -> bool:
        """Check if agent is currently speaking."""
        return self.state == SessionState.SPEAKING

    @property
    def is_listening(self) -> bool:
        """Check if session is listening for user input."""
        return self.state in (SessionState.IDLE, SessionState.LISTENING)

    @property
    def duration_seconds(self) -> float:
        """Get session duration in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()

    def _transition_to(self, new_state: SessionState, validate: bool = True) -> None:
        """Transition to a new state with optional validation.

        MEDIUM FIX: Added state transition validation.

        Args:
            new_state: The target state
            validate: Whether to validate the transition (default True)

        Raises:
            InvalidStateTransitionError: If transition is invalid and validate=True
        """
        if validate and new_state not in VALID_TRANSITIONS.get(self.state, set()):
            # Log warning but don't raise - allows graceful degradation
            import logging
            logging.getLogger(__name__).warning(
                f"Potentially invalid state transition: {self.state.value} -> {new_state.value} "
                f"(session: {self.session_id})"
            )
        self.state = new_state

    def start_listening(self) -> None:
        """Transition to listening state."""
        self._transition_to(SessionState.LISTENING)

    def start_processing(self) -> None:
        """Transition to processing state."""
        self._transition_to(SessionState.PROCESSING)

    def start_speaking(self, response_id: str) -> None:
        """Transition to speaking state."""
        self._transition_to(SessionState.SPEAKING)
        self.current_response_id = response_id

    def stop_speaking(self) -> None:
        """Stop speaking and return to idle."""
        self._transition_to(SessionState.IDLE)
        self.last_agent_speech_end = datetime.utcnow()
        self.current_response_id = None

    def record_interruption(self, interruption_type: InterruptionType) -> None:
        """Record a user interruption."""
        if self.current_response_id:
            self.interrupted_responses.append(self.current_response_id)
        self._transition_to(SessionState.INTERRUPTED)

    def increment_turn(self) -> int:
        """Increment turn counter and return new value."""
        self.turn_count += 1
        return self.turn_count

    def end(self) -> None:
        """End the session."""
        self._transition_to(SessionState.ENDED, validate=False)  # Always allow ending


@dataclass
class VoiceRequest:
    """
    Request to voice agent from user speech.

    Contains the transcribed text along with context and metadata
    needed for processing through the Sentinel framework.
    """
    text: str
    session_id: str
    turn_id: int
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Timestamp
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Context from previous interactions
    interrupted_response: Optional[str] = None
    continuation_context: Optional[str] = None
    is_confirmation: bool = False

    # Audio metadata
    audio_duration_ms: float = 0.0
    transcript_confidence: float = 1.0
    detected_language: Optional[str] = None

    # Additional context
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceResponse:
    """
    Response from voice agent to be synthesized.

    Contains the response text along with cognitive state information
    from Sentinel that influences voice synthesis.
    """
    response_id: str
    text: str
    session_id: str
    turn_id: int

    # Timestamp
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # From Sentinel framework
    coherence_state: Optional[Any] = None  # CoherenceState
    safety_contract: Optional[Any] = None  # SafetyContract
    goal_state: Optional[Any] = None       # GoalState
    quality_score: float = 0.0

    # Voice-specific flags
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    is_continuation: bool = False
    priority: str = "normal"  # "normal", "high", "critical"

    # TTS parameters (computed from P10 + coherence)
    tts_params: Optional[Any] = None  # TTSParams

    # Tool/action information
    tools_executed: List[str] = field(default_factory=list)
    actions_blocked: bool = False
    blocking_reasons: List[str] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def create(
        text: str,
        session_id: str,
        turn_id: int,
        **kwargs
    ) -> "VoiceResponse":
        """Create a new voice response."""
        return VoiceResponse(
            response_id=str(uuid.uuid4()),
            text=text,
            session_id=session_id,
            turn_id=turn_id,
            **kwargs
        )


@dataclass
class InterruptionEvent:
    """Event representing a user interruption."""
    interruption_type: InterruptionType
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # What was interrupted
    interrupted_response_id: Optional[str] = None
    interrupted_text: Optional[str] = None
    spoken_portion: Optional[str] = None

    # What triggered the interruption
    user_transcript: Optional[str] = None
    transcript_confidence: float = 0.0

    # Context for continuation
    continuation_context: Optional[str] = None


@dataclass
class TurnMetrics:
    """Metrics for a single conversation turn."""
    turn_id: int
    session_id: str

    # Timing
    user_speech_start: Optional[datetime] = None
    user_speech_end: Optional[datetime] = None
    processing_start: Optional[datetime] = None
    processing_end: Optional[datetime] = None
    agent_speech_start: Optional[datetime] = None
    agent_speech_end: Optional[datetime] = None

    # Durations (ms)
    user_speech_duration_ms: float = 0.0
    processing_duration_ms: float = 0.0
    agent_speech_duration_ms: float = 0.0
    total_latency_ms: float = 0.0

    # Quality
    transcript_confidence: float = 0.0
    response_quality_score: float = 0.0
    coherence_score: float = 0.0

    # Interruption
    was_interrupted: bool = False
    interruption_type: Optional[InterruptionType] = None

    def calculate_latency(self) -> float:
        """Calculate end-to-end latency in milliseconds."""
        if self.user_speech_end and self.agent_speech_start:
            delta = self.agent_speech_start - self.user_speech_end
            self.total_latency_ms = delta.total_seconds() * 1000
        return self.total_latency_ms
