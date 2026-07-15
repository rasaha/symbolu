"""Observation contract — what the runtime learns after an action runs.

Produced from a governed execution result (or a local fast-path result) and fed
back into memory and reflection. Observations never re-decide eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Observation:
    action_id: str
    outcome: str                        # "executed" | "blocked" | "held" | "pending" | "failed" | "local"
    output: Optional[Any] = None
    error: Optional[str] = None
    cer_digest: Optional[str] = None     # identity of the governed action, when applicable
    governance: Dict[str, Any] = field(default_factory=dict)  # AG/ACP/composed summary (read-only)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.outcome in ("executed", "local")
