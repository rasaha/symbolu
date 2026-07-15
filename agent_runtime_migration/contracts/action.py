"""Action contract — a single planned step the runtime may propose.

RiskClass is authoritative from a TRUSTED source (tool registry / policy), never
model-declared. GOVERNED_CONSEQUENTIAL actions MUST go through CER -> AI Control
Plane -> governed executor. LOCAL_READ_ONLY actions MAY use a policy-permitted
local fast path (no consequential actuation).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from .errors import ContractError


class RiskClass(str, Enum):
    LOCAL_READ_ONLY = "LOCAL_READ_ONLY"        # policy-permitted local fast path (no CER)
    GOVERNED_CONSEQUENTIAL = "GOVERNED_CONSEQUENTIAL"  # must pass through the control plane


@dataclass(frozen=True)
class Action:
    action_id: str
    kind: str                      # semantic action kind, e.g. "retrieve", "kubernetes.scale"
    tool_name: str                 # the concrete tool to invoke
    risk_class: RiskClass
    arguments: Dict[str, Any] = field(default_factory=dict)
    profile: Optional[str] = None  # CER profile id for governed actions (e.g. database.mutation.v1)
    target: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action_id or not isinstance(self.action_id, str):
            raise ContractError("Action.action_id required")
        if not self.tool_name:
            raise ContractError("Action.tool_name required")
        if not isinstance(self.risk_class, RiskClass):
            raise ContractError("Action.risk_class must be a RiskClass (trusted, not model-declared)")
        if self.risk_class is RiskClass.GOVERNED_CONSEQUENTIAL and not self.profile:
            raise ContractError("governed consequential action requires a CER profile")

    @property
    def is_governed(self) -> bool:
        return self.risk_class is RiskClass.GOVERNED_CONSEQUENTIAL
