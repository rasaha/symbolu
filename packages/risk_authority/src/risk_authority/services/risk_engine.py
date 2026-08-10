"""Risk Decision Engine — an evaluator, not the binding authority (spec §8).

The engine produces a recommendation, the required controls, the failed
controls, conditions and an explanation trace. It never issues runtime
authority — that is Decision Authority's job (user brief §5, "Evaluator ≠
Ruler"). Its logic is non-compensatory and fail-closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..domain.controls import ControlResult, unsatisfied_controls
from ..domain.enums import ControlStatus, RiskRecommendation, RuleEffect
from ..domain.risk_case import RiskDecisionCase
from ..domain.workflow_ir import WorkflowIR
from .control_resolver import applicable_rules, resolve_required_controls

__all__ = ["RiskEvaluation", "RiskEngine"]


@dataclass(frozen=True)
class RiskEvaluation:
    """The advisory output of the Risk Engine."""

    recommendation: RiskRecommendation
    applicable_rules: tuple[str, ...]
    required_controls: tuple[str, ...]
    failed_controls: tuple[tuple[str, ControlStatus], ...]
    conditions: tuple[str, ...]
    trace: tuple[str, ...]
    workflow_ir_digest: str = ""


class RiskEngine:
    """Evaluate a case against WorkflowIR and current control state."""

    def evaluate(
        self,
        *,
        workflow_ir: WorkflowIR,
        case: RiskDecisionCase,
        controls: tuple[ControlResult, ...],
        now: datetime,
        conditions: tuple[str, ...] = (),
    ) -> RiskEvaluation:
        context = case.evaluation_context()
        rules = applicable_rules(workflow_ir, context)
        required = resolve_required_controls(workflow_ir, context)
        failed = unsatisfied_controls(required, controls, now)

        trace: list[str] = [
            f"workflow={workflow_ir.workflow_ir_id}@{workflow_ir.version}",
            f"applicable_rules={[r.rule_id for r in rules]}",
            f"required_controls={list(required)}",
        ]

        # Any rule whose effect denies-unless-all governs the strongest posture.
        deny_unless_all = any(r.effect is RuleEffect.DENY_UNLESS_ALL for r in rules)

        if failed:
            trace.append(
                "failed_controls="
                + str([(cid, st.value) for cid, st in failed])
            )
            # Non-compensatory: a single unsatisfied required control governs.
            # Hard failures (FAIL) always deny; ambiguity (MISSING/STALE/UNKNOWN)
            # denies under DENY_UNLESS_ALL and escalates otherwise (fail closed,
            # never coerced to PASS).
            has_hard_fail = any(st is ControlStatus.FAIL for _, st in failed)
            if has_hard_fail or deny_unless_all:
                recommendation = RiskRecommendation.DENY
            else:
                recommendation = RiskRecommendation.ESCALATE
            trace.append(f"recommendation={recommendation.value}")
            return RiskEvaluation(
                recommendation=recommendation,
                applicable_rules=tuple(r.rule_id for r in rules),
                required_controls=required,
                failed_controls=failed,
                conditions=conditions,
                trace=tuple(trace),
                workflow_ir_digest=workflow_ir.digest,
            )

        # All required controls satisfied.
        if conditions:
            recommendation = RiskRecommendation.ALLOW_WITH_CONDITIONS
        else:
            recommendation = RiskRecommendation.ALLOW
        trace.append(f"recommendation={recommendation.value}")
        return RiskEvaluation(
            recommendation=recommendation,
            applicable_rules=tuple(r.rule_id for r in rules),
            required_controls=required,
            failed_controls=(),
            conditions=conditions,
            trace=tuple(trace),
            workflow_ir_digest=workflow_ir.digest,
        )
