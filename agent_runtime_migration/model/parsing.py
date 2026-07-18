"""Parse model output into typed runtime contracts. Fail closed.

The model proposes an ``actions`` array of {tool, description, arguments}. The
runtime does NOT take a risk class from the model — the tool's risk class comes from
the trusted registry. Malformed or incomplete output raises ``ModelParseError``; an
unknown tool raises ``ToolPolicyError``; a model-supplied risk field is ignored (and
recorded).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from ..contracts.action import Action, RiskClass
from ..contracts.errors import ContractError
from ..tools.registry import ToolRegistry

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_OBJ = re.compile(r"\{.*\}", re.DOTALL)

# model-supplied fields that are IGNORED (governance is not the model's to set)
_IGNORED_MODEL_FIELDS = ("risk", "risk_class", "risk_level", "authorized", "allow",
                         "deny", "eligible", "execution_reference")


class ModelParseError(ContractError):
    """Model output could not be parsed into a valid plan (fail closed)."""


def _extract_json(text: str) -> Dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise ModelParseError("empty model output")
    m = _FENCE.search(text) or _OBJ.search(text)
    candidate = m.group(1) if (m and m.re is _FENCE) else (m.group(0) if m else text)
    try:
        obj = json.loads(candidate)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ModelParseError(f"model output is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ModelParseError("model output JSON must be an object")
    return obj


def parse_plan_payload(model_output: str, *, goal_id: str,
                       registry: ToolRegistry) -> Tuple[List[Action], List[str]]:
    """Return (actions, ignored_field_notes). Fail closed on any problem.

    Risk class + profile are looked up from the TRUSTED registry, never taken from
    the model. Unknown tools fail closed via the registry.
    """
    obj = _extract_json(model_output)
    raw_actions = obj.get("actions")
    if not isinstance(raw_actions, list) or not raw_actions:
        raise ModelParseError("model output missing a non-empty 'actions' array")

    ignored: List[str] = []
    actions: List[Action] = []
    for i, ra in enumerate(raw_actions):
        if not isinstance(ra, dict):
            raise ModelParseError(f"action[{i}] must be an object")
        tool = ra.get("tool") or ra.get("tool_name")
        if not isinstance(tool, str) or not tool:
            raise ModelParseError(f"action[{i}] missing 'tool'")
        for f in _IGNORED_MODEL_FIELDS:
            if f in ra:
                ignored.append(f"action[{i}].{f}")
        # TRUSTED classification (registry wins; model cannot set risk):
        reg_tool = registry.get(tool)                 # unknown tool -> ToolPolicyError (fail closed)
        risk_class = reg_tool.risk_class
        arguments = ra.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ModelParseError(f"action[{i}].arguments must be an object")
        profile = reg_tool.profile if risk_class is RiskClass.GOVERNED_CONSEQUENTIAL else None
        actions.append(Action(
            action_id=f"{goal_id}:{i}", kind=tool, tool_name=tool,
            risk_class=risk_class, profile=profile, arguments=dict(arguments),
            metadata={"description": ra.get("description", "")}))
    return actions, ignored
