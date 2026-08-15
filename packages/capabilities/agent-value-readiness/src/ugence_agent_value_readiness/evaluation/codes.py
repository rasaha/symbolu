"""Stable rule / reason / advisory / condition-decision codes (GV-3R-b).

Every code is a stable token intended to survive across versions: consumers may
branch on them, so values are never repurposed. Codes are emitted in **enum
declaration order**, never in input order, so an identical case always produces
an identical ordered code tuple.

None of these codes asserts that anything was verified. They describe what the
evaluator did with **structurally supplied** artifacts.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "EVALUATOR_ID",
    "EVALUATOR_FORMULA_VERSION",
    "ReadinessRuleId",
    "ReadinessReasonCode",
    "ReadinessAdvisoryCode",
    "ConditionDecisionCode",
]

#: Identity of the single canonical evaluator entry point.
EVALUATOR_ID = "ugence.agent-value-readiness.readiness-determination-evaluator"

#: Version of the ratified determination rule set implemented here. Bumped only
#: when the selection algorithm itself changes.
EVALUATOR_FORMULA_VERSION = "GV-3R-b.1"


class ReadinessRuleId(str, Enum):
    """The single precedence rule that selected the classification.

    Exactly one rule is selected per evaluation, in this declaration order —
    the first matching rule wins and is recorded on the trace.
    """

    #: Any applicable mandatory gate FAIL. Dominates every other consideration
    #: (ADR §8, D-6): no condition, composite, or indicator strength overrides it.
    MANDATORY_FAIL = "GV3RB_R1_MANDATORY_FAIL"
    #: A structural assessability gap (context/policy binding, missing required
    #: gate result, missing indicator family, internally inconsistent input).
    ASSESSABILITY_GAP = "GV3RB_R2_ASSESSABILITY_GAP"
    #: No mandatory FAIL, but an applicable mandatory gate is INDETERMINATE.
    MANDATORY_INDETERMINATE = "GV3RB_R3_MANDATORY_INDETERMINATE"
    #: An unresolved applicable conditional concern the policy does not mark
    #: ``conditionally_compensable``.
    CONDITIONAL_NOT_COMPENSABLE = "GV3RB_R4_CONDITIONAL_NOT_COMPENSABLE"
    #: A compensable unresolved concern with no active covering ConditionSet.
    CONDITIONAL_UNCOVERED = "GV3RB_R5_CONDITIONAL_UNCOVERED"
    #: PILOT target, all applicable mandatory gates PASS, every unresolved
    #: conditional concern compensable and actively covered.
    PILOT_READY = "GV3RB_R6_PILOT_READY"
    #: PRODUCTION target with unresolved conditional concerns fully covered.
    READY_WITH_CONDITIONS = "GV3RB_R7_READY_WITH_CONDITIONS"
    #: PRODUCTION target with nothing unresolved and no open active condition.
    DEPLOYMENT_READY = "GV3RB_R8_DEPLOYMENT_READY"


class ReadinessReasonCode(str, Enum):
    """Why the selected rule fired. Emitted in declaration order."""

    # -- assessability gaps ------------------------------------------------- #
    #: The AssessmentContext binds no ReadinessPolicy reference at all.
    READINESS_POLICY_NOT_BOUND_TO_CONTEXT = "GV3RB_READINESS_POLICY_NOT_BOUND_TO_CONTEXT"
    #: The context's bound readiness reference is not the supplied policy.
    READINESS_POLICY_REF_CONTEXT_MISMATCH = "GV3RB_READINESS_POLICY_REF_CONTEXT_MISMATCH"
    #: The ReadinessPolicy does not govern the requested target.
    REQUESTED_TARGET_NOT_GOVERNED_BY_POLICY = "GV3RB_REQUESTED_TARGET_NOT_GOVERNED_BY_POLICY"
    #: No IntelligenceFitnessResult applicable to the requested target.
    INTELLIGENCE_RESULT_MISSING = "GV3RB_INTELLIGENCE_RESULT_MISSING"
    #: No CapabilityReadinessResult applicable to the requested target.
    CAPABILITY_RESULT_MISSING = "GV3RB_CAPABILITY_RESULT_MISSING"
    #: No AdoptionReadinessResult applicable to the requested target.
    ADOPTION_RESULT_MISSING = "GV3RB_ADOPTION_RESULT_MISSING"
    #: An applicable MANDATORY/CONDITIONAL policy gate has no supplied result.
    #: A missing gate is never treated as PASS.
    APPLICABLE_GATE_RESULT_MISSING = "GV3RB_APPLICABLE_GATE_RESULT_MISSING"
    #: An active condition names an applicable gate that currently PASSes — an
    #: open control implies an unresolved concern, so the input set contradicts
    #: itself.
    ACTIVE_CONDITION_WITHOUT_UNRESOLVED_CONCERN = (
        "GV3RB_ACTIVE_CONDITION_WITHOUT_UNRESOLVED_CONCERN"
    )
    #: No mandatory FAIL, but an applicable mandatory gate is INDETERMINATE.
    MANDATORY_GATE_INDETERMINATE = "GV3RB_MANDATORY_GATE_INDETERMINATE"

    # -- negative outcomes -------------------------------------------------- #
    MANDATORY_GATE_FAILED = "GV3RB_MANDATORY_GATE_FAILED"
    CONDITIONAL_CONCERN_NOT_COMPENSABLE = "GV3RB_CONDITIONAL_CONCERN_NOT_COMPENSABLE"
    CONDITIONAL_CONCERN_WITHOUT_ACTIVE_COVERAGE = (
        "GV3RB_CONDITIONAL_CONCERN_WITHOUT_ACTIVE_COVERAGE"
    )

    # -- positive outcomes -------------------------------------------------- #
    ALL_APPLICABLE_MANDATORY_GATES_PASSED = "GV3RB_ALL_APPLICABLE_MANDATORY_GATES_PASSED"
    CONDITIONAL_CONCERNS_COVERED_BY_ACTIVE_CONDITIONS = (
        "GV3RB_CONDITIONAL_CONCERNS_COVERED_BY_ACTIVE_CONDITIONS"
    )
    NO_UNRESOLVED_APPLICABLE_CONCERN = "GV3RB_NO_UNRESOLVED_APPLICABLE_CONCERN"
    #: PILOT_READY operates under bounded pilot scope/exposure/duration/monitoring
    #: limits; the enum has no separate PILOT_READY_WITH_CONDITIONS tier, so any
    #: accepted conditions are attached to the PILOT_READY determination.
    PILOT_SCOPE_IS_BOUNDED = "GV3RB_PILOT_SCOPE_IS_BOUNDED"


class ReadinessAdvisoryCode(str, Enum):
    """Standing honesty advisories carried by every evaluation result.

    These state what the evaluator did **not** do. They are emitted in
    declaration order and are never suppressed by a high readiness tier.
    """

    #: This determination is advisory. It is not an authorization to deploy.
    ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION = (
        "GV3RB_ADV_ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION"
    )
    #: The ReadinessPolicy and its gates are caller-supplied; their authenticity,
    #: approval, issuance and revocation are not verified here.
    POLICY_AUTHENTICITY_NOT_VERIFIED = "GV3RB_ADV_POLICY_AUTHENTICITY_NOT_VERIFIED"
    #: Every GateStatus was supplied by an upstream evaluator. This evaluator
    #: performs no evidence admission, benchmark resolution, or metric-to-threshold
    #: comparison, so a PASS is not an independently verified PASS.
    GATE_STATUS_STRUCTURALLY_SUPPLIED = "GV3RB_ADV_GATE_STATUS_STRUCTURALLY_SUPPLIED"
    #: Every MetricClaim keeps the exact evidence axes it arrived with; the
    #: evaluator never upgrades REPORTED/UNATTESTED/NOT_ATTRIBUTED/UNVERIFIED.
    EVIDENCE_CLASSIFICATION_PRESERVED = "GV3RB_ADV_EVIDENCE_CLASSIFICATION_PRESERVED"
    #: Readiness is a **leading indicator only**. This result carries no money,
    #: cost, benefit, return-on-investment or forecast, and must never be
    #: converted into one. (The code value deliberately avoids financial
    #: vocabulary so the package's anti-gaming scan stays strict.)
    READINESS_IS_LEADING_INDICATOR_ONLY = "GV3RB_ADV_READINESS_IS_LEADING_INDICATOR_ONLY"
    #: An APPROVED_ACTIVE ConditionSet remains a caller-asserted label; no real
    #: approving authority was resolved or validated.
    CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED = (
        "GV3RB_ADV_CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED"
    )
    #: ConditionSet carries no tenant/subject/context fields on the merged
    #: contract, so its scope was NOT matched against the assessed tenant or
    #: subject — only ``scope_exposure_limit`` presence is structurally required.
    CONDITION_SCOPE_NOT_TENANT_BOUND = "GV3RB_ADV_CONDITION_SCOPE_NOT_TENANT_BOUND"
    #: An AdvisoryComposite was supplied. It was validated and carried through
    #: unchanged and played no part in selecting the tier.
    COMPOSITE_CARRIED_NOT_USED_IN_SELECTION = (
        "GV3RB_ADV_COMPOSITE_CARRIED_NOT_USED_IN_SELECTION"
    )


class ConditionDecisionCode(str, Enum):
    """Why one supplied ``ConditionSet`` was accepted or rejected as coverage."""

    #: APPROVED_ACTIVE, active at evaluation_time, and naming an applicable
    #: unresolved conditional concern the policy marks conditionally compensable.
    ACCEPTED_ACTIVE_COVERAGE = "GV3RB_COND_ACCEPTED_ACTIVE_COVERAGE"
    STATUS_PROPOSED = "GV3RB_COND_STATUS_PROPOSED"
    STATUS_EXPIRED = "GV3RB_COND_STATUS_EXPIRED"
    STATUS_REVOKED = "GV3RB_COND_STATUS_REVOKED"
    #: SATISFIED is historical: it is never active coverage.
    STATUS_SATISFIED_HISTORICAL = "GV3RB_COND_STATUS_SATISFIED_HISTORICAL"
    #: effective_from is after evaluation_time.
    NOT_YET_EFFECTIVE = "GV3RB_COND_NOT_YET_EFFECTIVE"
    #: evaluation_time is at or after effective_to (half-open interval).
    WINDOW_ENDED = "GV3RB_COND_WINDOW_ENDED"
    #: evaluation_time is at or after expiry (half-open interval).
    EXPIRED_AT_EVALUATION_TIME = "GV3RB_COND_EXPIRED_AT_EVALUATION_TIME"
    #: The named source reference is not a gate of the supplied ReadinessPolicy.
    CONCERN_NOT_A_POLICY_GATE = "GV3RB_COND_CONCERN_NOT_A_POLICY_GATE"
    #: The named gate is not applicable to the requested target (diagnostic).
    CONCERN_NOT_APPLICABLE_TO_TARGET = "GV3RB_COND_CONCERN_NOT_APPLICABLE_TO_TARGET"
    #: The named gate is not a CONDITIONAL gate — a mandatory concern is never
    #: eligible for a compensating control (D-6).
    CONCERN_NOT_CONDITIONAL = "GV3RB_COND_CONCERN_NOT_CONDITIONAL"
    #: The named conditional gate is not unresolved (it PASSes, or no result was
    #: supplied), so there is nothing to compensate.
    CONCERN_NOT_UNRESOLVED = "GV3RB_COND_CONCERN_NOT_UNRESOLVED"
    #: The policy does not set ``conditionally_compensable=True`` on that gate.
    CONCERN_NOT_COMPENSABLE = "GV3RB_COND_CONCERN_NOT_COMPENSABLE"
