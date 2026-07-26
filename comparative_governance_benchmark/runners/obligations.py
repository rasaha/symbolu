"""Obligation state modeling + verification (benchmark-owned, provider-free).

Mirrors the frozen pilot's obligation semantics for cross-strategy fairness.
Obligation states are explicit and governance compliance is kept distinct from
execution success.
"""
from __future__ import annotations

from dataclasses import dataclass

_AUTO_SATISFIED = {"logging", "notification", "citation", "include_citation",
                   "include_uncertainty_disclosure", "uncertainty_disclosure",
                   "retain_source_attribution", "log_evidence_provenance", "evidence_retention"}
_HUMAN = {"human_review", "request_human_review", "human_approval", "post_execution_review"}


@dataclass(frozen=True)
class ObligationRecord:
    obligation_type: str
    value: str
    state: str


def _parse(obligations: tuple[str, ...]) -> list[tuple[str, str]]:
    out = []
    for o in obligations:
        body = o[4:] if o.startswith("ext:") else o
        t, v = (body.split("=", 1) if "=" in body else (body, ""))
        out.append((t, v))
    return out


def verify_obligations(obligations: tuple[str, ...], *, human_approval, waived=False
                       ) -> tuple[ObligationRecord, ...]:
    records: list[ObligationRecord] = []
    for otype, oval in _parse(obligations):
        if otype in _AUTO_SATISFIED:
            state = "SATISFIED"
        elif otype in _HUMAN:
            if waived:
                state = "WAIVED_BY_AUTHORITY"
            elif human_approval is True:
                state = "SATISFIED"
            elif human_approval is False:
                state = "FAILED"
            else:
                state = "PENDING"
        else:
            state = "PENDING"
        records.append(ObligationRecord(otype, oval, state))
    return tuple(records)


def compliance_verdict(obligations: tuple[ObligationRecord, ...], *,
                       reconciliation_ok: bool, dispatched: bool) -> str:
    if not dispatched:
        return "NOT_APPLICABLE"
    if any(o.state in ("FAILED", "PENDING", "EXPIRED") for o in obligations):
        return "NONCOMPLIANT"
    if not reconciliation_ok:
        return "NONCOMPLIANT"
    return "COMPLIANT"
