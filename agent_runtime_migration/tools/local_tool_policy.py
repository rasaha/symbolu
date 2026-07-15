"""Local fast-path policy.

A tool may run locally (no CER) ONLY if the trusted registry classifies it
LOCAL_READ_ONLY AND marks it fast_path_permitted. Anything that actuates is
GOVERNED_CONSEQUENTIAL by registry classification and cannot use the fast path.
The model cannot reclassify a tool.
"""
from __future__ import annotations

from ..contracts.action import RiskClass
from ..contracts.errors import ToolPolicyError
from .registry import RegisteredTool


def permits_local_fast_path(tool: RegisteredTool) -> bool:
    return tool.risk_class is RiskClass.LOCAL_READ_ONLY and tool.fast_path_permitted


def assert_local_allowed(tool: RegisteredTool) -> None:
    if not permits_local_fast_path(tool):
        raise ToolPolicyError(
            f"tool {tool.name!r} ({tool.risk_class.value}) is not permitted on the local "
            "fast path; it must be governed via CER -> AI Control Plane")
