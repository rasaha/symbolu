"""
Protocol definitions for voice SDK components.

These protocols define the interfaces that external components must implement
to integrate with the voice SDK, enabling loose coupling and testability.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class SentinelProtocol(Protocol):
    """Protocol for Sentinel framework integration.

    ARCHITECTURAL FIX: This protocol defines the interface that any
    Sentinel-like framework must implement to work with the voice SDK.
    This enables:
    - Loose coupling between voice SDK and Sentinel
    - Easy mocking for tests
    - Alternative framework implementations

    Required Attributes:
        coherence_state: Current coherence state (can be None)
        goal_state: Current goal state (can be None)

    Required Methods:
        new_session: Initialize a new session
        run: Process user input and return response
    """

    coherence_state: Optional[Any]
    goal_state: Optional[Any]

    def new_session(self, session_id: str) -> str:
        """Initialize a new Sentinel session.

        Args:
            session_id: Unique session identifier

        Returns:
            Session ID (may be the same or a new one)
        """
        ...

    def run(self, user_input: str) -> Dict[str, Any]:
        """Process user input through the agentic pipeline.

        Args:
            user_input: User's transcribed speech

        Returns:
            Dictionary containing:
            - response: str - The response text
            - quality_score: float - Quality score (0-1)
            - actions_executed: List[str] - Actions that were executed
            - actions_blocked: bool - Whether any actions were blocked
            - blocking_reasons: List[str] - Reasons for blocking
            - safety_contract: Optional[Any] - Safety contract info
        """
        ...


@runtime_checkable
class CoherenceStateProtocol(Protocol):
    """Protocol for coherence state objects.

    Defines the expected interface for coherence state from Sentinel.
    """

    @property
    def current_metrics(self) -> Any:
        """Get current coherence metrics."""
        ...


@runtime_checkable
class CoherenceMetricsProtocol(Protocol):
    """Protocol for coherence metrics.

    Defines the expected metrics that influence voice synthesis.
    """

    overall_coherence: float
    prediction_reversal_risk: Optional[float]
    drift_direction: Optional[str]
    internal_consistency: Optional[float]
    goal_alignment: Optional[float]


@runtime_checkable
class SafetyContractProtocol(Protocol):
    """Protocol for safety contract objects.

    Defines the expected interface for safety contracts from Sentinel.
    """

    eligible: bool
    violated_preconditions: List[str]
    blocking_reasons: List[str]


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Protocol for LLM client adapters.

    ARCHITECTURAL FIX: Unified interface for LLM providers,
    eliminating duplicate adapter implementations.
    """

    def call(self, prompt: str) -> str:
        """Send prompt to LLM and get response.

        Args:
            prompt: User prompt text

        Returns:
            LLM response text
        """
        ...


class BaseSentinelAdapter:
    """Base class for Sentinel adapters with default attribute handling.

    Provides safe attribute access for coherence_state and goal_state
    to avoid AttributeError when these are not set.
    """

    def __init__(self):
        self._coherence_state: Optional[Any] = None
        self._goal_state: Optional[Any] = None

    @property
    def coherence_state(self) -> Optional[Any]:
        """Get current coherence state."""
        return self._coherence_state

    @coherence_state.setter
    def coherence_state(self, value: Any) -> None:
        """Set coherence state."""
        self._coherence_state = value

    @property
    def goal_state(self) -> Optional[Any]:
        """Get current goal state."""
        return self._goal_state

    @goal_state.setter
    def goal_state(self, value: Any) -> None:
        """Set goal state."""
        self._goal_state = value


def validate_sentinel(sentinel: Any) -> bool:
    """Validate that an object implements SentinelProtocol.

    Args:
        sentinel: Object to validate

    Returns:
        True if object implements required interface

    Example:
        if not validate_sentinel(my_sentinel):
            raise TypeError("Sentinel must implement SentinelProtocol")
    """
    required_methods = ['new_session', 'run']

    for method in required_methods:
        if not hasattr(sentinel, method) or not callable(getattr(sentinel, method)):
            return False

    return True
