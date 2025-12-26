"""
Human Interface for Robotics
==============================

Natural language and gesture-based human-robot interaction.
"""

from dataclasses import dataclass
from typing import Optional, List, Callable
from enum import Enum
import re


class CommandType(Enum):
    """Types of human commands."""
    MOTION = "motion"
    MANIPULATION = "manipulation"
    NAVIGATION = "navigation"
    QUERY = "query"
    STOP = "stop"
    CONFIRM = "confirm"
    CANCEL = "cancel"


@dataclass
class ParsedCommand:
    """Parsed human command."""
    type: CommandType
    action: str
    target: Optional[str] = None
    parameters: dict = None
    confidence: float = 1.0
    raw_text: str = ""

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class HumanInterface:
    """
    Interface for human-robot interaction.

    Parses natural language commands and gestures.
    """

    def __init__(self):
        # Command patterns (regex -> (type, action))
        self._patterns = [
            # Stop commands (highest priority)
            (r"\b(stop|halt|freeze|emergency)\b", CommandType.STOP, "stop"),

            # Motion commands
            (r"\b(move|go)\s+(forward|ahead)\b", CommandType.MOTION, "move_forward"),
            (r"\b(move|go)\s+(back|backward)\b", CommandType.MOTION, "move_backward"),
            (r"\b(turn|rotate)\s+(left)\b", CommandType.MOTION, "turn_left"),
            (r"\b(turn|rotate)\s+(right)\b", CommandType.MOTION, "turn_right"),

            # Manipulation
            (r"\b(pick|grab|grasp)\s+(?:up\s+)?(?:the\s+)?(\w+)\b", CommandType.MANIPULATION, "pick"),
            (r"\b(put|place|drop)\s+(?:down\s+)?(?:the\s+)?(\w+)?\b", CommandType.MANIPULATION, "place"),
            (r"\b(release|let\s+go)\b", CommandType.MANIPULATION, "release"),

            # Navigation
            (r"\b(go|navigate|move)\s+to\s+(?:the\s+)?(\w+)\b", CommandType.NAVIGATION, "goto"),
            (r"\b(come|follow)\s+(?:here|me)\b", CommandType.NAVIGATION, "follow"),

            # Queries
            (r"\b(where|what|how)\b.*\?", CommandType.QUERY, "query"),

            # Confirmations
            (r"\b(yes|okay|ok|confirm|sure|affirmative)\b", CommandType.CONFIRM, "confirm"),
            (r"\b(no|cancel|abort|negative)\b", CommandType.CANCEL, "cancel"),
        ]

        # Gesture handlers
        self._gesture_handlers: dict = {}

    def parse_command(self, text: str) -> ParsedCommand:
        """
        Parse natural language command.

        Args:
            text: Input text from human

        Returns:
            ParsedCommand with type, action, and parameters
        """
        text_lower = text.lower().strip()

        for pattern, cmd_type, action in self._patterns:
            match = re.search(pattern, text_lower)
            if match:
                # Extract target from groups if present
                target = None
                if len(match.groups()) > 0:
                    groups = [g for g in match.groups() if g]
                    if len(groups) > 1:
                        target = groups[-1]

                return ParsedCommand(
                    type=cmd_type,
                    action=action,
                    target=target,
                    confidence=0.9,
                    raw_text=text
                )

        # Unknown command
        return ParsedCommand(
            type=CommandType.QUERY,
            action="unknown",
            confidence=0.3,
            raw_text=text
        )

    def register_gesture(
        self,
        gesture_name: str,
        handler: Callable[[dict], ParsedCommand]
    ) -> None:
        """Register gesture handler."""
        self._gesture_handlers[gesture_name] = handler

    def process_gesture(self, gesture_name: str, data: dict = None) -> Optional[ParsedCommand]:
        """Process detected gesture."""
        handler = self._gesture_handlers.get(gesture_name)
        if handler:
            return handler(data or {})
        return None

    def generate_response(self, command: ParsedCommand, success: bool) -> str:
        """Generate verbal response to command."""
        if not success:
            return f"Sorry, I couldn't {command.action}."

        responses = {
            "move_forward": "Moving forward.",
            "move_backward": "Moving backward.",
            "turn_left": "Turning left.",
            "turn_right": "Turning right.",
            "pick": f"Picking up {command.target or 'object'}.",
            "place": "Placing object.",
            "release": "Releasing.",
            "goto": f"Going to {command.target or 'location'}.",
            "follow": "Following you.",
            "stop": "Stopping.",
            "confirm": "Confirmed.",
            "cancel": "Cancelled.",
        }

        return responses.get(command.action, "Command acknowledged.")

    def extract_location(self, text: str) -> Optional[tuple]:
        """Extract location coordinates from text if present."""
        # Pattern: numbers like "5 meters forward" or coordinates
        coord_pattern = r"(\d+(?:\.\d+)?)\s*(?:,\s*)?(\d+(?:\.\d+)?)"
        match = re.search(coord_pattern, text)
        if match:
            return (float(match.group(1)), float(match.group(2)))
        return None


class ConversationManager:
    """
    Manages multi-turn conversations with humans.
    """

    def __init__(self, interface: HumanInterface):
        self.interface = interface
        self._context: dict = {}
        self._pending_confirmation: Optional[ParsedCommand] = None
        self._history: List[tuple] = []  # (human_input, robot_response)

    def process(self, text: str) -> str:
        """
        Process input and generate response.

        Maintains conversation context.
        """
        command = self.interface.parse_command(text)

        # Handle confirmation/cancellation of pending action
        if self._pending_confirmation:
            if command.type == CommandType.CONFIRM:
                # Execute pending command
                response = self._execute(self._pending_confirmation)
                self._pending_confirmation = None
                return response
            elif command.type == CommandType.CANCEL:
                self._pending_confirmation = None
                return "Cancelled."

        # Low confidence: ask for confirmation
        if command.confidence < 0.5 and command.type != CommandType.QUERY:
            self._pending_confirmation = command
            return f"Did you mean to {command.action}? Please confirm."

        # Execute command
        return self._execute(command)

    def _execute(self, command: ParsedCommand) -> str:
        """Execute command and return response."""
        # Store in history
        self._history.append((command.raw_text, command.action))

        # Store context
        if command.target:
            self._context["last_target"] = command.target

        # Generate response
        return self.interface.generate_response(command, success=True)

    def get_context(self) -> dict:
        """Get conversation context."""
        return self._context.copy()

    def clear(self) -> None:
        """Clear conversation state."""
        self._context = {}
        self._pending_confirmation = None
        self._history = []
