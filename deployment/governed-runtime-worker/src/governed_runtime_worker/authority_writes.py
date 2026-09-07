"""The authority plane's two directory writes (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §16,
rulings AW-2 to AW-5, under AP-3's invariant; §18, AW-1 reversed).

    TWO WRITES OVER THE DIRECTORY THIS WORKER ALREADY OWNS, EACH BEHIND THE IDENTITY GATE.
    NOTHING HERE IS RECORDED WITHOUT AN IDP_AUTHENTICATED HUMAN SUBJECT OF THIS TENANT.
    NOTHING HERE IS SERVED UNTIL THE CONTRACT NAMES IT (AP-3 CONTROLLING).

The writes are the two AW-2 operations: load one time-bounded role grant, and revoke
one grant. Each acts on the ``SqliteAuthorityDirectory`` the composition opened, for
this worker's own tenant, at the injected clock. The router built here registers only
the writes ``authority_plane.SERVED_WRITES`` names, which under AP-3 is none until the
owner records the adapter's validation against a real enterprise issuer; the composed
worker therefore answers a write path with the framework's 405 (a path a read shares)
or 404. Tests exercise the implementation by passing ``serve=IMPLEMENTED_WRITES``
explicitly: that is implementation and conformance evidence against the in-process
issuer, never enterprise identity validation. The other two writes of the plane,
activate and issue, act on packages this worker does not compose.

**The gate (AW-5), stricter than the decision route.** The proof arrives on the same
header the decision route reads. A worker composed without an identity port refuses
every write; so does a missing proof, a proof that authenticates nobody, a non-human
actor, a proof that has expired at the write, a port that cannot answer, and a tenant
claim that is missing, ambiguous or not this worker's. There is no presented-approver
fallback: a grant is the basis of a decision, and a grant under a configured tenant has
nothing behind it. The subject recorded as ``loaded_by`` or the revocation's actor is
the issuer-qualified subject reference (ID-2), never the proof.

**What the answer says, honestly (AW-1).** A recorded write carries
``identity_proof: IDP_AUTHENTICATED``, the subject, the authentication reference, and
the adapter's ``issuer_validation`` label, which stays ``IN_PROCESS_ISSUER_ONLY`` until
the owner validates the adapter against a real issuer. Nothing here can claim more.

**The intake (AW-4).** The load body carries ``RoleGrant``'s typed fields and nothing
else; the worker derives ``grant_id`` so a replayed identical load answers
``ALREADY_LOADED`` with the standing grant instead of a second one. No proof, DSN or
credential is echoed in any answer.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import datetime
from typing import Any, Callable, Mapping, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ugence_approver_identity_jwt import ISSUER_VALIDATION
from ugence_authority_directory import (
    AuthorityDirectoryPort,
    ContractViolation,
    GrantAlreadyExistsError,
    GrantNotFoundError,
    PrincipalKind,
    PrincipalRef,
    RoleGrant,
    grant_id_for,
)
from ugence_governance_contracts.api import Validity
from ugence_governed_review_service.identity import (
    IDP_AUTHENTICATED,
    PROOF_HEADER,
    ActorKind,
    ApproverIdentity,
    authentication_reference,
)

from .authority_plane import IMPLEMENTED_WRITES, PLANE_OPERATIONS, SERVED_WRITES, PlaneOperation
from .version import MATURITY

__all__ = [
    "WRITE_OPERATIONS",
    "LOAD_BODY_KEYS",
    "PRINCIPAL_KEYS",
    "REVOKE_BODY_KEYS",
    "build_authority_writes",
]

#: The two writes this module implements, exactly as the contract names them; the
#: router below is built from this tuple so it cannot drift from the document a reader
#: sees. Which of them a router actually registers is ``serve``, defaulting to the
#: contract's ``SERVED_WRITES``.
WRITE_OPERATIONS: tuple[PlaneOperation, ...] = tuple(
    op for op in PLANE_OPERATIONS if op.kind == "write" and op.operation_id in IMPLEMENTED_WRITES)

RULING_GATE = "AW-5"
RULING_INTAKE = "AW-4"
RULING_WRITE = "AW-1"

#: AW-4: the load body carries these keys and no other.
LOAD_BODY_KEYS = frozenset({
    "principal", "role", "scope", "issued_at", "expires_at", "authority_reference", "member_of",
})
PRINCIPAL_KEYS = frozenset({"principal_id", "principal_kind", "display_ref", "quorum"})
REVOKE_BODY_KEYS = frozenset({"reason"})

MAX_TOKEN = 256
MAX_TEXT = 1024


class _Refused(Exception):
    """A typed refusal; the router turns it into the JSON answer."""

    def __init__(self, status: int, result: str, reason: str, ruling: str, **extra: Any) -> None:
        super().__init__(reason)
        self.status, self.result, self.reason, self.ruling, self.extra = status, result, reason, ruling, extra


def _is_typed(value: Any) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= MAX_TOKEN
            and value == value.strip() and not any(ch.isspace() for ch in value)
            and unicodedata.is_normalized("NFC", value))


def _typed(body: Mapping[str, Any], key: str, *, required: bool = True) -> str:
    value = body.get(key, "")
    if value in ("", None):
        if required:
            raise _Refused(422, "REFUSED_UNTYPED", f"{key} is required", RULING_INTAKE)
        return ""
    if not _is_typed(value):
        raise _Refused(422, "REFUSED_UNTYPED",
                       f"{key} must be a typed token: non-empty, NFC, no whitespace, at most "
                       f"{MAX_TOKEN} characters", RULING_INTAKE)
    return value


def _text(body: Mapping[str, Any], key: str) -> str:
    value = body.get(key, "")
    if value in ("", None):
        return ""
    if not isinstance(value, str) or len(value) > MAX_TEXT or not unicodedata.is_normalized("NFC", value):
        raise _Refused(422, "REFUSED_UNTYPED",
                       f"{key} must be NFC text of at most {MAX_TEXT} characters", RULING_INTAKE)
    return value.strip()


def _instant(body: Mapping[str, Any], key: str) -> datetime:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _Refused(422, "REFUSED_UNTYPED", f"{key} is required (ISO 8601, with timezone)",
                       RULING_INTAKE)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _Refused(422, "REFUSED_UNTYPED", f"{key} is not an ISO 8601 instant", RULING_INTAKE)
    if parsed.tzinfo is None:
        raise _Refused(422, "REFUSED_UNTYPED", f"{key} must carry a timezone", RULING_INTAKE)
    return parsed


def _object(value: Any, what: str, allowed: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _Refused(422, "REFUSED_UNTYPED", f"{what} must be an object", RULING_INTAKE)
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise _Refused(422, "REFUSED_UNTYPED",
                       f"{what} carries only {sorted(allowed)}; refused keys {unknown}", RULING_INTAKE)
    return value


def _principal(body: Mapping[str, Any]) -> PrincipalRef:
    raw = _object(body.get("principal"), "principal", PRINCIPAL_KEYS)
    kind_value = raw.get("principal_kind", "")
    try:
        kind = PrincipalKind(str(kind_value))
    except ValueError:
        raise _Refused(422, "REFUSED_UNTYPED",
                       f"principal_kind must be one of {[k.value for k in PrincipalKind]}", RULING_INTAKE)
    quorum = raw.get("quorum", 0)
    if quorum in ("", None):
        quorum = 0
    if isinstance(quorum, bool) or not isinstance(quorum, int) or quorum < 0:
        raise _Refused(422, "REFUSED_UNTYPED", "quorum must be a non-negative integer", RULING_INTAKE)
    try:
        return PrincipalRef(principal_id=_typed(raw, "principal_id"), principal_kind=kind,
                            display_ref=_text(raw, "display_ref"), quorum=quorum)
    except ContractViolation as exc:
        raise _Refused(422, "REFUSED_UNTYPED", str(exc), RULING_INTAKE)


def build_authority_writes(
    directory: AuthorityDirectoryPort,
    *,
    tenant_id: str,
    clock: Callable[[], datetime],
    identity_port: Optional[Any],
    serve: tuple[str, ...] = SERVED_WRITES,
) -> Any:
    """A FastAPI router over one directory, for one tenant, at one clock, behind one
    identity port, registering exactly the writes ``serve`` names. The default is the
    contract's ``SERVED_WRITES``, empty under AP-3 until enterprise issuer validation is
    recorded, so the composed worker registers nothing. ``identity_port`` may be
    ``None``: every write is then refused (AW-5), never recorded as presented."""
    if not _is_typed(tenant_id):
        raise ValueError("tenant_id must be a typed token")
    unknown = sorted(set(serve) - set(IMPLEMENTED_WRITES))
    if unknown:
        raise ValueError(f"not implemented here: {unknown}")
    router = APIRouter(tags=["authority"])
    by_id = {op.operation_id: op for op in WRITE_OPERATIONS}
    grant_op, revoke_op = by_id["authority_grant_role"], by_id["authority_revoke_grant"]

    def refusal(op: PlaneOperation, exc: _Refused) -> Any:
        content = {
            "result": exc.result, "recorded": False, "plane": "authority", "ruling": exc.ruling,
            "operation": op.operation_id, "reason": exc.reason,
            "issuer_validation": ISSUER_VALIDATION, "maturity": MATURITY, **exc.extra,
        }
        return JSONResponse(status_code=exc.status, content=content)

    def recorded(op: PlaneOperation, identity: ApproverIdentity, as_of: datetime,
                 grant: RoleGrant, event: str) -> dict:
        assert identity.claims is not None
        return {
            "result": "RECORDED", "recorded": True, "plane": "authority", "ruling": RULING_WRITE,
            "operation": op.operation_id, "tenant_id": tenant_id, "as_of": as_of.isoformat(),
            "identity_proof": identity.proof, "subject": identity.actor_id,
            "authentication_reference": authentication_reference(identity.claims),
            "issuer_validation": ISSUER_VALIDATION,
            "provenance": "what an administrator loaded; the directory attests nothing about whether it should exist",
            "maturity": MATURITY, "event": event, "grant": grant.to_dict(),
        }

    def resolve(proof: str, as_of: datetime) -> ApproverIdentity:
        """AW-5. The proven human subject of this tenant, or a typed refusal."""
        if identity_port is None:
            raise _Refused(409, "REFUSED_NO_IDENTITY_PORT",
                           "no identity port is composed; a write is never recorded as presented",
                           RULING_GATE)
        if not proof:
            raise _Refused(409, "REFUSED_UNAUTHENTICATED",
                           f"no proof was presented on {PROOF_HEADER}", RULING_GATE)
        try:
            identity = identity_port.authenticate(proof)
        except Exception as exc:  # noqa: BLE001 - fail closed on any failure to answer
            raise _Refused(409, "REFUSED_IDENTITY_UNAVAILABLE",
                           f"the identity port could not answer: {type(exc).__name__}", RULING_GATE)
        if not isinstance(identity, ApproverIdentity):
            raise _Refused(409, "REFUSED_IDENTITY_UNAVAILABLE",
                           "the identity port answered with the wrong shape", RULING_GATE)
        if not identity.authenticated or identity.claims is None \
                or identity.proof != IDP_AUTHENTICATED:
            raise _Refused(409, "REFUSED_UNAUTHENTICATED",
                           "the proof does not authenticate anyone", RULING_GATE)
        if identity.actor_type is not ActorKind.HUMAN:
            raise _Refused(409, "REFUSED_NOT_HUMAN",
                           f"a {identity.actor_type.value} actor never administers a grant", RULING_GATE)
        if identity.claims.expires_at <= as_of:
            raise _Refused(409, "REFUSED_UNAUTHENTICATED",
                           "the proof had expired when the write was made", RULING_GATE)
        claims = identity.claims.tenant_claims
        if len(claims) != 1:
            raise _Refused(409, "REFUSED_TENANT_UNPROVEN",
                           "the proof carries no single tenant claim; configuration never fills the gap",
                           RULING_GATE)
        if claims[0] != tenant_id:
            raise _Refused(409, "REFUSED_TENANT_MISMATCH",
                           "the proof's tenant is not this worker's tenant", RULING_GATE)
        return identity

    async def parse(request: Request, allowed: frozenset[str], what: str) -> Mapping[str, Any]:
        raw = await request.body()
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            raise _Refused(422, "REFUSED_UNTYPED", f"the {what} body must be a JSON object", RULING_INTAKE)
        return _object(body, f"the {what} body", allowed)

    async def grant_role(request: Request) -> Any:
        try:
            as_of = clock()
            identity = resolve(request.headers.get(PROOF_HEADER, ""), as_of)
            body = await parse(request, LOAD_BODY_KEYS, "load")
            principal = _principal(body)
            role, scope = _typed(body, "role"), _typed(body, "scope")
            issued_at, expires_at = _instant(body, "issued_at"), _instant(body, "expires_at")
            try:
                validity = Validity(issued_at=issued_at, expires_at=expires_at)
                grant = RoleGrant(
                    grant_id=grant_id_for(tenant_id, principal.principal_id, role, scope, validity),
                    tenant_id=tenant_id, principal=principal, role=role, scope=scope,
                    validity=validity, authority_reference=_text(body, "authority_reference"),
                    member_of=_text(body, "member_of"),
                )
            except (ContractViolation, ValueError, TypeError) as exc:
                raise _Refused(422, "REFUSED_UNTYPED", str(exc), RULING_INTAKE)
            try:
                stored = directory.put_grant(grant, as_of=as_of, loaded_by=identity.actor_id)
            except GrantAlreadyExistsError:
                standing = directory.get_grant(grant.grant_id)
                raise _Refused(409, "ALREADY_LOADED",
                               "an identical grant is already loaded; a grant is a record and is never "
                               "overwritten", RULING_INTAKE,
                               grant=standing.to_dict() if standing is not None else None)
            except ContractViolation as exc:
                raise _Refused(422, "REFUSED_UNTYPED", str(exc), RULING_INTAKE)
        except _Refused as exc:
            return refusal(grant_op, exc)
        return recorded(grant_op, identity, as_of, stored, "GRANTED")

    async def revoke_grant(grant_id: str, request: Request) -> Any:
        try:
            as_of = clock()
            identity = resolve(request.headers.get(PROOF_HEADER, ""), as_of)
            if not _is_typed(grant_id):
                raise _Refused(422, "REFUSED_UNTYPED", "grant_id must be a typed token", RULING_INTAKE)
            body = await parse(request, REVOKE_BODY_KEYS, "revoke")
            reason = _text(body, "reason")
            standing = directory.get_grant(grant_id)
            if standing is None or standing.tenant_id != tenant_id:
                # a foreign tenant's grant is not distinguishable from an unknown one, on purpose
                raise _Refused(404, "NOT_FOUND", f"this tenant holds no grant {grant_id!r}", RULING_INTAKE)
            if standing.revoked_at is not None:
                raise _Refused(409, "ALREADY_REVOKED",
                               f"grant {grant_id!r} was revoked at {standing.revoked_at.isoformat()}",
                               RULING_INTAKE, grant=standing.to_dict())
            try:
                revoked = directory.revoke_grant(grant_id, as_of=as_of, reason=reason,
                                                 actor=identity.actor_id)
            except GrantNotFoundError:
                raise _Refused(404, "NOT_FOUND", f"this tenant holds no grant {grant_id!r}", RULING_INTAKE)
            except ContractViolation as exc:
                raise _Refused(422, "REFUSED_UNTYPED", str(exc), RULING_INTAKE)
        except _Refused as exc:
            return refusal(revoke_op, exc)
        return recorded(revoke_op, identity, as_of, revoked, "REVOKED")

    # Registration is the one place the contract's served set is consulted: an
    # implemented write that the contract does not name is not reachable.
    if grant_op.operation_id in serve:
        router.add_api_route(grant_op.path, grant_role, methods=[grant_op.method],
                             operation_id=grant_op.operation_id, summary=grant_op.summary)
    if revoke_op.operation_id in serve:
        router.add_api_route(revoke_op.path, revoke_grant, methods=[revoke_op.method],
                             operation_id=revoke_op.operation_id, summary=revoke_op.summary)
    return router
