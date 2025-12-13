"""
PlannerGate: PO1 Constraint Enforcement
(PO1 = Observer–Observed Grounding, implemented as phase_minus_one)

Filters and blocks planner actions based on grounding constraints
established by PO1 analysis.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Gating Rules by Mode:
- REFLEXIVE (SELF observed):
  - ALLOW: CARE, GROUND, CLARIFY_SELF, REFLECT
  - FORBID: ANALYZE, EXPLAIN, DIAGNOSE, JUDGE, ASSERT_ABOUT_OTHERS

- RELATIONAL (OTHER observed):
  - ALLOW: ALIGN, ASK, REFLECT_BACK, DE_ESCALATE, CLARIFY_REFERENCE
  - FORBID: DIAGNOSE_OTHER, ASSERT_OTHER_STATE, LABEL, BLAME, EXPLAIN_CAUSES

- DETACHED (PHENOMENON observed):
  - ALLOW: EXPLAIN, ANALYZE, COMPARE, SUMMARIZE, INSTRUCT_GENERAL
  - FORBID: PERSONAL_DIAGNOSIS, ASSERT_USER_STATE

Global Constraints:
- If analysis_allowed == False: Strip ANALYZE/EXPLAIN from allowed set

Authority Model:
- PlannerGate receives authority from PO1 envelope
- Cannot override grounding decisions
- Reports violations for metrics but enforces constraints
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import (
    ClauseGroundingResult,
    GroundingCandidate,
    ObservationMode,
    OverallPolicy,
    PhaseMinusOneEnvelope,
)


class ActionClass(str, Enum):
    """
    Action classes that can be proposed by planners.

    Grouped by category for clarity.
    """
    # Care/Support actions (generally safe for REFLEXIVE)
    CARE = "CARE"
    GROUND = "GROUND"
    CLARIFY_SELF = "CLARIFY_SELF"
    REFLECT = "REFLECT"
    VALIDATE = "VALIDATE"

    # Relational actions (appropriate for RELATIONAL)
    ALIGN = "ALIGN"
    ASK = "ASK"
    REFLECT_BACK = "REFLECT_BACK"
    DE_ESCALATE = "DE_ESCALATE"
    CLARIFY_REFERENCE = "CLARIFY_REFERENCE"

    # Analytical actions (appropriate for DETACHED)
    EXPLAIN = "EXPLAIN"
    ANALYZE = "ANALYZE"
    COMPARE = "COMPARE"
    SUMMARIZE = "SUMMARIZE"
    INSTRUCT_GENERAL = "INSTRUCT_GENERAL"

    # Dangerous actions (often forbidden)
    DIAGNOSE = "DIAGNOSE"
    DIAGNOSE_OTHER = "DIAGNOSE_OTHER"
    JUDGE = "JUDGE"
    ASSERT_ABOUT_OTHERS = "ASSERT_ABOUT_OTHERS"
    ASSERT_OTHER_STATE = "ASSERT_OTHER_STATE"
    ASSERT_USER_STATE = "ASSERT_USER_STATE"
    LABEL = "LABEL"
    BLAME = "BLAME"
    EXPLAIN_CAUSES = "EXPLAIN_CAUSES"
    PERSONAL_DIAGNOSIS = "PERSONAL_DIAGNOSIS"

    # Special actions
    ASK_CLARIFY_REFERENCE = "ASK_CLARIFY_REFERENCE"  # For BLOCKED state


@dataclass
class GatedPlanStep:
    """
    A single step in a gated plan.

    Attributes:
        action: The action class for this step.
        target_clause_index: Which clause this step applies to.
        allowed: Whether this action was allowed through the gate.
        rejection_reason: If rejected, why.
        original_intent: Original planner intent if available.
    """
    action: ActionClass
    target_clause_index: int
    allowed: bool
    rejection_reason: Optional[str] = None
    original_intent: Optional[str] = None


@dataclass
class GatedPlanResult:
    """
    Result of applying PlannerGate to proposed actions.

    Attributes:
        selected_action_classes: Actions that passed through the gate.
        rejected_action_classes: Actions that were blocked with reasons.
        blocked: Whether the entire plan was blocked.
        blocked_reason: If blocked, why.
        plan_steps: Detailed steps with clause targeting.
        violations: List of violation records for metrics.
    """
    selected_action_classes: List[ActionClass]
    rejected_action_classes: Dict[ActionClass, str]  # action -> reason
    blocked: bool
    blocked_reason: Optional[str]
    plan_steps: List[GatedPlanStep]
    violations: List[Dict]  # For metrics logging


class PlannerGate:
    """
    Enforces PO1 grounding constraints on planner actions.

    Usage:
        gate = PlannerGate()
        result = gate.filter(envelope, proposed_actions)
        # result.selected_action_classes contains allowed actions
        # result.violations contains any constraint violations
    """

    # Action sets by mode
    REFLEXIVE_ALLOWED: Set[ActionClass] = {
        ActionClass.CARE,
        ActionClass.GROUND,
        ActionClass.CLARIFY_SELF,
        ActionClass.REFLECT,
        ActionClass.VALIDATE,
        ActionClass.ASK,
    }

    REFLEXIVE_FORBIDDEN: Set[ActionClass] = {
        ActionClass.ANALYZE,
        ActionClass.EXPLAIN,
        ActionClass.DIAGNOSE,
        ActionClass.DIAGNOSE_OTHER,
        ActionClass.JUDGE,
        ActionClass.ASSERT_ABOUT_OTHERS,
        ActionClass.ASSERT_OTHER_STATE,
        ActionClass.LABEL,
        ActionClass.BLAME,
        ActionClass.EXPLAIN_CAUSES,
        ActionClass.PERSONAL_DIAGNOSIS,
    }

    RELATIONAL_ALLOWED: Set[ActionClass] = {
        ActionClass.ALIGN,
        ActionClass.ASK,
        ActionClass.REFLECT_BACK,
        ActionClass.DE_ESCALATE,
        ActionClass.CLARIFY_REFERENCE,
        ActionClass.VALIDATE,
    }

    RELATIONAL_FORBIDDEN: Set[ActionClass] = {
        ActionClass.DIAGNOSE_OTHER,
        ActionClass.ASSERT_OTHER_STATE,
        ActionClass.LABEL,
        ActionClass.BLAME,
        ActionClass.EXPLAIN_CAUSES,
        ActionClass.ANALYZE,
        ActionClass.DIAGNOSE,
        ActionClass.PERSONAL_DIAGNOSIS,
    }

    DETACHED_ALLOWED: Set[ActionClass] = {
        ActionClass.EXPLAIN,
        ActionClass.ANALYZE,
        ActionClass.COMPARE,
        ActionClass.SUMMARIZE,
        ActionClass.INSTRUCT_GENERAL,
        ActionClass.ASK,
    }

    DETACHED_FORBIDDEN: Set[ActionClass] = {
        ActionClass.PERSONAL_DIAGNOSIS,
        ActionClass.ASSERT_USER_STATE,
        ActionClass.DIAGNOSE,
        ActionClass.DIAGNOSE_OTHER,
    }

    # Actions that require analysis_allowed == True
    ANALYSIS_DEPENDENT: Set[ActionClass] = {
        ActionClass.ANALYZE,
        ActionClass.EXPLAIN,
        ActionClass.EXPLAIN_CAUSES,
        ActionClass.DIAGNOSE,
        ActionClass.DIAGNOSE_OTHER,
        ActionClass.PERSONAL_DIAGNOSIS,
    }

    def __init__(self) -> None:
        """Initialize the planner gate."""
        self._violation_count = 0

    def filter(
        self,
        envelope: PhaseMinusOneEnvelope,
        proposed_actions: List[ActionClass],
    ) -> GatedPlanResult:
        """
        Filter proposed actions based on PO1 grounding constraints.

        Uses AND semantics (intersection safety):
        An action is allowed ONLY if it is safe for ALL grounded clauses.

        Authority flows downward; safety dominates permissiveness.

        Args:
            envelope: PO1 grounding envelope.
            proposed_actions: List of actions proposed by planner.

        Returns:
            GatedPlanResult with allowed/rejected actions.
        """
        # Handle BLOCKED state
        if envelope.is_blocked():
            return self._build_blocked_result(envelope)

        # Handle empty clauses edge case
        if not envelope.clauses:
            return GatedPlanResult(
                selected_action_classes=[],
                rejected_action_classes={a: "no_clauses" for a in proposed_actions},
                blocked=True,
                blocked_reason="no_clauses_to_evaluate",
                plan_steps=[],
                violations=[],
            )

        # Safety hardening: block if any clause has no selected grounding
        for clause in envelope.clauses:
            if clause.selected is None:
                return self._build_blocked_result(envelope)

        # Process each clause and determine allowed actions
        allowed_actions: List[ActionClass] = []
        rejected_actions: Dict[ActionClass, str] = {}
        plan_steps: List[GatedPlanStep] = []
        violations: List[Dict] = []

        # For each proposed action, check against ALL clauses (AND semantics)
        for action in proposed_actions:
            # Start as allowed; any rejection makes it rejected
            action_allowed = True
            rejection_reasons: List[str] = []
            rejecting_clause_indices: List[int] = []

            # Check ALL clauses - action must be safe for every clause
            for clause in envelope.clauses:
                clause_result = self._check_action_for_clause(
                    action, clause, envelope
                )
                if not clause_result["allowed"]:
                    action_allowed = False
                    rejection_reasons.append(
                        f"clause[{clause.clause_index}]:{clause_result['reason']}"
                    )
                    rejecting_clause_indices.append(clause.clause_index)

            if action_allowed:
                # Action is safe for ALL clauses
                allowed_actions.append(action)
                plan_steps.append(GatedPlanStep(
                    action=action,
                    target_clause_index=0,  # Safe for all, target first
                    allowed=True,
                ))
            else:
                # Action was rejected by at least one clause
                reason = "; ".join(rejection_reasons)
                rejected_actions[action] = reason
                plan_steps.append(GatedPlanStep(
                    action=action,
                    target_clause_index=rejecting_clause_indices[0] if rejecting_clause_indices else 0,
                    allowed=False,
                    rejection_reason=reason,
                ))
                violations.append({
                    "action": action.value,
                    "reason": reason,
                    "envelope_policy": envelope.overall_policy.value,
                    "rejecting_clauses": rejecting_clause_indices,
                })
                self._violation_count += 1

        return GatedPlanResult(
            selected_action_classes=allowed_actions,
            rejected_action_classes=rejected_actions,
            blocked=False,
            blocked_reason=None,
            plan_steps=plan_steps,
            violations=violations,
        )

    def _check_action_for_clause(
        self,
        action: ActionClass,
        clause: ClauseGroundingResult,
        envelope: PhaseMinusOneEnvelope,
    ) -> Dict:
        """
        Check if an action is allowed for a specific clause.

        Returns dict with "allowed" bool and "reason" if rejected.
        """
        if clause.selected is None:
            return {"allowed": False, "reason": "no_selected_grounding"}

        selected = clause.selected
        mode = selected.mode

        # Get allowed/forbidden sets for this mode
        if mode == ObservationMode.REFLEXIVE:
            allowed_set = self.REFLEXIVE_ALLOWED
            forbidden_set = self.REFLEXIVE_FORBIDDEN
        elif mode == ObservationMode.RELATIONAL:
            allowed_set = self.RELATIONAL_ALLOWED
            forbidden_set = self.RELATIONAL_FORBIDDEN
        else:  # DETACHED
            allowed_set = self.DETACHED_ALLOWED
            forbidden_set = self.DETACHED_FORBIDDEN

        # Check if action is explicitly forbidden
        if action in forbidden_set:
            return {
                "allowed": False,
                "reason": f"forbidden_for_{mode.value.lower()}_mode",
            }

        # Check analysis_allowed constraint
        if action in self.ANALYSIS_DEPENDENT and not selected.analysis_allowed:
            return {
                "allowed": False,
                "reason": "analysis_not_allowed",
            }

        # Check if action is explicitly allowed (strict allow-list)
        if action in allowed_set:
            return {"allowed": True, "reason": None}

        # Strict allow-list: reject if not explicitly allowed
        return {
            "allowed": False,
            "reason": f"not_allowed_for_{mode.value.lower()}_mode",
        }

    def _build_blocked_result(
        self, envelope: PhaseMinusOneEnvelope
    ) -> GatedPlanResult:
        """
        Build result for BLOCKED envelope state.

        Only allows ASK_CLARIFY_REFERENCE action.
        """
        return GatedPlanResult(
            selected_action_classes=[ActionClass.ASK_CLARIFY_REFERENCE],
            rejected_action_classes={},
            blocked=True,
            blocked_reason="envelope_blocked_requires_clarification",
            plan_steps=[GatedPlanStep(
                action=ActionClass.ASK_CLARIFY_REFERENCE,
                target_clause_index=0,
                allowed=True,
            )],
            violations=[],
        )

    def get_allowed_actions_for_mode(
        self,
        mode: ObservationMode,
        analysis_allowed: bool,
    ) -> Set[ActionClass]:
        """
        Get the set of allowed actions for a given mode.

        Useful for introspection and testing.
        """
        if mode == ObservationMode.REFLEXIVE:
            base_set = self.REFLEXIVE_ALLOWED.copy()
        elif mode == ObservationMode.RELATIONAL:
            base_set = self.RELATIONAL_ALLOWED.copy()
        else:
            base_set = self.DETACHED_ALLOWED.copy()

        if not analysis_allowed:
            base_set -= self.ANALYSIS_DEPENDENT

        return base_set

    def get_violation_count(self) -> int:
        """Get total violation count for metrics."""
        return self._violation_count

    def reset_violation_count(self) -> None:
        """Reset violation counter."""
        self._violation_count = 0


# Public exports
__all__ = ["PlannerGate", "GatedPlanResult", "ActionClass", "GatedPlanStep"]
