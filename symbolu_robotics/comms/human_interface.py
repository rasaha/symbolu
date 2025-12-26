"""
Human Interface for Robotics
==============================

Natural language and gesture-based human-robot interaction.

Enhanced with LLM integration for:
- Complex command understanding
- Context-aware responses
- Multi-turn dialogue
- Intent disambiguation

Integrates with Symbolu:
- O8_PURPOSE: Goal extraction from commands
- SCC coherence: Confidence in understanding
- BCVF: Action selection from ambiguous commands
"""

from dataclasses import dataclass, field
from typing import Optional, List, Callable, Dict, Any, Tuple
from enum import Enum
from abc import ABC, abstractmethod
import re
import json


class CommandType(Enum):
    """Types of human commands."""
    MOTION = "motion"
    MANIPULATION = "manipulation"
    NAVIGATION = "navigation"
    QUERY = "query"
    STOP = "stop"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    COMPLEX = "complex"  # Requires LLM understanding


class IntentConfidence(Enum):
    """Confidence level in parsed intent."""
    HIGH = "high"  # > 0.8
    MEDIUM = "medium"  # 0.5 - 0.8
    LOW = "low"  # < 0.5
    AMBIGUOUS = "ambiguous"  # Multiple possible intents


@dataclass
class ParsedCommand:
    """Parsed human command."""
    type: CommandType
    action: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    raw_text: str = ""

    # LLM-enhanced fields
    intent_confidence: IntentConfidence = IntentConfidence.HIGH
    alternative_intents: List[Tuple[str, float]] = field(default_factory=list)
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    requires_clarification: bool = False
    clarification_question: str = ""


@dataclass
class LLMConfig:
    """Configuration for LLM integration."""
    # Model settings
    model_name: str = "gpt-4"  # or local model
    temperature: float = 0.3
    max_tokens: int = 256

    # Behavior
    use_llm_for_complex: bool = True
    use_llm_for_response: bool = True
    fallback_to_regex: bool = True

    # Coherence integration
    require_high_coherence: bool = True
    min_coherence_for_llm: float = 0.5

    # Safety
    allow_unsafe_commands: bool = False
    unsafe_patterns: List[str] = field(default_factory=lambda: [
        r"\b(attack|harm|damage|destroy)\b",
        r"\b(ignore\s+safety)\b",
    ])


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def parse_command(
        self,
        text: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Parse command using LLM."""
        pass

    @abstractmethod
    def generate_response(
        self,
        command: ParsedCommand,
        success: bool,
        context: Dict[str, Any],
    ) -> str:
        """Generate natural response."""
        pass

    @abstractmethod
    def disambiguate(
        self,
        text: str,
        options: List[str],
        context: Dict[str, Any],
    ) -> Tuple[int, float]:
        """Disambiguate between options, return (index, confidence)."""
        pass


class MockLLMProvider(LLMProvider):
    """
    Mock LLM provider for testing without external API.

    Uses enhanced regex with heuristics.
    """

    def __init__(self):
        self._entity_patterns = {
            "location": r"(?:to|at|from)\s+(?:the\s+)?(\w+(?:\s+\w+)?)",
            "object": r"(?:the|a)\s+(\w+(?:\s+\w+)?)",
            "number": r"(\d+(?:\.\d+)?)\s*(?:meters?|m|degrees?|deg)?",
            "direction": r"\b(left|right|forward|backward|up|down)\b",
        }

    def parse_command(
        self,
        text: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Enhanced parsing with entity extraction."""
        text_lower = text.lower().strip()

        # Extract entities
        entities = {}
        for entity_type, pattern in self._entity_patterns.items():
            matches = re.findall(pattern, text_lower)
            if matches:
                entities[entity_type] = matches[0] if len(matches) == 1 else matches

        # Determine intent
        intent = "unknown"
        confidence = 0.5

        if re.search(r"\b(stop|halt|emergency)\b", text_lower):
            intent = "stop"
            confidence = 0.95
        elif re.search(r"\b(pick|grab|grasp)\b.*\b(\w+)\b", text_lower):
            intent = "pick"
            confidence = 0.85
        elif re.search(r"\b(put|place|drop)\b", text_lower):
            intent = "place"
            confidence = 0.85
        elif re.search(r"\b(go|move|navigate)\s+to\b", text_lower):
            intent = "goto"
            confidence = 0.8
        elif re.search(r"\b(move|go)\s+(forward|back)", text_lower):
            intent = "motion"
            confidence = 0.8
        elif "?" in text:
            intent = "query"
            confidence = 0.7

        # Check for complex/ambiguous commands
        alternatives = []
        if confidence < 0.8:
            # Generate alternatives
            if "pick" in text_lower or "get" in text_lower:
                alternatives.append(("pick", 0.6))
            if "go" in text_lower or "to" in text_lower:
                alternatives.append(("goto", 0.5))

        return {
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "alternatives": alternatives,
            "requires_clarification": confidence < 0.6 and len(alternatives) > 1,
        }

    def generate_response(
        self,
        command: ParsedCommand,
        success: bool,
        context: Dict[str, Any],
    ) -> str:
        """Generate contextual response."""
        if not success:
            reasons = context.get("failure_reasons", [])
            if reasons:
                return f"I couldn't {command.action}. {reasons[0]}"
            return f"Sorry, I wasn't able to {command.action}."

        # Context-aware responses
        task_history = context.get("task_history", [])
        location = context.get("current_location", "here")

        responses = {
            "pick": f"I've picked up {command.target or 'the object'}.",
            "place": f"Object placed at {command.parameters.get('location', location)}.",
            "goto": f"Arrived at {command.target or 'the destination'}.",
            "motion": "Motion complete.",
            "stop": "Stopped. Awaiting your next command.",
            "query": self._answer_query(command, context),
        }

        base = responses.get(command.action, "Done.")

        # Add context
        if len(task_history) > 0:
            base += f" (Task {len(task_history)} completed)"

        return base

    def _answer_query(self, command: ParsedCommand, context: Dict[str, Any]) -> str:
        """Generate answer to query."""
        text = command.raw_text.lower()

        if "where" in text:
            loc = context.get("current_location", "unknown location")
            return f"I'm currently at {loc}."
        elif "what" in text and "hold" in text:
            obj = context.get("holding", None)
            return f"I'm holding {obj}." if obj else "I'm not holding anything."
        elif "how" in text:
            return "I can help with picking, placing, and navigation tasks."

        return "I'm not sure how to answer that."

    def disambiguate(
        self,
        text: str,
        options: List[str],
        context: Dict[str, Any],
    ) -> Tuple[int, float]:
        """Simple disambiguation based on keyword matching."""
        text_lower = text.lower()

        scores = []
        for i, option in enumerate(options):
            option_lower = option.lower()
            # Count matching words
            words = set(option_lower.split())
            matches = sum(1 for word in words if word in text_lower)
            score = matches / max(len(words), 1)
            scores.append((i, score))

        best = max(scores, key=lambda x: x[1])
        return best[0], best[1]


class OpenAILLMProvider(LLMProvider):
    """
    OpenAI API-based LLM provider.

    Skeleton: Defines interface, actual API calls require external setup.
    """

    def __init__(self, api_key: Optional[str] = None, config: Optional[LLMConfig] = None):
        self._api_key = api_key
        self._config = config or LLMConfig()
        self._mock = MockLLMProvider()

        # System prompt for robotics
        self._system_prompt = """You are a robot command interpreter. Parse natural language commands into structured intents.

Output JSON with:
- intent: one of [pick, place, goto, motion, stop, query, unknown]
- confidence: 0.0-1.0
- entities: extracted entities (object, location, direction, number)
- parameters: action parameters
- requires_clarification: true if ambiguous
- clarification_question: question to ask if clarification needed

Context about the robot will be provided. Be conservative with confidence.
"""

    def parse_command(
        self,
        text: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Parse using OpenAI API."""
        # Skeleton: Would call OpenAI API here
        # For now, fall back to mock
        return self._mock.parse_command(text, context)

    def generate_response(
        self,
        command: ParsedCommand,
        success: bool,
        context: Dict[str, Any],
    ) -> str:
        """Generate response using OpenAI API."""
        # Skeleton: Would call OpenAI API here
        return self._mock.generate_response(command, success, context)

    def disambiguate(
        self,
        text: str,
        options: List[str],
        context: Dict[str, Any],
    ) -> Tuple[int, float]:
        """Disambiguate using OpenAI API."""
        # Skeleton: Would call OpenAI API here
        return self._mock.disambiguate(text, options, context)


class HumanInterface:
    """
    Interface for human-robot interaction.

    Enhanced with LLM for complex command understanding.
    Falls back to regex for simple commands (faster, no API cost).
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        config: Optional[LLMConfig] = None,
    ):
        self._config = config or LLMConfig()
        self._llm = llm_provider or MockLLMProvider()

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
        self._gesture_handlers: Dict[str, Callable] = {}

        # Context for LLM
        self._context: Dict[str, Any] = {}

    def set_context(self, key: str, value: Any) -> None:
        """Set context for LLM."""
        self._context[key] = value

    def update_context(self, updates: Dict[str, Any]) -> None:
        """Update multiple context values."""
        self._context.update(updates)

    def parse_command(
        self,
        text: str,
        coherence: float = 1.0,
    ) -> ParsedCommand:
        """
        Parse natural language command.

        Uses regex for simple commands, LLM for complex ones.
        """
        text_lower = text.lower().strip()

        # Check for unsafe commands
        if self._is_unsafe(text_lower):
            return ParsedCommand(
                type=CommandType.STOP,
                action="blocked",
                confidence=1.0,
                raw_text=text,
                requires_clarification=True,
                clarification_question="That command was blocked for safety reasons.",
            )

        # Try simple regex patterns first
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
                    raw_text=text,
                    intent_confidence=IntentConfidence.HIGH,
                )

        # Complex command: use LLM if coherence is sufficient
        if self._config.use_llm_for_complex:
            if coherence < self._config.min_coherence_for_llm:
                # Low coherence: don't trust complex parsing
                return ParsedCommand(
                    type=CommandType.STOP,
                    action="await_coherence",
                    confidence=0.3,
                    raw_text=text,
                    requires_clarification=True,
                    clarification_question="Please repeat your command clearly.",
                )

            return self._parse_with_llm(text)

        # Fallback: unknown command
        return ParsedCommand(
            type=CommandType.QUERY,
            action="unknown",
            confidence=0.3,
            raw_text=text,
            intent_confidence=IntentConfidence.LOW,
        )

    def _parse_with_llm(self, text: str) -> ParsedCommand:
        """Parse complex command using LLM."""
        result = self._llm.parse_command(text, self._context)

        intent = result.get("intent", "unknown")
        confidence = result.get("confidence", 0.5)
        entities = result.get("entities", {})
        alternatives = result.get("alternatives", [])

        # Determine command type
        intent_to_type = {
            "pick": CommandType.MANIPULATION,
            "place": CommandType.MANIPULATION,
            "goto": CommandType.NAVIGATION,
            "motion": CommandType.MOTION,
            "stop": CommandType.STOP,
            "query": CommandType.QUERY,
        }
        cmd_type = intent_to_type.get(intent, CommandType.COMPLEX)

        # Determine confidence level
        if confidence > 0.8:
            conf_level = IntentConfidence.HIGH
        elif confidence > 0.5:
            conf_level = IntentConfidence.MEDIUM
        elif len(alternatives) > 1:
            conf_level = IntentConfidence.AMBIGUOUS
        else:
            conf_level = IntentConfidence.LOW

        return ParsedCommand(
            type=cmd_type,
            action=intent,
            target=entities.get("object") or entities.get("location"),
            parameters={"entities": entities},
            confidence=confidence,
            raw_text=text,
            intent_confidence=conf_level,
            alternative_intents=alternatives,
            extracted_entities=entities,
            requires_clarification=result.get("requires_clarification", False),
            clarification_question=result.get("clarification_question", ""),
        )

    def _is_unsafe(self, text: str) -> bool:
        """Check if command contains unsafe patterns."""
        if self._config.allow_unsafe_commands:
            return False

        for pattern in self._config.unsafe_patterns:
            if re.search(pattern, text):
                return True
        return False

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

    def generate_response(
        self,
        command: ParsedCommand,
        success: bool,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate verbal response to command."""
        context = {**self._context}
        if additional_context:
            context.update(additional_context)

        if self._config.use_llm_for_response:
            return self._llm.generate_response(command, success, context)

        # Fallback responses
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
        coord_pattern = r"(\d+(?:\.\d+)?)\s*(?:,\s*)?(\d+(?:\.\d+)?)"
        match = re.search(coord_pattern, text)
        if match:
            return (float(match.group(1)), float(match.group(2)))
        return None


class ConversationManager:
    """
    Manages multi-turn conversations with humans.

    Enhanced with:
    - Conversation history for LLM context
    - Intent tracking across turns
    - Clarification handling
    """

    def __init__(
        self,
        interface: HumanInterface,
        max_history: int = 10,
    ):
        self.interface = interface
        self._context: Dict[str, Any] = {}
        self._pending_confirmation: Optional[ParsedCommand] = None
        self._pending_clarification: Optional[ParsedCommand] = None
        self._history: List[Dict[str, Any]] = []
        self._max_history = max_history

    def process(
        self,
        text: str,
        coherence: float = 1.0,
    ) -> str:
        """
        Process input and generate response.

        Handles multi-turn dialogue, confirmations, and clarifications.
        """
        # Update interface context with history
        self.interface.update_context({
            "conversation_history": self._history[-5:],
            "pending_clarification": self._pending_clarification is not None,
        })

        command = self.interface.parse_command(text, coherence)

        # Handle clarification response
        if self._pending_clarification:
            return self._handle_clarification_response(text, command)

        # Handle confirmation/cancellation of pending action
        if self._pending_confirmation:
            if command.type == CommandType.CONFIRM:
                response = self._execute(self._pending_confirmation)
                self._pending_confirmation = None
                return response
            elif command.type == CommandType.CANCEL:
                self._pending_confirmation = None
                return "Cancelled."

        # Handle new command
        if command.requires_clarification:
            self._pending_clarification = command
            return command.clarification_question or "Could you please clarify what you mean?"

        # Low confidence: ask for confirmation
        if command.confidence < 0.5 and command.type not in (CommandType.QUERY, CommandType.STOP):
            self._pending_confirmation = command
            if command.alternative_intents:
                alts = ", ".join(a[0] for a in command.alternative_intents[:3])
                return f"Did you mean to {command.action}? Or perhaps: {alts}?"
            return f"Did you mean to {command.action}? Please confirm."

        # Execute command
        return self._execute(command)

    def _handle_clarification_response(self, text: str, new_command: ParsedCommand) -> str:
        """Handle response to clarification question."""
        original = self._pending_clarification
        self._pending_clarification = None

        # Try to disambiguate
        if original and original.alternative_intents:
            options = [a[0] for a in original.alternative_intents]
            idx, conf = self.interface._llm.disambiguate(text, options, self._context)

            if conf > 0.5:
                # Use selected option
                original.action = options[idx]
                original.confidence = conf
                return self._execute(original)

        # Use new command if it's clear
        if new_command.confidence > 0.6:
            return self._execute(new_command)

        return "I still don't understand. Could you try rephrasing?"

    def _execute(self, command: ParsedCommand) -> str:
        """Execute command and return response."""
        # Store in history
        self._history.append({
            "input": command.raw_text,
            "action": command.action,
            "target": command.target,
            "success": True,
        })

        # Trim history
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Store context
        if command.target:
            self._context["last_target"] = command.target
        self._context["last_action"] = command.action
        self._context["task_history"] = [h["action"] for h in self._history]

        # Generate response
        return self.interface.generate_response(command, success=True, additional_context=self._context)

    def get_context(self) -> Dict[str, Any]:
        """Get conversation context."""
        return self._context.copy()

    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history."""
        return self._history.copy()

    def clear(self) -> None:
        """Clear conversation state."""
        self._context = {}
        self._pending_confirmation = None
        self._pending_clarification = None
        self._history = []
