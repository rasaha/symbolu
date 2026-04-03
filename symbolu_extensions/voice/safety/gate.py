"""
Safety Voice Gate - Safety-aware voice response processing.

Applies Sentinel's safety contracts to voice responses, enabling:
- Verbal confirmation requests before risky actions
- Safety disclaimers and warnings
- Escalation to human operators when needed
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from ..orchestration.models import VoiceResponse

logger = logging.getLogger(__name__)


class SafetyAction(Enum):
    """Action to take based on safety evaluation."""
    PASS = "pass"           # Response passes safety checks
    CONFIRM = "confirm"     # Request user confirmation
    DISCLAIM = "disclaim"   # Add safety disclaimer
    ESCALATE = "escalate"   # Escalate to human


@dataclass
class SafetyEvaluation:
    """Result of safety evaluation."""
    action: SafetyAction
    original_response: str
    modified_response: str
    reasons: List[str] = field(default_factory=list)
    confirmation_prompt: Optional[str] = None
    blocked_action: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SafetyGateConfig:
    """Configuration for safety voice gate."""
    # Enable/disable features
    enable_confirmations: bool = True
    enable_disclaimers: bool = True
    enable_escalation: bool = True

    # Thresholds
    escalation_violation_threshold: int = 3   # Violations before escalation
    low_coherence_threshold: float = 0.4      # Coherence level for escalation

    # Confirmation templates
    action_confirmation_template: str = (
        "Before I proceed, I want to make sure I understand correctly. "
        "You're asking me to {action_summary}. Is that right?"
    )
    high_risk_warning_template: str = (
        "I want to flag that this action {risk_description}. "
        "Would you like me to continue?"
    )
    escalation_template: str = (
        "This request involves {concern}. "
        "I'd recommend speaking with a human specialist about this."
    )
    disclaimer_template: str = (
        "Please note: {disclaimer}"
    )


class SafetyVoiceGate:
    """
    Applies safety contracts to voice responses.

    When safety contract is not eligible, this gate can:
    1. Insert verbal confirmation requests
    2. Add safety disclaimers
    3. Escalate to human if needed

    Usage:
        gate = SafetyVoiceGate()
        gated_response = await gate.process(response)

        if gated_response.requires_confirmation:
            # Wait for user confirmation
            pass
    """

    def __init__(self, config: Optional[SafetyGateConfig] = None):
        """
        Initialize safety voice gate.

        Args:
            config: Configuration for safety gate
        """
        self.config = config or SafetyGateConfig()

        # Track pending confirmations by session
        self._pending_confirmations: Dict[str, Dict[str, Any]] = {}

        # Track violation history by session
        self._violation_history: Dict[str, List[str]] = {}

    async def process(self, response: VoiceResponse) -> VoiceResponse:
        """
        Process response through safety gate.

        May modify response to include confirmations, disclaimers,
        or escalation notices.

        Args:
            response: Original voice response

        Returns:
            Processed voice response (may be modified)
        """
        # Evaluate safety
        evaluation = self._evaluate_safety(response)

        # Apply appropriate action
        if evaluation.action == SafetyAction.PASS:
            return response

        elif evaluation.action == SafetyAction.CONFIRM:
            return self._create_confirmation_response(response, evaluation)

        elif evaluation.action == SafetyAction.DISCLAIM:
            return self._add_disclaimer(response, evaluation)

        elif evaluation.action == SafetyAction.ESCALATE:
            return self._create_escalation_response(response, evaluation)

        return response

    def _evaluate_safety(self, response: VoiceResponse) -> SafetyEvaluation:
        """Evaluate safety and determine action."""
        contract = response.safety_contract
        coherence = response.coherence_state

        reasons = []
        action = SafetyAction.PASS

        # Check safety contract
        if contract is not None:
            if hasattr(contract, 'eligible') and not contract.eligible:
                # Contract not eligible
                if hasattr(contract, 'violated_preconditions'):
                    reasons.extend([
                        f"Violated: {p}"
                        for p in contract.violated_preconditions
                    ])

                if hasattr(contract, 'blocking_reasons'):
                    reasons.extend(contract.blocking_reasons)

                # Determine action based on severity
                if self._requires_escalation(contract, coherence):
                    action = SafetyAction.ESCALATE
                elif self._requires_confirmation(contract):
                    action = SafetyAction.CONFIRM
                else:
                    action = SafetyAction.DISCLAIM

        # Track violations
        if reasons and action != SafetyAction.PASS:
            self._record_violation(response.session_id, reasons)

            # Check if accumulated violations warrant escalation
            session_violations = self._violation_history.get(
                response.session_id, []
            )
            if len(session_violations) >= self.config.escalation_violation_threshold:
                action = SafetyAction.ESCALATE
                reasons.append("Multiple safety violations in session")

        return SafetyEvaluation(
            action=action,
            original_response=response.text,
            modified_response=response.text,
            reasons=reasons
        )

    def _requires_escalation(
        self,
        contract: Any,
        coherence: Optional[Any]
    ) -> bool:
        """Check if response requires human escalation."""
        if not self.config.enable_escalation:
            return False

        # Multiple preconditions violated
        if hasattr(contract, 'violated_preconditions'):
            if len(contract.violated_preconditions) >= 3:
                return True

        # Very low coherence
        if coherence is not None:
            try:
                metrics = coherence.current_metrics
                if (hasattr(metrics, 'internal_consistency') and
                        metrics.internal_consistency < self.config.low_coherence_threshold):
                    return True
            except AttributeError:
                pass

        return False

    def _requires_confirmation(self, contract: Any) -> bool:
        """Check if response requires user confirmation."""
        if not self.config.enable_confirmations:
            return False

        # Any precondition violation typically needs confirmation
        if hasattr(contract, 'violated_preconditions'):
            return len(contract.violated_preconditions) > 0

        return False

    def _create_confirmation_response(
        self,
        original: VoiceResponse,
        evaluation: SafetyEvaluation
    ) -> VoiceResponse:
        """Create response that requests confirmation."""
        # Summarize what the agent was about to do
        action_summary = self._summarize_action(original)

        # Build confirmation text
        confirmation_text = self.config.action_confirmation_template.format(
            action_summary=action_summary
        )

        # Store pending confirmation
        confirmation_id = str(uuid.uuid4())
        self._pending_confirmations[original.session_id] = {
            "id": confirmation_id,
            "original_response": original.text,
            "reasons": evaluation.reasons,
            "timestamp": datetime.utcnow()
        }

        # Create modified response
        return VoiceResponse(
            response_id=original.response_id,
            text=confirmation_text,
            session_id=original.session_id,
            turn_id=original.turn_id,
            coherence_state=original.coherence_state,
            safety_contract=original.safety_contract,
            goal_state=original.goal_state,
            quality_score=original.quality_score,
            requires_confirmation=True,
            confirmation_prompt=confirmation_text,
            tts_params=original.tts_params,
            blocking_reasons=evaluation.reasons
        )

    def _create_escalation_response(
        self,
        original: VoiceResponse,
        evaluation: SafetyEvaluation
    ) -> VoiceResponse:
        """Create response that escalates to human."""
        concern = self._identify_concern(evaluation.reasons)

        escalation_text = self.config.escalation_template.format(
            concern=concern
        )

        return VoiceResponse(
            response_id=original.response_id,
            text=escalation_text,
            session_id=original.session_id,
            turn_id=original.turn_id,
            coherence_state=original.coherence_state,
            safety_contract=original.safety_contract,
            goal_state=original.goal_state,
            quality_score=original.quality_score,
            requires_confirmation=False,
            priority="high",
            tts_params=original.tts_params,
            blocking_reasons=evaluation.reasons,
            metadata={"escalated": True, "escalation_reason": concern}
        )

    def _add_disclaimer(
        self,
        original: VoiceResponse,
        evaluation: SafetyEvaluation
    ) -> VoiceResponse:
        """Add safety disclaimer to response."""
        if not self.config.enable_disclaimers:
            return original

        # Build disclaimer based on reasons
        disclaimer = self._build_disclaimer(evaluation.reasons)

        disclaimer_prefix = self.config.disclaimer_template.format(
            disclaimer=disclaimer
        )

        modified_text = f"{disclaimer_prefix} {original.text}"

        return VoiceResponse(
            response_id=original.response_id,
            text=modified_text,
            session_id=original.session_id,
            turn_id=original.turn_id,
            coherence_state=original.coherence_state,
            safety_contract=original.safety_contract,
            goal_state=original.goal_state,
            quality_score=original.quality_score,
            requires_confirmation=False,
            tts_params=original.tts_params,
            blocking_reasons=evaluation.reasons
        )

    def _summarize_action(self, response: VoiceResponse) -> str:
        """Summarize the intended action for confirmation."""
        if response.goal_state is not None:
            try:
                # Try to get action from goal state
                if hasattr(response.goal_state, 'actions') and response.goal_state.actions:
                    return response.goal_state.actions[0].description

                if hasattr(response.goal_state, 'purpose'):
                    purpose = response.goal_state.purpose
                    if len(purpose) > 100:
                        purpose = purpose[:100] + "..."
                    return purpose
            except AttributeError:
                pass

        # Fall back to summarizing response text
        text = response.text
        if len(text) > 100:
            text = text[:100] + "..."
        return f"respond with: {text}"

    def _identify_concern(self, reasons: List[str]) -> str:
        """Identify the main safety concern."""
        if reasons:
            # Return first reason, cleaned up
            concern = reasons[0]
            # Remove technical prefixes
            concern = concern.replace("Violated: ", "")
            concern = concern.replace("precondition_", "")
            return concern

        return "potential safety considerations"

    def _build_disclaimer(self, reasons: List[str]) -> str:
        """Build disclaimer text from reasons."""
        # Map technical reasons to human-readable disclaimers
        disclaimers = []

        for reason in reasons:
            if "coherence" in reason.lower() or "consistency" in reason.lower():
                disclaimers.append("I'm not entirely certain about this")
            elif "reversal" in reason.lower() or "uncertainty" in reason.lower():
                disclaimers.append("this may change based on new information")
            elif "alignment" in reason.lower():
                disclaimers.append("this may not fully address your question")
            else:
                disclaimers.append("I recommend verifying this information")

        if not disclaimers:
            return "I recommend verifying this information"

        # Deduplicate and join
        unique_disclaimers = list(dict.fromkeys(disclaimers))
        return " and ".join(unique_disclaimers[:2])

    def _record_violation(
        self,
        session_id: str,
        reasons: List[str]
    ) -> None:
        """Record safety violation for session."""
        if session_id not in self._violation_history:
            self._violation_history[session_id] = []

        self._violation_history[session_id].extend(reasons)

        # Keep only recent violations (last 10)
        self._violation_history[session_id] = \
            self._violation_history[session_id][-10:]

    def process_confirmation(
        self,
        session_id: str,
        user_confirmed: bool
    ) -> Optional[str]:
        """
        Process user's confirmation response.

        Args:
            session_id: Session ID
            user_confirmed: Whether user confirmed the action

        Returns:
            Original response text if confirmed, None otherwise
        """
        pending = self._pending_confirmations.pop(session_id, None)
        if pending is None:
            return None

        if user_confirmed:
            logger.info(f"User confirmed action in session {session_id}")
            return pending["original_response"]
        else:
            logger.info(f"User declined action in session {session_id}")
            return None

    def clear_session(self, session_id: str) -> None:
        """Clear all state for a session."""
        self._pending_confirmations.pop(session_id, None)
        self._violation_history.pop(session_id, None)

    def get_session_violations(self, session_id: str) -> List[str]:
        """Get violation history for a session."""
        return self._violation_history.get(session_id, []).copy()

    @property
    def has_pending_confirmation(self) -> Dict[str, bool]:
        """Check which sessions have pending confirmations."""
        return {
            session_id: True
            for session_id in self._pending_confirmations
        }
