"""Model-driven planner. The model proposes tools+arguments; the runtime assigns the
trusted risk class and builds typed Actions. Deterministic given the model output.
"""
from __future__ import annotations
from typing import List, Optional

from ..contracts.goal import Goal
from ..contracts.plan import Plan
from ..model.interface import LanguageModel
from ..model.parsing import parse_plan_payload
from ..tools.registry import ToolRegistry

# FROZEN prompt template (preregistered). {objective} is the only variable.
DECOMPOSITION_TEMPLATE = (
    "You are a planning component. Decompose the objective into an ordered list of "
    "tool calls. Respond ONLY with JSON: "
    '{{"actions": [{{"tool": "<registered tool name>", "description": "<why>", '
    '"arguments": {{}}}}]}}. Do not include any risk, authorization, or eligibility '
    "fields; those are decided by the control plane, not you.\n\nObjective: {objective}"
)


class ModelPlanner:
    def __init__(self, model: LanguageModel, registry: ToolRegistry,
                 template: str = DECOMPOSITION_TEMPLATE):
        self._model = model
        self._registry = registry
        self._template = template
        self.last_ignored_fields: List[str] = []

    def plan(self, goal: Goal) -> Plan:
        prompt = self._template.format(objective=goal.objective)
        output = self._model.generate(prompt)
        actions, ignored = parse_plan_payload(output, goal_id=goal.goal_id, registry=self._registry)
        self.last_ignored_fields = ignored
        deps = {k: tuple(v) for k, v in goal.metadata.get("dependencies", {}).items()}
        return Plan(plan_id=f"plan:{goal.goal_id}", goal_id=goal.goal_id,
                    steps=actions, dependencies=deps)
