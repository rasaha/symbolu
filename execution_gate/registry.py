"""Executable Model Registry (see EXECUTABLE_REGISTRY_SCHEMA.md).

Distinguishes declared / enumerated / authenticated / execution-verified / currently-eligible
status, with execution-verification lineage and TTLs. Never marks a model
execution-verified from enumeration alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from gate import ExecutionGate
from model import Candidate, Request
from reason_codes import ReasonCode
from states import EligibilityDecision


class ExecStatus(str, Enum):
    DECLARED = "declared"              # exists in docs/spec
    ENUMERATED = "enumerated"          # returned by provider model-list
    AUTHENTICATED = "authenticated"    # provider accepted our credential
    EXECUTION_VERIFIED = "execution_verified"  # a real inference succeeded
    DISABLED = "disabled"


@dataclass
class ModelRecord:
    internal_id: str
    candidate: Candidate                    # serving provider, developer, family, exact id, declared caps, prices
    exec_status: ExecStatus = ExecStatus.DECLARED
    last_success_ts: Optional[float] = None
    last_failure_ts: Optional[float] = None
    last_failure_reason: Optional[ReasonCode] = None
    billing_tier: str = "unknown"           # 'paid' | 'free' | 'unknown'
    quota_state: str = "unknown"
    observed_latency_ms: Optional[float] = None
    observed_reliability: Optional[float] = None
    evidence_ttl_s: float = 900.0
    enabled: bool = True

    def mark_verified(self, now: float):
        self.exec_status = ExecStatus.EXECUTION_VERIFIED
        self.last_success_ts = now

    def mark_failure(self, now: float, reason: ReasonCode):
        self.last_failure_ts = now
        self.last_failure_reason = reason


class ExecutableRegistry:
    def __init__(self, gate: Optional[ExecutionGate] = None):
        self.gate = gate or ExecutionGate()
        self.records: Dict[str, ModelRecord] = {}

    def upsert(self, rec: ModelRecord):
        self.records[rec.internal_id] = rec

    def evaluate(self, req: Request, now: float
                 ) -> Tuple[List[Tuple[ModelRecord, EligibilityDecision]],
                            List[Tuple[ModelRecord, EligibilityDecision]]]:
        """Run the gate over all enabled records. Returns (selectable, excluded)."""
        selectable, excluded = [], []
        for rec in self.records.values():
            if not rec.enabled:
                continue
            decision = self.gate.evaluate(rec.candidate, req, now)
            (selectable if decision.selectable else excluded).append((rec, decision))
        return selectable, excluded
