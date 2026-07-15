"""Deterministic goal decomposition.

A goal MAY carry an explicit plan (a list of Action objects) in
``goal.metadata['plan']`` — the runtime uses it directly (planning is runtime-owned
and pluggable). Otherwise the goal decomposes to a single local 'respond' action.
No LLM call here, so the default is fully deterministic and testable; an
LLM-driven planner can implement the same Planner interface later.
"""
from __future__ import annotations
from typing import List
from ..contracts.action import Action, RiskClass
from ..contracts.goal import Goal


def decompose(goal: Goal) -> List[Action]:
    plan = goal.metadata.get("plan")
    if plan:
        for a in plan:
            if not isinstance(a, Action):
                from ..contracts.errors import ContractError
                raise ContractError("goal.metadata['plan'] must contain Action objects")
        return list(plan)
    return [Action(action_id=f"{goal.goal_id}:respond", kind="respond",
                   tool_name="respond", risk_class=RiskClass.LOCAL_READ_ONLY,
                   arguments={"objective": goal.objective})]
