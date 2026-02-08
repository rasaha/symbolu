"""
Voice Orchestration Models Tests
================================

Tests for voice session, request, response, and related models.
"""

import pytest
from datetime import datetime, timedelta
import uuid

from symbolu.voice.orchestration.models import (
    SessionState,
    InterruptionType,
    VoiceSession,
    VoiceRequest,
    VoiceResponse,
    InterruptionEvent,
    TurnMetrics,
)


class TestSessionState:
    """Tests for SessionState enum."""

    def test_all_states_defined(self):
        """Verify all expected states are defined."""
        assert SessionState.IDLE is not None
        assert SessionState.LISTENING is not None
        assert SessionState.PROCESSING is not None
        assert SessionState.SPEAKING is not None
        assert SessionState.INTERRUPTED is not None
        assert SessionState.CONFIRMING is not None
        assert SessionState.ENDED is not None


class TestInterruptionType:
    """Tests for InterruptionType enum."""

    def test_all_types_defined(self):
        """Verify all expected interruption types are defined."""
        assert InterruptionType.BARGE_IN is not None
        assert InterruptionType.CANCEL is not None
        assert InterruptionType.REDIRECT is not None


class TestVoiceSession:
    """Tests for VoiceSession dataclass."""

    def test_create_session(self):
        """Verify session creation with defaults."""
        session = VoiceSession.create()

        assert session.session_id is not None
        assert session.state == SessionState.IDLE
        assert session.turn_count == 0
        assert session.is_speaking is False
        assert session.is_listening is True

    def test_create_session_with_id(self):
        """Verify session creation with specific ID."""
        session = VoiceSession.create(session_id="test-session-123")
        assert session.session_id == "test-session-123"

    def test_is_speaking_property(self):
        """Verify is_speaking property reflects state."""
        session = VoiceSession.create()

        session.state = SessionState.IDLE
        assert session.is_speaking is False

        session.state = SessionState.SPEAKING
        assert session.is_speaking is True

    def test_is_listening_property(self):
        """Verify is_listening property reflects state."""
        session = VoiceSession.create()

        session.state = SessionState.IDLE
        assert session.is_listening is True

        session.state = SessionState.LISTENING
        assert session.is_listening is True

        session.state = SessionState.SPEAKING
        assert session.is_listening is False

    def test_duration_seconds_property(self):
        """Verify duration calculation."""
        session = VoiceSession.create()
        # Duration should be positive
        assert session.duration_seconds >= 0

    def test_start_listening(self):
        """Verify start_listening transition."""
        session = VoiceSession.create()
        session.start_listening()
        assert session.state == SessionState.LISTENING

    def test_start_processing(self):
        """Verify start_processing transition."""
        session = VoiceSession.create()
        session.start_processing()
        assert session.state == SessionState.PROCESSING

    def test_start_speaking(self):
        """Verify start_speaking transition."""
        session = VoiceSession.create()
        session.start_speaking(response_id="resp-123")

        assert session.state == SessionState.SPEAKING
        assert session.current_response_id == "resp-123"

    def test_stop_speaking(self):
        """Verify stop_speaking transition."""
        session = VoiceSession.create()
        session.start_speaking(response_id="resp-123")
        session.stop_speaking()

        assert session.state == SessionState.IDLE
        assert session.current_response_id is None
        assert session.last_agent_speech_end is not None

    def test_record_interruption(self):
        """Verify interruption recording."""
        session = VoiceSession.create()
        session.start_speaking(response_id="resp-123")
        session.record_interruption(InterruptionType.BARGE_IN)

        assert session.state == SessionState.INTERRUPTED
        assert "resp-123" in session.interrupted_responses

    def test_increment_turn(self):
        """Verify turn increment."""
        session = VoiceSession.create()
        assert session.turn_count == 0

        turn1 = session.increment_turn()
        assert turn1 == 1
        assert session.turn_count == 1

        turn2 = session.increment_turn()
        assert turn2 == 2
        assert session.turn_count == 2

    def test_end_session(self):
        """Verify session end."""
        session = VoiceSession.create()
        session.end()
        assert session.state == SessionState.ENDED


class TestVoiceRequest:
    """Tests for VoiceRequest dataclass."""

    def test_create_request(self):
        """Verify request creation."""
        request = VoiceRequest(
            text="Hello, how are you?",
            session_id="session-123",
            turn_id=1
        )

        assert request.text == "Hello, how are you?"
        assert request.session_id == "session-123"
        assert request.turn_id == 1
        assert request.request_id is not None
        assert request.is_confirmation is False
        assert request.transcript_confidence == 1.0

    def test_request_with_interruption_context(self):
        """Verify request with interruption context."""
        request = VoiceRequest(
            text="Actually, I meant...",
            session_id="session-123",
            turn_id=2,
            interrupted_response="resp-456",
            continuation_context="[User interrupted]"
        )

        assert request.interrupted_response == "resp-456"
        assert request.continuation_context == "[User interrupted]"

    def test_request_confirmation(self):
        """Verify confirmation request."""
        request = VoiceRequest(
            text="Yes",
            session_id="session-123",
            turn_id=3,
            is_confirmation=True
        )

        assert request.is_confirmation is True


class TestVoiceResponse:
    """Tests for VoiceResponse dataclass."""

    def test_create_response(self):
        """Verify response creation."""
        response = VoiceResponse.create(
            text="I'm doing well, thank you!",
            session_id="session-123",
            turn_id=1
        )

        assert response.text == "I'm doing well, thank you!"
        assert response.session_id == "session-123"
        assert response.turn_id == 1
        assert response.response_id is not None
        assert response.requires_confirmation is False

    def test_response_with_confirmation(self):
        """Verify response requiring confirmation."""
        response = VoiceResponse.create(
            text="Are you sure?",
            session_id="session-123",
            turn_id=2,
            requires_confirmation=True,
            confirmation_prompt="Please confirm."
        )

        assert response.requires_confirmation is True
        assert response.confirmation_prompt == "Please confirm."

    def test_response_with_tools(self):
        """Verify response with tool execution info."""
        response = VoiceResponse.create(
            text="Here's the weather...",
            session_id="session-123",
            turn_id=3,
            tools_executed=["weather_api", "calendar_api"]
        )

        assert "weather_api" in response.tools_executed
        assert "calendar_api" in response.tools_executed

    def test_response_with_blocked_actions(self):
        """Verify response with blocked actions."""
        response = VoiceResponse.create(
            text="I can't do that.",
            session_id="session-123",
            turn_id=4,
            actions_blocked=True,
            blocking_reasons=["safety_violation"]
        )

        assert response.actions_blocked is True
        assert "safety_violation" in response.blocking_reasons


class TestInterruptionEvent:
    """Tests for InterruptionEvent dataclass."""

    def test_create_event(self):
        """Verify event creation."""
        event = InterruptionEvent(
            interruption_type=InterruptionType.BARGE_IN,
            interrupted_response_id="resp-123",
            user_transcript="Wait, stop"
        )

        assert event.interruption_type == InterruptionType.BARGE_IN
        assert event.interrupted_response_id == "resp-123"
        assert event.user_transcript == "Wait, stop"
        assert event.timestamp is not None


class TestTurnMetrics:
    """Tests for TurnMetrics dataclass."""

    def test_create_metrics(self):
        """Verify metrics creation."""
        metrics = TurnMetrics(
            turn_id=1,
            session_id="session-123"
        )

        assert metrics.turn_id == 1
        assert metrics.session_id == "session-123"
        assert metrics.was_interrupted is False

    def test_calculate_latency(self):
        """Verify latency calculation."""
        metrics = TurnMetrics(
            turn_id=1,
            session_id="session-123"
        )

        now = datetime.utcnow()
        metrics.user_speech_end = now
        metrics.agent_speech_start = now + timedelta(milliseconds=250)

        latency = metrics.calculate_latency()
        assert latency == pytest.approx(250.0, rel=0.1)

    def test_calculate_latency_without_timestamps(self):
        """Verify latency calculation returns 0 without timestamps."""
        metrics = TurnMetrics(
            turn_id=1,
            session_id="session-123"
        )

        latency = metrics.calculate_latency()
        assert latency == 0.0
