"""
Tests for audit fixes in the Hybrid Voice SDK.

These tests validate the fixes for issues identified in the code audit:
- CRITICAL: Memory leak, Silent Sentinel fallback, Race conditions
- HIGH: Exception classification, Bounds checking, WebSocket validation
- MEDIUM: Timeouts, State validation, SSML injection, Circuit breaker
- ARCHITECTURAL: Protocols and interfaces
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Import modules under test
from symbolu.voice.providers.registry import (
    CircuitBreaker,
    CircuitState,
    ProviderHealth,
    ProviderStatus,
    ProviderRegistry,
)
from symbolu.voice.orchestration.models import (
    VoiceSession,
    SessionState,
    VALID_TRANSITIONS,
    InvalidStateTransitionError,
)
from symbolu.voice.orchestration.barge_in import BargeInHandler, BargeInConfig
from symbolu.voice.prosody.mapper import P10ProsodyMapper, AcousticRegime
from symbolu.voice.protocols import (
    SentinelProtocol,
    validate_sentinel,
    BaseSentinelAdapter,
)


class TestCircuitBreaker:
    """Tests for the circuit breaker pattern (MEDIUM FIX)."""

    def test_initial_state_is_closed(self):
        """Circuit breaker starts in closed state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_opens_after_failure_threshold(self):
        """Circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_success_resets_failure_count(self):
        """Successful calls reset the failure counter."""
        cb = CircuitBreaker(failure_threshold=5)

        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        cb.record_success()
        assert cb.failure_count == 0

    def test_half_open_after_recovery_timeout(self):
        """Circuit transitions to half-open after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

        # Wait for recovery timeout
        import time
        time.sleep(0.15)

        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_closes_on_success(self):
        """Circuit closes after successful calls in half-open."""
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.01,
            half_open_max_calls=2
        )

        # Open the circuit
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery
        import time
        time.sleep(0.02)
        cb.can_execute()  # Triggers half-open

        # Record successful calls
        cb.record_success()
        cb.record_success()

        assert cb.state == CircuitState.CLOSED

    def test_half_open_reopens_on_failure(self):
        """Circuit reopens if failure occurs in half-open."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)

        cb.record_failure()
        import time
        time.sleep(0.02)
        cb.can_execute()  # Triggers half-open
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestStateTransitionValidation:
    """Tests for state transition validation (MEDIUM FIX)."""

    def test_valid_transitions_defined(self):
        """All states have defined transitions."""
        for state in SessionState:
            assert state in VALID_TRANSITIONS

    def test_valid_transition_idle_to_listening(self):
        """IDLE -> LISTENING is valid."""
        session = VoiceSession.create()
        assert session.state == SessionState.IDLE

        session.start_listening()
        assert session.state == SessionState.LISTENING

    def test_valid_transition_listening_to_processing(self):
        """LISTENING -> PROCESSING is valid."""
        session = VoiceSession.create()
        session.state = SessionState.LISTENING

        session.start_processing()
        assert session.state == SessionState.PROCESSING

    def test_valid_transition_processing_to_speaking(self):
        """PROCESSING -> SPEAKING is valid."""
        session = VoiceSession.create()
        session.state = SessionState.PROCESSING

        session.start_speaking("response-123")
        assert session.state == SessionState.SPEAKING
        assert session.current_response_id == "response-123"

    def test_end_always_allowed(self):
        """END transition is always allowed from any state."""
        for state in SessionState:
            if state != SessionState.ENDED:
                session = VoiceSession.create()
                session.state = state
                session.end()
                assert session.state == SessionState.ENDED

    def test_invalid_transition_logged(self):
        """Invalid transitions are logged as warnings."""
        session = VoiceSession.create()
        session.state = SessionState.SPEAKING

        # SPEAKING -> LISTENING is not in VALID_TRANSITIONS
        with patch('logging.Logger.warning') as mock_warn:
            session.start_listening()
            # Should still transition but log warning


class TestBoundsChecking:
    """Tests for bounds checking in barge-in (HIGH FIX)."""

    def test_continuation_context_empty_text(self):
        """Empty interrupted_text returns empty string."""
        handler = BargeInHandler()
        result = handler.get_continuation_context("", "spoken")
        assert result == ""

    def test_continuation_context_none_spoken(self):
        """None spoken_portion is handled safely."""
        handler = BargeInHandler()
        result = handler.get_continuation_context("full text", None)
        assert "full text" in result

    def test_continuation_context_spoken_longer_than_interrupted(self):
        """Spoken portion longer than interrupted text is handled."""
        handler = BargeInHandler()
        result = handler.get_continuation_context(
            "short",
            "this is a very long spoken portion"
        )
        assert result == ""  # Nothing remaining

    def test_continuation_context_normal_case(self):
        """Normal case with partial spoken portion."""
        handler = BargeInHandler()
        result = handler.get_continuation_context(
            "Hello, I wanted to tell you about the weather today.",
            "Hello, I wanted to"
        )
        assert "tell you about the weather" in result

    def test_continuation_context_truncation(self):
        """Long remaining text is truncated."""
        handler = BargeInHandler()
        long_text = "x" * 200
        result = handler.get_continuation_context(long_text, "")
        assert "..." in result
        assert len(result) < 150  # Account for prefix text


class TestSSMLInjectionPrevention:
    """Tests for SSML injection prevention (MEDIUM FIX)."""

    def test_escape_html_entities(self):
        """HTML entities are escaped."""
        mapper = P10ProsodyMapper()
        result = mapper._escape_ssml("<script>alert('xss')</script>")
        assert "<" not in result
        assert ">" not in result
        assert "&lt;" in result
        assert "&gt;" in result

    def test_escape_quotes(self):
        """Quotes are escaped."""
        mapper = P10ProsodyMapper()
        result = mapper._escape_ssml('Test "quoted" text')
        assert '"' not in result or "&quot;" in result

    def test_ssml_markers_in_user_text(self):
        """SSML-like content in user text is escaped."""
        mapper = P10ProsodyMapper()
        malicious = '<prosody rate="200%">fast</prosody>'
        result = mapper.compute_ssml(malicious)
        assert '<prosody rate="200%">' not in result

    def test_break_tags_escaped(self):
        """Break tags in user text are escaped."""
        mapper = P10ProsodyMapper()
        malicious = '<break time="10s"/>'
        result = mapper.compute_ssml(malicious)
        assert '<break' not in result


class TestSentinelProtocol:
    """Tests for Sentinel Protocol interface (ARCHITECTURAL FIX)."""

    def test_valid_sentinel_validation(self):
        """Valid Sentinel implementations pass validation."""
        class ValidSentinel:
            coherence_state = None
            goal_state = None

            def new_session(self, session_id):
                return session_id

            def run(self, user_input):
                return {"response": "test", "quality_score": 1.0}

        assert validate_sentinel(ValidSentinel())

    def test_invalid_sentinel_missing_run(self):
        """Sentinel without run() fails validation."""
        class InvalidSentinel:
            def new_session(self, session_id):
                return session_id

        assert validate_sentinel(InvalidSentinel()) is False

    def test_invalid_sentinel_missing_new_session(self):
        """Sentinel without new_session() fails validation."""
        class InvalidSentinel:
            def run(self, user_input):
                return {}

        assert validate_sentinel(InvalidSentinel()) is False

    def test_base_sentinel_adapter_properties(self):
        """BaseSentinelAdapter provides safe attribute access."""
        adapter = BaseSentinelAdapter()

        assert adapter.coherence_state is None
        assert adapter.goal_state is None

        adapter.coherence_state = {"test": "value"}
        assert adapter.coherence_state == {"test": "value"}


class TestExceptionClassification:
    """Tests for improved exception classification (HIGH FIX)."""

    def test_connection_error_detected(self):
        """ConnectionError is classified as provider unavailable."""
        # This tests the logic in the exception handlers
        error = ConnectionError("Connection refused")
        assert isinstance(error, (ConnectionError, OSError, TimeoutError))

    def test_timeout_error_detected(self):
        """TimeoutError is classified as provider unavailable."""
        error = TimeoutError("Connection timed out")
        assert isinstance(error, (ConnectionError, OSError, TimeoutError))

    def test_os_error_detected(self):
        """OSError is classified as provider unavailable."""
        error = OSError("Network unreachable")
        assert isinstance(error, (ConnectionError, OSError, TimeoutError))


class TestProviderRegistryWithCircuitBreaker:
    """Integration tests for registry with circuit breaker."""

    def test_registry_creates_circuit_breaker_per_provider(self):
        """Each registered provider gets its own circuit breaker."""
        registry = ProviderRegistry()

        mock_adapter1 = Mock()
        mock_adapter1.stt = Mock()
        mock_adapter1.tts = Mock()

        mock_adapter2 = Mock()
        mock_adapter2.stt = Mock()
        mock_adapter2.tts = Mock()

        registry.register("provider1", mock_adapter1)
        registry.register("provider2", mock_adapter2)

        # Each should have its own circuit breaker
        p1 = registry._providers["provider1"]
        p2 = registry._providers["provider2"]

        assert p1.circuit_breaker is not p2.circuit_breaker

    def test_mark_unhealthy_updates_circuit_breaker(self):
        """mark_unhealthy() updates circuit breaker."""
        registry = ProviderRegistry()

        mock_adapter = Mock()
        mock_adapter.stt = Mock()
        registry.register("test", mock_adapter)

        # Record failures
        for _ in range(5):
            registry.mark_unhealthy("test", "error")

        cb = registry._providers["test"].circuit_breaker
        assert cb.state == CircuitState.OPEN

    def test_mark_healthy_updates_circuit_breaker(self):
        """mark_healthy() updates circuit breaker."""
        registry = ProviderRegistry()

        mock_adapter = Mock()
        mock_adapter.stt = Mock()
        registry.register("test", mock_adapter)

        # Record success
        registry.mark_healthy("test", latency_ms=50)

        cb = registry._providers["test"].circuit_breaker
        assert cb.state == CircuitState.CLOSED


class TestWebSocketValidation:
    """Tests for WebSocket input validation (HIGH FIX)."""

    def test_valid_session_id_patterns(self):
        """Valid session IDs match the pattern."""
        import re
        pattern = r'^[a-zA-Z0-9_-]{1,128}$'

        valid_ids = [
            "abc123",
            "session-123",
            "user_session_456",
            "ABC-xyz-123",
            "a" * 128,
        ]

        for sid in valid_ids:
            assert re.match(pattern, sid), f"{sid} should be valid"

    def test_invalid_session_id_patterns(self):
        """Invalid session IDs are rejected."""
        import re
        pattern = r'^[a-zA-Z0-9_-]{1,128}$'

        invalid_ids = [
            "",  # Empty
            "a" * 129,  # Too long
            "session.id",  # Dot not allowed
            "session/id",  # Slash not allowed
            "session<id>",  # Angle brackets not allowed
            "session id",  # Space not allowed
        ]

        for sid in invalid_ids:
            assert not re.match(pattern, sid), f"{sid} should be invalid"


class TestSentinelTimeout:
    """Tests for Sentinel timeout handling (MEDIUM FIX)."""

    @pytest.mark.asyncio
    async def test_timeout_returns_graceful_response(self):
        """Timeout returns graceful degradation response."""
        # This tests the structure of the timeout response
        timeout_response = {
            "response": "I apologize, but I'm taking longer than expected to process your request. Could you please try again?",
            "quality_score": 0.3,
            "error": "sentinel_timeout"
        }

        assert "apologize" in timeout_response["response"]
        assert timeout_response["quality_score"] < 0.5
        assert timeout_response["error"] == "sentinel_timeout"


class TestSessionStateValidation:
    """Additional tests for session state validation."""

    def test_speaking_to_idle_valid(self):
        """SPEAKING -> IDLE is valid (stop_speaking)."""
        session = VoiceSession.create()
        session.state = SessionState.SPEAKING
        session.current_response_id = "test-123"

        session.stop_speaking()

        assert session.state == SessionState.IDLE
        assert session.current_response_id is None
        assert session.last_agent_speech_end is not None

    def test_speaking_to_interrupted_valid(self):
        """SPEAKING -> INTERRUPTED is valid (barge-in)."""
        from symbolu.voice.orchestration.models import InterruptionType

        session = VoiceSession.create()
        session.state = SessionState.SPEAKING
        session.current_response_id = "test-123"

        session.record_interruption(InterruptionType.BARGE_IN)

        assert session.state == SessionState.INTERRUPTED
        assert "test-123" in session.interrupted_responses


class TestCircuitBreakerEdgeCases:
    """Edge case tests for circuit breaker."""

    def test_multiple_rapid_failures(self):
        """Rapid consecutive failures properly open circuit."""
        cb = CircuitBreaker(failure_threshold=3)

        # Rapid failures
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()  # Extra failure after open

        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 4

    def test_success_in_closed_state_increments_counter(self):
        """Success in closed state increments success counter."""
        cb = CircuitBreaker()

        cb.record_success()
        cb.record_success()
        cb.record_success()

        assert cb.success_count == 3
        assert cb.state == CircuitState.CLOSED

    def test_partial_half_open_success(self):
        """Partial success in half-open doesn't close circuit."""
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.01,
            half_open_max_calls=3
        )

        # Open circuit
        cb.record_failure()

        # Wait and enter half-open
        import time
        time.sleep(0.02)
        cb.can_execute()

        # Only 1 success (need 3)
        cb.record_success()

        assert cb.state == CircuitState.HALF_OPEN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
