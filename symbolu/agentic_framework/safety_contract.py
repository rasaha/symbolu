"""
Safety Contract Component

Fail-closed safety gate before any action execution.
Inspired by Phase 55 Agent-Handoff Safety Contract (AHSC).

CORE PRINCIPLE: Fail-Closed by Default
- Default state: eligible = False
- Permission requires: ALL preconditions satisfied
- Violation of ANY precondition: immediate denial
- No partial permissions
- No implicit escalation

PRECONDITIONS:
1. Internal consistency >= threshold
2. Goal alignment >= threshold
3. Prediction reversal risk <= threshold
4. Identity stability >= threshold
5. No recent blocked states
6. Agency level permits action

INVARIANTS:
- INV-SC-1: Immutable (frozen dataclass)
- INV-SC-2: Deterministic (same inputs -> same contract)
- INV-SC-3: Zero-LLM (pure Python logic)
- INV-SC-4: Fail-closed (eligible defaults to False)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SafetyContract:
    """
    Fail-closed safety contract for action authorization.

    CRITICAL INVARIANTS (from Phase 55):
    - Immutable: Cannot be modified after creation (frozen=True)
    - Deterministic: Same inputs -> same contract
    - Zero-LLM: Pure Python logic, no LLM calls
    - Fail-closed: eligible defaults to False
    """

    # Eligibility verdict
    eligible: bool = False  # Fail-closed default

    # Precondition results (tuples for immutability)
    satisfied_preconditions: Tuple[str, ...] = ()
    violated_preconditions: Tuple[str, ...] = ()
    blocking_reasons: Tuple[str, ...] = ()

    # Metrics used for evaluation (all bounded [0.0, 1.0])
    internal_consistency: float = 0.0
    goal_alignment: float = 0.0
    prediction_reversal_risk: float = 1.0  # Worst case default
    identity_stability: float = 0.0

    # Metadata
    contract_version: str = "1.0.0"
    evaluation_timestamp: str = ""
    session_id: str = ""
    turn_index: int = 0

    # Prohibited capabilities (always forbidden)
    forbidden_capabilities: Tuple[str, ...] = (
        "destructive_file_operations",
        "network_attacks",
        "credential_access",
        "privilege_escalation",
        "system_modification",
        "data_exfiltration",
        "malware_execution",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "eligible": self.eligible,
            "satisfied_preconditions": list(self.satisfied_preconditions),
            "violated_preconditions": list(self.violated_preconditions),
            "blocking_reasons": list(self.blocking_reasons),
            "internal_consistency": self.internal_consistency,
            "goal_alignment": self.goal_alignment,
            "prediction_reversal_risk": self.prediction_reversal_risk,
            "identity_stability": self.identity_stability,
            "contract_version": self.contract_version,
            "evaluation_timestamp": self.evaluation_timestamp,
            "session_id": self.session_id,
            "turn_index": self.turn_index,
            "forbidden_capabilities": list(self.forbidden_capabilities),
        }

    def is_action_forbidden(self, action_type: str) -> bool:
        """Check if action type is in forbidden list."""
        return action_type in self.forbidden_capabilities

    def get_rejection_summary(self) -> str:
        """Get human-readable rejection summary."""
        if self.eligible:
            return "Contract approved"

        reasons = "\n".join(f"  - {r}" for r in self.blocking_reasons)
        return f"Contract denied:\n{reasons}"


class SafetyContractEvaluator:
    """
    Evaluates safety contract preconditions.

    ALL preconditions must pass for eligible=True.
    Any failure -> eligible=False (fail-closed).

    PRECONDITIONS:
    1. Internal consistency >= threshold (0.60 default)
    2. Goal alignment >= threshold (0.60 default)
    3. Prediction reversal risk <= threshold (0.40 default)
    4. Identity stability >= threshold (0.60 default)
    5. No recent blocked states
    6. Agency level permits action
    """

    def __init__(
        self,
        consistency_threshold: float = 0.60,
        alignment_threshold: float = 0.60,
        reversal_risk_threshold: float = 0.40,
        stability_threshold: float = 0.60,
    ):
        """
        Initialize evaluator with thresholds.

        Args:
            consistency_threshold: Min internal consistency required
            alignment_threshold: Min goal alignment required
            reversal_risk_threshold: Max reversal risk allowed
            stability_threshold: Min identity stability required
        """
        self.consistency_threshold = consistency_threshold
        self.alignment_threshold = alignment_threshold
        self.reversal_risk_threshold = reversal_risk_threshold
        self.stability_threshold = stability_threshold

    def evaluate(
        self,
        coherence_state: Any,  # CoherenceState
        goal_state: Optional[Any] = None,  # GoalState
        recent_blocked: bool = False,
    ) -> SafetyContract:
        """
        Evaluate all preconditions and return immutable contract.

        INVARIANT: Same inputs -> same contract (deterministic)

        Args:
            coherence_state: Current CoherenceState
            goal_state: Optional GoalState
            recent_blocked: Whether recent turns were blocked

        Returns:
            Immutable SafetyContract
        """
        satisfied: List[str] = []
        violated: List[str] = []
        blocking_reasons: List[str] = []

        # Extract metrics from coherence state
        metrics = getattr(coherence_state, "current_metrics", None)
        if metrics is None:
            # No metrics available, deny
            violated.append("precondition_0_metrics_available")
            blocking_reasons.append("No coherence metrics available")
            return self._create_contract(
                eligible=False,
                satisfied=satisfied,
                violated=violated,
                blocking_reasons=blocking_reasons,
                coherence_state=coherence_state,
            )

        internal_consistency = getattr(metrics, "internal_consistency", 0.0)
        goal_alignment = getattr(metrics, "goal_alignment", 0.0)
        reversal_risk = getattr(metrics, "prediction_reversal_risk", 1.0)
        identity_stability = getattr(metrics, "identity_stability", 0.0)

        # Precondition 1: Internal consistency
        if internal_consistency >= self.consistency_threshold:
            satisfied.append("precondition_1_internal_consistency")
        else:
            violated.append("precondition_1_internal_consistency")
            blocking_reasons.append(
                f"internal_consistency {internal_consistency:.2f} < {self.consistency_threshold}"
            )

        # Precondition 2: Goal alignment
        if goal_alignment >= self.alignment_threshold:
            satisfied.append("precondition_2_goal_alignment")
        else:
            violated.append("precondition_2_goal_alignment")
            blocking_reasons.append(
                f"goal_alignment {goal_alignment:.2f} < {self.alignment_threshold}"
            )

        # Precondition 3: Prediction reversal risk
        if reversal_risk <= self.reversal_risk_threshold:
            satisfied.append("precondition_3_reversal_risk")
        else:
            violated.append("precondition_3_reversal_risk")
            blocking_reasons.append(
                f"reversal_risk {reversal_risk:.2f} > {self.reversal_risk_threshold}"
            )

        # Precondition 4: Identity stability
        if identity_stability >= self.stability_threshold:
            satisfied.append("precondition_4_identity_stability")
        else:
            violated.append("precondition_4_identity_stability")
            blocking_reasons.append(
                f"identity_stability {identity_stability:.2f} < {self.stability_threshold}"
            )

        # Precondition 5: No recent blocked states
        if not recent_blocked:
            satisfied.append("precondition_5_no_recent_blocked")
        else:
            violated.append("precondition_5_no_recent_blocked")
            blocking_reasons.append("recent_blocked_state")

        # Precondition 6: Agency level permits action
        if goal_state is not None:
            agency_level = getattr(goal_state, "agency_level", "INFORM")
            if agency_level in ("FULL", "CONFIRM"):
                satisfied.append("precondition_6_agency_permits")
            else:
                violated.append("precondition_6_agency_permits")
                blocking_reasons.append(f"agency_level={agency_level} does not permit actions")
        else:
            # No goal state, be conservative
            violated.append("precondition_6_agency_permits")
            blocking_reasons.append("no_goal_state_provided")

        # All-or-nothing decision
        eligible = len(violated) == 0

        return self._create_contract(
            eligible=eligible,
            satisfied=satisfied,
            violated=violated,
            blocking_reasons=blocking_reasons,
            coherence_state=coherence_state,
            metrics=metrics,
        )

    def _create_contract(
        self,
        eligible: bool,
        satisfied: List[str],
        violated: List[str],
        blocking_reasons: List[str],
        coherence_state: Any,
        metrics: Optional[Any] = None,
    ) -> SafetyContract:
        """Create immutable SafetyContract."""
        # Sort for determinism
        satisfied_tuple = tuple(sorted(satisfied))
        violated_tuple = tuple(sorted(violated))
        blocking_tuple = tuple(sorted(blocking_reasons))

        # Extract session info
        session_id = getattr(coherence_state, "session_id", "")
        turn_index = getattr(coherence_state, "current_turn", 0)

        # Extract metrics (with defaults)
        if metrics is not None:
            internal_consistency = getattr(metrics, "internal_consistency", 0.0)
            goal_alignment = getattr(metrics, "goal_alignment", 0.0)
            reversal_risk = getattr(metrics, "prediction_reversal_risk", 1.0)
            identity_stability = getattr(metrics, "identity_stability", 0.0)
        else:
            internal_consistency = 0.0
            goal_alignment = 0.0
            reversal_risk = 1.0
            identity_stability = 0.0

        return SafetyContract(
            eligible=eligible,
            satisfied_preconditions=satisfied_tuple,
            violated_preconditions=violated_tuple,
            blocking_reasons=blocking_tuple,
            internal_consistency=internal_consistency,
            goal_alignment=goal_alignment,
            prediction_reversal_risk=reversal_risk,
            identity_stability=identity_stability,
            evaluation_timestamp=datetime.utcnow().isoformat(),
            session_id=session_id,
            turn_index=turn_index,
        )

    def evaluate_action(
        self,
        contract: SafetyContract,
        action_type: str,
    ) -> Tuple[bool, str]:
        """
        Evaluate if specific action is allowed.

        Args:
            contract: Evaluated SafetyContract
            action_type: Type of action to check

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        # Check if contract is eligible
        if not contract.eligible:
            return False, f"Contract not eligible: {contract.blocking_reasons}"

        # Check if action type is forbidden
        if contract.is_action_forbidden(action_type):
            return False, f"Action type '{action_type}' is forbidden"

        return True, "Action allowed"


class SafetyGate:
    """
    High-level safety gate for action authorization.

    Combines contract evaluation with action filtering.
    """

    def __init__(
        self,
        evaluator: Optional[SafetyContractEvaluator] = None,
    ):
        """
        Initialize safety gate.

        Args:
            evaluator: Contract evaluator (uses default if None)
        """
        self.evaluator = evaluator or SafetyContractEvaluator()
        self._recent_blocked = False
        self._blocked_count = 0

    def check(
        self,
        coherence_state: Any,
        goal_state: Optional[Any] = None,
        action_types: Optional[List[str]] = None,
    ) -> Tuple[SafetyContract, List[str]]:
        """
        Check safety contract and filter allowed actions.

        Args:
            coherence_state: Current CoherenceState
            goal_state: Optional GoalState
            action_types: List of action types to filter

        Returns:
            Tuple of (contract, allowed_action_types)
        """
        # Evaluate contract
        contract = self.evaluator.evaluate(
            coherence_state=coherence_state,
            goal_state=goal_state,
            recent_blocked=self._recent_blocked,
        )

        # Update blocked tracking
        if not contract.eligible:
            self._blocked_count += 1
            self._recent_blocked = True
        else:
            self._blocked_count = 0
            self._recent_blocked = False

        # Filter allowed actions
        allowed_actions = []
        if action_types and contract.eligible:
            for action_type in action_types:
                allowed, _ = self.evaluator.evaluate_action(contract, action_type)
                if allowed:
                    allowed_actions.append(action_type)

        return contract, allowed_actions

    def reset(self) -> None:
        """Reset blocked state tracking."""
        self._recent_blocked = False
        self._blocked_count = 0

    def get_blocked_count(self) -> int:
        """Get consecutive blocked count."""
        return self._blocked_count


def create_default_evaluator() -> SafetyContractEvaluator:
    """Create evaluator with default thresholds."""
    return SafetyContractEvaluator(
        consistency_threshold=0.60,
        alignment_threshold=0.60,
        reversal_risk_threshold=0.40,
        stability_threshold=0.60,
    )


def create_strict_evaluator() -> SafetyContractEvaluator:
    """Create evaluator with strict thresholds."""
    return SafetyContractEvaluator(
        consistency_threshold=0.75,
        alignment_threshold=0.75,
        reversal_risk_threshold=0.25,
        stability_threshold=0.75,
    )


def create_permissive_evaluator() -> SafetyContractEvaluator:
    """Create evaluator with permissive thresholds."""
    return SafetyContractEvaluator(
        consistency_threshold=0.50,
        alignment_threshold=0.50,
        reversal_risk_threshold=0.50,
        stability_threshold=0.50,
    )
