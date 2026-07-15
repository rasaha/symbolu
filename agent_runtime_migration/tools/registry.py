"""Trusted tool registry.

The risk class of a tool is set HERE, at registration, by a trusted operator — never
by the model. A tool is either LOCAL_READ_ONLY (policy-permitted local fast path, no
consequential actuation) or GOVERNED_CONSEQUENTIAL (must pass through CER -> AI
Control Plane -> governed executor). Governed tools declare their CER profile.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from ..contracts.action import RiskClass
from ..contracts.errors import ToolPolicyError


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    handler: Callable[[Dict[str, Any]], Any]
    risk_class: RiskClass
    profile: Optional[str] = None      # required for GOVERNED_CONSEQUENTIAL
    fast_path_permitted: bool = False  # only meaningful for LOCAL_READ_ONLY

    def __post_init__(self) -> None:
        if self.risk_class is RiskClass.GOVERNED_CONSEQUENTIAL and not self.profile:
            raise ToolPolicyError(f"governed tool {self.name!r} must declare a CER profile")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}

    def register(self, name: str, handler, risk_class: RiskClass, *,
                 profile: Optional[str] = None, fast_path_permitted: bool = False) -> None:
        if not isinstance(risk_class, RiskClass):
            raise ToolPolicyError("risk_class must be a trusted RiskClass, not model-declared")
        self._tools[name] = RegisteredTool(name=name, handler=handler, risk_class=risk_class,
                                           profile=profile, fast_path_permitted=fast_path_permitted)

    def get(self, name: str) -> RegisteredTool:
        if name not in self._tools:
            raise ToolPolicyError(f"unknown tool {name!r} (not in trusted registry)")
        return self._tools[name]

    def risk_class(self, name: str) -> RiskClass:
        return self.get(name).risk_class
