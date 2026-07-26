"""TAP provider observability — structured evaluation records.

Captured separately from DGM milestone/audit events. Records the provider
version, mapping version, engine mode, compatibility, TAP trace id, normalized
outcome, evidence count, evidence coverage, duration, error classification, and
result fingerprint. **No unrestricted evidence content and no secrets are ever
recorded** — only counts and coverage ratios.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TapInvocationRecord:
    provider_id: str
    provider_version: str
    mapping_version: str
    mode: str
    compatible: bool
    completed: bool
    outcome: str = ""
    trace_id: str = ""
    policy_version: str = ""
    evidence_count: int = 0
    evidence_coverage: Optional[float] = None
    duration_ms: Optional[float] = None
    fingerprint: str = ""
    error_class: Optional[str] = None
    failure_class: Optional[str] = None


class TapInvocationLog:
    def __init__(self) -> None:
        self._records: list[TapInvocationRecord] = []

    def append(self, record: TapInvocationRecord) -> None:
        self._records.append(record)

    def all(self) -> tuple[TapInvocationRecord, ...]:
        return tuple(self._records)


__all__ = ["TapInvocationRecord", "TapInvocationLog"]
