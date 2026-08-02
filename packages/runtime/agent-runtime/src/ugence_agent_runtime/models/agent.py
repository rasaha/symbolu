"""Agent descriptor — a neutral, declarative identity for the actor a workflow runs
on behalf of.

The descriptor is coordination metadata only. It confers no authority and carries
no credentials. It exists so events, traces, and governance evaluations can be
correlated to a stable agent identity without the runtime knowing anything
product-specific about that agent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AgentDescriptor:
    agent_id: str
    kind: str = "generic"
    version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.agent_id or not isinstance(self.agent_id, str):
            raise ValueError("AgentDescriptor.agent_id required")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "kind": self.kind,
            "version": self.version,
            "metadata": dict(self.metadata),
        }
