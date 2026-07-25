"""ActionGate provider observability — structured invocation records.

Richer than the framework's generic record: captures the provider version, the
mapping version, engine mode, compatibility, latency bucket, outcome, error
classification, and fallback. Distinct from DGM kernel audit events. **No
secrets or vendor payloads are recorded.**
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ActionGateInvocationRecord:
    provider_id: str
    provider_version: str
    mapping_version: str
    mode: str
    compatible: bool
    completed: bool
    outcome: str = ""
    trace_id: str = ""
    policy_version: str = ""
    error_class: Optional[str] = None
    failure_class: Optional[str] = None
    fallback_provider_id: str = ""


class ActionGateInvocationLog:
    def __init__(self) -> None:
        self._records: list[ActionGateInvocationRecord] = []

    def append(self, record: ActionGateInvocationRecord) -> None:
        self._records.append(record)

    def all(self) -> tuple[ActionGateInvocationRecord, ...]:
        return tuple(self._records)
