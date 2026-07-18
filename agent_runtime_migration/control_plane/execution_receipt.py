"""Execution receipt — the control-plane-issued reference the runtime accepts.

The runtime accepts an execution reference ONLY from the control-plane decision.
It never mints one. A receipt with no reference means "not eligible" and the tool
must not run.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ExecutionReceipt:
    cer_digest: str
    combined_outcome: Optional[str]
    execution_reference: Optional[str]

    @property
    def permits_execution(self) -> bool:
        return self.combined_outcome == "PROCEED" and bool(self.execution_reference)

    @classmethod
    def from_decision(cls, decision) -> "ExecutionReceipt":
        return cls(cer_digest=decision.cer_digest,
                   combined_outcome=decision.composed_eligibility,
                   execution_reference=decision.execution_reference)
