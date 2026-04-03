"""
Conversation State Management for Pipeline B

Enables multi-turn interactions with context tracking:
- Message history management
- Intent evolution tracking
- Constraint accumulation across turns
- Session management

This provides the stateful layer needed for conversational generation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4
import json

from .semantic_layer import ParsedIntent, SemanticVector, IntentParser


class MessageRole(Enum):
    """Role of message sender."""
    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """Single message in conversation."""
    role: MessageRole
    content: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Parsed intent (for user messages)
    parsed_intent: Optional[ParsedIntent] = None

    # Generated results (for assistant messages)
    generated_sequences: Optional[Tuple[Tuple[str, ...], ...]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ConversationState:
    """
    Current state of a conversation.

    Tracks:
    - Accumulated semantic preferences
    - Active constraints
    - Generated sequences history
    - Conversation context
    """
    # Accumulated semantic vector (blended from all turns)
    accumulated_vector: SemanticVector = field(default_factory=SemanticVector)

    # Constraints that persist across turns
    persistent_constraints: Dict[str, Any] = field(default_factory=dict)

    # Constraints for current turn only
    turn_constraints: Dict[str, Any] = field(default_factory=dict)

    # Previously generated sequences (for exclusion/variation)
    generated_history: List[Tuple[str, ...]] = field(default_factory=list)

    # Turn counter
    turn_count: int = 0

    # Custom context data
    context: Dict[str, Any] = field(default_factory=dict)


class ConversationSession:
    """
    Manages a single conversation session.

    Provides:
    - Message history tracking
    - State evolution
    - Constraint accumulation
    - Intent blending across turns
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        max_history: int = 100,
        intent_decay: float = 0.7,
    ):
        """
        Initialize a conversation session.

        Args:
            session_id: Unique session identifier (auto-generated if None)
            max_history: Maximum messages to retain
            intent_decay: How much previous intents decay each turn (0-1)
        """
        self.session_id = session_id or str(uuid4())
        self.max_history = max_history
        self.intent_decay = intent_decay

        self.messages: List[Message] = []
        self.state = ConversationState()
        self.intent_parser = IntentParser()

        self.created_at = datetime.utcnow().isoformat()
        self.last_activity = self.created_at

    def add_user_message(self, content: str) -> ParsedIntent:
        """
        Add a user message and parse its intent.

        Args:
            content: User's message text

        Returns:
            ParsedIntent from the message
        """
        # Parse intent
        parsed = self.intent_parser.parse(content)

        # Create message
        message = Message(
            role=MessageRole.USER,
            content=content,
            parsed_intent=parsed,
        )

        self._add_message(message)

        # Update state with new intent
        self._update_state_with_intent(parsed)

        return parsed

    def add_assistant_message(
        self,
        content: str,
        sequences: Optional[Tuple[Tuple[str, ...], ...]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Add an assistant response message.

        Args:
            content: Response text
            sequences: Generated sequences (if any)
            metadata: Additional metadata

        Returns:
            Created message
        """
        message = Message(
            role=MessageRole.ASSISTANT,
            content=content,
            generated_sequences=sequences,
            metadata=metadata or {},
        )

        self._add_message(message)

        # Track generated sequences for history
        if sequences:
            for seq in sequences:
                if seq not in self.state.generated_history:
                    self.state.generated_history.append(seq)
            # Limit history size
            if len(self.state.generated_history) > 1000:
                self.state.generated_history = self.state.generated_history[-500:]

        return message

    def add_system_message(self, content: str) -> Message:
        """Add a system message (instructions, context)."""
        message = Message(
            role=MessageRole.SYSTEM,
            content=content,
        )
        self._add_message(message)
        return message

    def get_current_constraints(self) -> Dict[str, Any]:
        """
        Get merged constraints for current turn.

        Combines:
        - Persistent constraints (from previous turns)
        - Turn constraints (from current turn)
        - Exclusion of previously generated sequences
        """
        constraints = dict(self.state.persistent_constraints)
        constraints.update(self.state.turn_constraints)

        # Optionally exclude recently generated sequences
        if self.state.generated_history:
            recent = self.state.generated_history[-50:]  # Last 50
            if recent:
                existing_exclusions = constraints.get("sequence NOT IN", set())
                if isinstance(existing_exclusions, (list, tuple)):
                    existing_exclusions = set(existing_exclusions)
                constraints["sequence NOT IN"] = existing_exclusions | set(recent)

        return constraints

    def get_semantic_vector(self) -> SemanticVector:
        """Get current accumulated semantic vector."""
        return self.state.accumulated_vector

    def set_persistent_constraint(self, key: str, value: Any) -> None:
        """Set a constraint that persists across turns."""
        self.state.persistent_constraints[key] = value

    def clear_persistent_constraint(self, key: str) -> None:
        """Remove a persistent constraint."""
        self.state.persistent_constraints.pop(key, None)

    def set_context(self, key: str, value: Any) -> None:
        """Set custom context data."""
        self.state.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get custom context data."""
        return self.state.context.get(key, default)

    def get_history(self, limit: Optional[int] = None) -> List[Message]:
        """Get message history."""
        if limit:
            return self.messages[-limit:]
        return list(self.messages)

    def get_summary(self) -> Dict[str, Any]:
        """Get conversation summary."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "turn_count": self.state.turn_count,
            "message_count": len(self.messages),
            "sequences_generated": len(self.state.generated_history),
            "persistent_constraints": list(self.state.persistent_constraints.keys()),
            "semantic_vector": self.state.accumulated_vector.to_dict(),
        }

    def reset(self) -> None:
        """Reset conversation state while keeping session ID."""
        self.messages = []
        self.state = ConversationState()
        self.last_activity = datetime.utcnow().isoformat()

    def _add_message(self, message: Message) -> None:
        """Internal: add message and manage history."""
        self.messages.append(message)
        self.last_activity = message.timestamp

        # Trim history if needed
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]

    def _update_state_with_intent(self, intent: ParsedIntent) -> None:
        """Internal: update state based on parsed intent."""
        self.state.turn_count += 1

        # Decay previous accumulated vector
        prev = self.state.accumulated_vector
        decay = self.intent_decay

        # Blend with new intent vector
        new = intent.semantic_vector
        blended = SemanticVector(
            energy=prev.energy * decay + new.energy * (1 - decay) if new.energy != 0 else prev.energy * decay,
            duration=prev.duration * decay + new.duration * (1 - decay) if new.duration != 0 else prev.duration * decay,
            complexity=prev.complexity * decay + new.complexity * (1 - decay) if new.complexity != 0 else prev.complexity * decay,
            direction=prev.direction * decay + new.direction * (1 - decay) if new.direction != 0 else prev.direction * decay,
            stability=prev.stability * decay + new.stability * (1 - decay) if new.stability != 0 else prev.stability * decay,
            rhythm=prev.rhythm * decay + new.rhythm * (1 - decay) if new.rhythm != 0 else prev.rhythm * decay,
        )

        self.state.accumulated_vector = blended

        # Update turn constraints from new intent
        self.state.turn_constraints = intent.mechanical_constraints


class ConversationManager:
    """
    Manages multiple conversation sessions.

    Provides:
    - Session creation and retrieval
    - Session persistence (in-memory, could be extended to disk/db)
    - Session cleanup
    """

    def __init__(self, default_max_history: int = 100):
        self.sessions: Dict[str, ConversationSession] = {}
        self.default_max_history = default_max_history

    def create_session(
        self,
        session_id: Optional[str] = None,
        **kwargs
    ) -> ConversationSession:
        """Create a new conversation session."""
        session = ConversationSession(
            session_id=session_id,
            max_history=kwargs.get("max_history", self.default_max_history),
            intent_decay=kwargs.get("intent_decay", 0.7),
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get an existing session by ID."""
        return self.sessions.get(session_id)

    def get_or_create_session(
        self,
        session_id: str,
        **kwargs
    ) -> ConversationSession:
        """Get existing session or create new one."""
        if session_id in self.sessions:
            return self.sessions[session_id]
        return self.create_session(session_id=session_id, **kwargs)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions with summaries."""
        return [session.get_summary() for session in self.sessions.values()]

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Remove sessions older than max_age_hours."""
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        cutoff_iso = cutoff.isoformat()

        to_delete = [
            sid for sid, session in self.sessions.items()
            if session.last_activity < cutoff_iso
        ]

        for sid in to_delete:
            del self.sessions[sid]

        return len(to_delete)


# Global conversation manager (singleton pattern)
_global_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Get the global conversation manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = ConversationManager()
    return _global_manager


def chat(
    message: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Simple chat interface for conversational generation.

    Args:
        message: User's message
        session_id: Optional session ID for continuity

    Returns:
        Response with generated sequences and state info
    """
    from .pipeline_router import generate, PipelineType

    manager = get_conversation_manager()

    # Get or create session
    if session_id:
        session = manager.get_or_create_session(session_id)
    else:
        session = manager.create_session()

    # Add user message and parse intent
    intent = session.add_user_message(message)

    # Get merged constraints
    constraints = session.get_current_constraints()

    # Generate using Pipeline B (semantic)
    response = generate(
        target=constraints if constraints else None,
        intent=message,
        pipeline=PipelineType.SEMANTIC,
    )

    # Add assistant response
    session.add_assistant_message(
        content=f"Generated {len(response.sequences)} sequences",
        sequences=response.sequences,
        metadata={
            "intent_confidence": intent.confidence,
            "keywords_matched": intent.keywords_matched,
        },
    )

    return {
        "session_id": session.session_id,
        "sequences": response.sequences,
        "intent": {
            "keywords": intent.keywords_matched,
            "confidence": intent.confidence,
            "semantic_vector": intent.semantic_vector.to_dict(),
        },
        "constraints_applied": constraints,
        "turn_count": session.state.turn_count,
        "pipeline_used": response.pipeline_used.value,
    }
