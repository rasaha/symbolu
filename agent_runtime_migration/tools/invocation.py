"""Local tool invocation (read-only fast path only)."""
from __future__ import annotations

from typing import Any, Dict
from .registry import RegisteredTool


def invoke_local(tool: RegisteredTool, arguments: Dict[str, Any]) -> Any:
    return tool.handler(arguments)
