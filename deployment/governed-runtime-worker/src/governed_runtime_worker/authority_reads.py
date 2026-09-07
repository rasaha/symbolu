"""The authority plane's reads (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §11 step 2, ruling
AP-5 ``READS_FIRST``).

    FOUR READS OVER THE DIRECTORY THIS WORKER ALREADY OWNS. NOTHING HERE WRITES.

The reads are the four AP-5 operations the contract in ``authority_plane.py`` names:
the grants one principal holds, the holders of one role in one scope, one committee's
report, and one grant's append-only event history. Each is answered from the
``SqliteAuthorityDirectory`` the composition opened, for this worker's own tenant and
at the injected clock's instant. No tenant, instant, credential or proof is taken from
the caller: a foreign tenant's grants are not expressible, and the proof header the
decision route reads is not read here.

**What the answer says about identity, honestly.** A read is not authenticated
(``read_authenticated: false``). What the answer carries is the identity proof the
deployment can give on a *decision*: ``IDP_AUTHENTICATED`` when an identity port is
composed, ``PRESENTED_UNPROVEN`` otherwise, beside the adapter's own
``issuer_validation`` label, which stays ``IN_PROCESS_ISSUER_ONLY`` until AI-C is
validated against a real issuer. A grant shown here is what an administrator loaded;
the directory's ADR says so, and so does every answer.

**What is not here.** No write. The four AP-3 operations stay unserved until the
identity gate is met, and ``tests/test_authority_plane_contract.py`` asserts that no
write path is served and no module of this worker names one outside the contract.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any, Callable, Optional

from ugence_approver_identity_jwt import ISSUER_VALIDATION
from ugence_authority_directory import (
    AuthorityDirectoryPort,
    CommitteeReport,
    GrantEvent,
    PrincipalRef,
    RoleGrant,
)

from .authority_plane import PLANE_OPERATIONS, PlaneOperation
from .version import MATURITY

__all__ = ["READ_OPERATIONS", "build_authority_reads", "IDP_AUTHENTICATED", "PRESENTED_UNPROVEN"]

#: The four reads, exactly as the contract names them; the router below is built from
#: this tuple so it cannot drift from the document a reader sees.
READ_OPERATIONS: tuple[PlaneOperation, ...] = tuple(op for op in PLANE_OPERATIONS if op.kind == "read")

IDP_AUTHENTICATED = "IDP_AUTHENTICATED"
PRESENTED_UNPROVEN = "PRESENTED_UNPROVEN"

#: A typed identifier: non-empty, NFC, no whitespace, bounded. Anything else is refused
#: before the directory is asked (FD-4: typed intake, never guessed at).
MAX_TOKEN = 256


def _is_typed(value: Any) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= MAX_TOKEN
            and value == value.strip() and not any(ch.isspace() for ch in value)
            and unicodedata.is_normalized("NFC", value))


def _principal_view(principal: PrincipalRef) -> dict:
    return {
        "principal_id": principal.principal_id,
        "principal_kind": principal.principal_kind.value,
        "display_ref": principal.display_ref,
        "quorum": principal.quorum,
    }


def _grant_view(grant: RoleGrant) -> dict:
    return grant.to_dict()


def _event_view(event: GrantEvent) -> dict:
    return event.to_dict()


def _committee_view(report: CommitteeReport, as_of: datetime) -> dict:
    members = [_grant_view(g) for g in report.members]
    return {
        "committee": _principal_view(report.committee),
        "role": report.role,
        "scope": report.scope,
        "quorum": report.quorum,
        "members": members,
        "member_count": len(members),
        "quorum_met_at_as_of": len(members) >= report.quorum,
        "as_of": as_of.isoformat(),
    }


def _op(operation_id: str) -> PlaneOperation:
    for op in READ_OPERATIONS:
        if op.operation_id == operation_id:
            return op
    raise KeyError(operation_id)


def build_authority_reads(
    directory: AuthorityDirectoryPort,
    *,
    tenant_id: str,
    clock: Callable[[], datetime],
    identity_port_configured: bool,
) -> Any:
    """A FastAPI router over one directory, for one tenant, at one clock."""
    from fastapi import APIRouter, Query
    from fastapi.responses import JSONResponse

    if not _is_typed(tenant_id):
        raise ValueError("tenant_id must be a typed token")
    router = APIRouter(tags=["authority"])
    decision_proof = IDP_AUTHENTICATED if identity_port_configured else PRESENTED_UNPROVEN

    def envelope(as_of: datetime, **payload: Any) -> dict:
        return {
            "result": "READ",
            "plane": "authority",
            "ruling": "AP-5",
            "tenant_id": tenant_id,
            "as_of": as_of.isoformat(),
            "read_authenticated": False,
            "decision_identity_proof": decision_proof,
            "issuer_validation": ISSUER_VALIDATION,
            "provenance": "what an administrator loaded; the directory attests nothing about whether it should exist",
            "maturity": MATURITY,
            **payload,
        }

    def refused(status: int, result: str, reason: str) -> Any:
        return JSONResponse(status_code=status, content={
            "result": result, "plane": "authority", "ruling": "AP-5", "reason": reason,
            "maturity": MATURITY})

    def untyped(name: str) -> Any:
        return refused(422, "REFUSED_UNTYPED", f"{name} must be a typed token: non-empty, NFC, "
                                                f"no whitespace, at most {MAX_TOKEN} characters")

    grants_op = _op("authority_list_grants")

    @router.get(grants_op.path, operation_id=grants_op.operation_id, summary=grants_op.summary)
    def list_grants(principal_id: str = Query(...)):
        if not _is_typed(principal_id):
            return untyped("principal_id")
        as_of = clock()
        grants = directory.grants_for(tenant_id=tenant_id, principal_id=principal_id, as_of=as_of)
        return envelope(as_of, principal_id=principal_id,
                        grants=[_grant_view(g) for g in grants], grant_count=len(grants))

    holders_op = _op("authority_list_holders")

    @router.get(holders_op.path, operation_id=holders_op.operation_id, summary=holders_op.summary)
    def list_holders(role: str = Query(...), scope: str = Query(...)):
        for name, value in (("role", role), ("scope", scope)):
            if not _is_typed(value):
                return untyped(name)
        as_of = clock()
        holders = directory.holders_of(tenant_id=tenant_id, role=role, scope=scope, as_of=as_of)
        return envelope(as_of, role=role, scope=scope,
                        holders=[_grant_view(g) for g in holders], holder_count=len(holders))

    committee_op = _op("authority_read_committee")

    @router.get(committee_op.path, operation_id=committee_op.operation_id, summary=committee_op.summary)
    def read_committee(committee_id: str, role: str = Query(...), scope: str = Query(...)):
        for name, value in (("committee_id", committee_id), ("role", role), ("scope", scope)):
            if not _is_typed(value):
                return untyped(name)
        as_of = clock()
        report: Optional[CommitteeReport] = directory.committee_report(
            tenant_id=tenant_id, committee_id=committee_id, role=role, scope=scope, as_of=as_of)
        if report is None:
            return refused(404, "NOT_FOUND",
                           f"no committee {committee_id!r} holds a grant of {role!r} in {scope!r} "
                           f"for this tenant at {as_of.isoformat()}")
        return envelope(as_of, committee_id=committee_id, report=_committee_view(report, as_of))

    events_op = _op("authority_read_grant_events")

    @router.get(events_op.path, operation_id=events_op.operation_id, summary=events_op.summary)
    def read_grant_events(grant_id: str):
        if not _is_typed(grant_id):
            return untyped("grant_id")
        as_of = clock()
        grant = directory.get_grant(grant_id)
        if grant is None or grant.tenant_id != tenant_id:
            # a foreign tenant's grant is not distinguishable from an unknown one, on purpose
            return refused(404, "NOT_FOUND", f"this tenant holds no grant {grant_id!r}")
        events = directory.grant_events(grant_id)
        return envelope(as_of, grant_id=grant_id, grant=_grant_view(grant),
                        events=[_event_view(e) for e in events], event_count=len(events))

    return router
