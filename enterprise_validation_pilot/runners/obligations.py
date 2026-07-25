"""Obligation state modeling + verification (Task 108).

Obligations are tracked with explicit states (PENDING / SATISFIED / FAILED /
WAIVED_BY_AUTHORITY / EXPIRED) and verified independently of execution success.
An action may execute successfully while remaining governance-noncompliant — this
module keeps those outcomes distinct.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..schemas.taxonomy import ComplianceVerdict, ObligationState


@dataclass(frozen=True)
class ObligationRecord:
    obligation_type: str
    value: str
    state: str


def _parse(obligations: tuple[str, ...]) -> list[tuple[str, str]]:
    out = []
    for o in obligations:
        body = o[4:] if o.startswith("ext:") else o
        if "=" in body:
            t, v = body.split("=", 1)
        else:
            t, v = body, ""
        out.append((t, v))
    return out


#: obligations the offline pilot satisfies automatically (system-fulfilled)
_AUTO_SATISFIED = {"logging", "notification", "citation", "include_citation",
                   "include_uncertainty_disclosure", "uncertainty_disclosure",
                   "retain_source_attribution", "log_evidence_provenance",
                   "evidence_retention"}
#: obligations requiring explicit human action
_HUMAN = {"human_review", "request_human_review", "human_approval", "post_execution_review"}


def verify_obligations(obligations: tuple[str, ...], *,
                       human_approval: bool | None,
                       waived: bool = False) -> tuple[ObligationRecord, ...]:
    """Resolve each obligation to a terminal state.

    ``human_approval`` is None when no human-review fixture applied (obligation
    stays PENDING/FAILED — never silently satisfied), True/False when a human
    explicitly approved/declined.
    """
    records: list[ObligationRecord] = []
    for otype, oval in _parse(obligations):
        if otype in _AUTO_SATISFIED:
            state = ObligationState.SATISFIED.value
        elif otype in _HUMAN:
            if waived:
                state = ObligationState.WAIVED_BY_AUTHORITY.value
            elif human_approval is True:
                state = ObligationState.SATISFIED.value
            elif human_approval is False:
                state = ObligationState.FAILED.value
            else:
                state = ObligationState.PENDING.value
        else:
            # unknown obligation type is never silently satisfied
            state = ObligationState.PENDING.value
        records.append(ObligationRecord(otype, oval, state))
    return tuple(records)


def compliance_verdict(obligations: tuple[ObligationRecord, ...], *,
                       reconciliation_ok: bool, dispatched: bool) -> str:
    """Governance compliance is distinct from execution success."""
    if not dispatched:
        return ComplianceVerdict.NOT_APPLICABLE.value
    if any(o.state in (ObligationState.FAILED.value, ObligationState.PENDING.value,
                       ObligationState.EXPIRED.value) for o in obligations):
        return ComplianceVerdict.NONCOMPLIANT.value
    if not reconciliation_ok:
        return ComplianceVerdict.NONCOMPLIANT.value
    return ComplianceVerdict.COMPLIANT.value
