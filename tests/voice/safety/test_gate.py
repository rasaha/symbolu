"""
Safety Voice Gate Tests
=======================

Tests for safety-aware voice response processing,
including confirmations, disclaimers, and escalation.
"""

import pytest
from dataclasses import dataclass, field
from typing import List

from symbolu.voice.safety.gate import (
    SafetyAction,
    SafetyEvaluation,
    SafetyGateConfig,
    SafetyVoiceGate,
)
from symbolu.voice.orchestration.models import VoiceResponse


# Mock objects for testing
@dataclass
class MockCoherenceMetrics:
    """Mock coherence metrics."""
    internal_consistency: float = 0.8
    overall_coherence: float = 0.8


@dataclass
class MockCoherenceState:
    """Mock coherence state."""
    current_metrics: MockCoherenceMetrics = None

    def __post_init__(self):
        if self.current_metrics is None:
            self.current_metrics = MockCoherenceMetrics()


@dataclass
class MockSafetyContract:
    """Mock safety contract."""
    eligible: bool = True
    violated_preconditions: List[str] = field(default_factory=list)
    blocking_reasons: List[str] = field(default_factory=list)


@dataclass
class MockGoalState:
    """Mock goal state."""
    purpose: str = "Test purpose"
    actions: list = None

    def __post_init__(self):
        if self.actions is None:
            self.actions = []


class TestSafetyAction:
    """Tests for SafetyAction enum."""

    def test_all_actions_defined(self):
        """Verify all expected actions are defined."""
        assert SafetyAction.PASS is not None
        assert SafetyAction.CONFIRM is not None
        assert SafetyAction.DISCLAIM is not None
        assert SafetyAction.ESCALATE is not None


class TestSafetyEvaluation:
    """Tests for SafetyEvaluation dataclass."""

    def test_create_evaluation(self):
        """Verify evaluation creation."""
        evaluation = SafetyEvaluation(
            action=SafetyAction.PASS,
            original_response="Test response",
            modified_response="Test response"
        )

        assert evaluation.action == SafetyAction.PASS
        assert evaluation.original_response == "Test response"
        assert evaluation.reasons == []


class TestSafetyGateConfig:
    """Tests for SafetyGateConfig dataclass."""

    def test_default_config(self):
        """Verify default configuration."""
        config = SafetyGateConfig()

        assert config.enable_confirmations is True
        assert config.enable_disclaimers is True
        assert config.enable_escalation is True
        assert config.escalation_violation_threshold == 3

    def test_custom_config(self):
        """Verify custom configuration."""
        config = SafetyGateConfig(
            enable_confirmations=False,
            escalation_violation_threshold=5
        )

        assert config.enable_confirmations is False
        assert config.escalation_violation_threshold == 5


class TestSafetyVoiceGate:
    """Tests for SafetyVoiceGate."""

    def create_response(
        self,
        text: str = "Test response",
        safety_contract: MockSafetyContract = None,
        coherence_state: MockCoherenceState = None,
        goal_state: MockGoalState = None
    ) -> VoiceResponse:
        """Helper to create voice responses."""
        return VoiceResponse(
            response_id="resp-123",
            text=text,
            session_id="session-123",
            turn_id=1,
            safety_contract=safety_contract or MockSafetyContract(),
            coherence_state=coherence_state or MockCoherenceState(),
            goal_state=goal_state or MockGoalState()
        )

    @pytest.mark.asyncio
    async def test_pass_eligible_response(self):
        """Verify eligible responses pass through unchanged."""
        gate = SafetyVoiceGate()

        response = self.create_response(
            text="Here's the information you requested.",
            safety_contract=MockSafetyContract(eligible=True)
        )

        result = await gate.process(response)

        assert result.text == response.text
        assert result.requires_confirmation is False

    @pytest.mark.asyncio
    async def test_confirm_single_violation(self):
        """Verify single violation triggers confirmation."""
        gate = SafetyVoiceGate()

        contract = MockSafetyContract(
            eligible=False,
            violated_preconditions=["precondition_1_internal_consistency"],
            blocking_reasons=["internal_consistency 0.50 < 0.60"]
        )
        response = self.create_response(
            text="I'll proceed with the action.",
            safety_contract=contract
        )

        result = await gate.process(response)

        assert result.requires_confirmation is True
        assert "make sure I understand" in result.text or "confirm" in result.text.lower()

    @pytest.mark.asyncio
    async def test_disclaim_when_confirmations_disabled(self):
        """Verify disclaimer used when confirmations disabled."""
        config = SafetyGateConfig(enable_confirmations=False)
        gate = SafetyVoiceGate(config=config)

        contract = MockSafetyContract(
            eligible=False,
            violated_preconditions=["precondition_1"]
        )
        response = self.create_response(
            text="Here's the answer.",
            safety_contract=contract
        )

        result = await gate.process(response)

        assert result.requires_confirmation is False
        assert "Please note" in result.text or "note" in result.text.lower()

    @pytest.mark.asyncio
    async def test_escalate_multiple_violations(self):
        """Verify multiple violations trigger escalation."""
        gate = SafetyVoiceGate()

        contract = MockSafetyContract(
            eligible=False,
            violated_preconditions=[
                "precondition_1",
                "precondition_2",
                "precondition_3"
            ]
        )
        response = self.create_response(
            text="I'll do that.",
            safety_contract=contract
        )

        result = await gate.process(response)

        assert "specialist" in result.text.lower() or "human" in result.text.lower()

    @pytest.mark.asyncio
    async def test_escalate_very_low_coherence(self):
        """Verify very low coherence triggers escalation."""
        gate = SafetyVoiceGate()

        contract = MockSafetyContract(
            eligible=False,
            violated_preconditions=["precondition_1"]
        )
        coherence = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(internal_consistency=0.3)
        )
        response = self.create_response(
            text="I'll do that.",
            safety_contract=contract,
            coherence_state=coherence
        )

        result = await gate.process(response)

        assert "specialist" in result.text.lower() or "human" in result.text.lower()

    @pytest.mark.asyncio
    async def test_accumulated_violations_escalate(self):
        """Verify accumulated violations trigger escalation."""
        gate = SafetyVoiceGate(SafetyGateConfig(
            escalation_violation_threshold=2
        ))

        # First violation
        response1 = self.create_response(
            safety_contract=MockSafetyContract(
                eligible=False,
                violated_preconditions=["precondition_1"]
            )
        )
        await gate.process(response1)

        # Second violation - should escalate
        response2 = self.create_response(
            safety_contract=MockSafetyContract(
                eligible=False,
                violated_preconditions=["precondition_2"]
            )
        )
        result = await gate.process(response2)

        # With 2 violations total, should escalate
        assert "specialist" in result.text.lower() or "human" in result.text.lower()

    def test_process_confirmation_approved(self):
        """Verify confirmation approval returns original response."""
        gate = SafetyVoiceGate()

        # Simulate pending confirmation
        gate._pending_confirmations["session-123"] = {
            "id": "conf-123",
            "original_response": "Original text",
            "reasons": ["reason1"],
        }

        result = gate.process_confirmation("session-123", user_confirmed=True)

        assert result == "Original text"
        assert "session-123" not in gate._pending_confirmations

    def test_process_confirmation_declined(self):
        """Verify confirmation decline returns None."""
        gate = SafetyVoiceGate()

        # Simulate pending confirmation
        gate._pending_confirmations["session-123"] = {
            "id": "conf-123",
            "original_response": "Original text",
            "reasons": ["reason1"],
        }

        result = gate.process_confirmation("session-123", user_confirmed=False)

        assert result is None
        assert "session-123" not in gate._pending_confirmations

    def test_process_confirmation_no_pending(self):
        """Verify no-op when no pending confirmation."""
        gate = SafetyVoiceGate()

        result = gate.process_confirmation("session-123", user_confirmed=True)
        assert result is None

    def test_clear_session(self):
        """Verify session clearing removes all state."""
        gate = SafetyVoiceGate()

        # Add some state
        gate._pending_confirmations["session-123"] = {"test": "data"}
        gate._violation_history["session-123"] = ["violation1"]

        gate.clear_session("session-123")

        assert "session-123" not in gate._pending_confirmations
        assert "session-123" not in gate._violation_history

    def test_get_session_violations(self):
        """Verify getting session violation history."""
        gate = SafetyVoiceGate()

        gate._violation_history["session-123"] = ["v1", "v2"]

        violations = gate.get_session_violations("session-123")

        assert violations == ["v1", "v2"]

    def test_get_session_violations_empty(self):
        """Verify empty list for session without violations."""
        gate = SafetyVoiceGate()

        violations = gate.get_session_violations("nonexistent")
        assert violations == []

    def test_has_pending_confirmation(self):
        """Verify pending confirmation check."""
        gate = SafetyVoiceGate()

        assert gate.has_pending_confirmation == {}

        gate._pending_confirmations["session-123"] = {"test": "data"}

        assert "session-123" in gate.has_pending_confirmation

    @pytest.mark.asyncio
    async def test_disclaimer_content(self):
        """Verify disclaimer content is appropriate."""
        config = SafetyGateConfig(
            enable_confirmations=False,
            enable_disclaimers=True
        )
        gate = SafetyVoiceGate(config=config)

        contract = MockSafetyContract(
            eligible=False,
            violated_preconditions=["coherence_violation"],
            blocking_reasons=["coherence low"]
        )
        response = self.create_response(
            text="The answer is 42.",
            safety_contract=contract
        )

        result = await gate.process(response)

        # Should contain disclaimer
        assert "Please note" in result.text
        # Should still contain original response
        assert "42" in result.text

    @pytest.mark.asyncio
    async def test_confirmation_template_uses_action_summary(self):
        """Verify confirmation uses action summary."""
        gate = SafetyVoiceGate()

        goal = MockGoalState(purpose="Delete all files")
        contract = MockSafetyContract(
            eligible=False,
            violated_preconditions=["precondition_1"]
        )
        response = self.create_response(
            text="I'll delete the files.",
            safety_contract=contract,
            goal_state=goal
        )

        result = await gate.process(response)

        assert result.requires_confirmation is True
        # Should reference the action
        assert "Delete" in result.text or "delete" in result.text.lower()

    @pytest.mark.asyncio
    async def test_escalation_sets_high_priority(self):
        """Verify escalation responses have high priority."""
        gate = SafetyVoiceGate()

        contract = MockSafetyContract(
            eligible=False,
            violated_preconditions=["p1", "p2", "p3"]
        )
        response = self.create_response(safety_contract=contract)

        result = await gate.process(response)

        assert result.priority == "high"

    @pytest.mark.asyncio
    async def test_escalation_adds_metadata(self):
        """Verify escalation adds metadata."""
        gate = SafetyVoiceGate()

        contract = MockSafetyContract(
            eligible=False,
            violated_preconditions=["p1", "p2", "p3"]
        )
        response = self.create_response(safety_contract=contract)

        result = await gate.process(response)

        assert result.metadata.get("escalated") is True
