"""Tool selection — resolve an Action to a registered tool (runtime-owned).

Fail closed if the action's declared risk class disagrees with the TRUSTED registry
classification: the registry always wins."""
from __future__ import annotations

from ..contracts.action import Action
from ..contracts.errors import GovernanceBoundaryError
from .registry import RegisteredTool, ToolRegistry


def resolve(action: Action, registry: ToolRegistry) -> RegisteredTool:
    tool = registry.get(action.tool_name)
    if tool.risk_class is not action.risk_class:
        raise GovernanceBoundaryError(
            f"action risk_class {action.risk_class.value} != trusted registry "
            f"{tool.risk_class.value} for tool {action.tool_name!r}; fail closed "
            "(the model cannot reclassify a tool)")
    return tool
