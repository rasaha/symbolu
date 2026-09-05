"""Phase 5 signed envelope issuance seam (ADR RA Phase 5 envelope issuance, D-1 … D-5).

The only place a Phase 5 envelope is signed. Construct via :meth:`production` or
:meth:`reference`; the initializer is internal. The seam composes what Risk
Authority already owns — the decision repository, the issuer, revocation epochs,
the verifier — around one new obligation: **issuance is conditioned on injected
verification**, performed at the seam's own instant, and the envelope commits to
what was verified.

The act, in order:

1. read the clock **once**; that instant is ``issued_at`` and ``not_before``;
2. find the decision for the tenant; recompute its digest and compare it to the
   caller's ``decision_digest`` (a substituted or drifted decision is refused);
3. refuse a decision that grants no authority or has expired at the instant;
4. call the injected :class:`ArtifactVerificationPort` with ``as_of`` = that
   instant; every required binding kind must be present, report ``VERIFIED``,
   and carry ``resolved_as_of`` equal to the instant (``INSTANT_MISMATCH`` is the
   ratified 5B-2 D-4 refusal);
5. issue through :class:`~risk_authority.services.envelope_issuer.EnvelopeIssuer`
   with the signer port, expiry capped by the decision's own expiry, and the
   verified digests as ``artifact_bindings``;
6. persist the envelope and advance the case, exactly as the contained legacy
   path does.

Risk Authority names no domain's artifacts: the composition root declares the
binding kinds it requires. The reference signer and any non-authoritative
verification port are refused by :meth:`production` at construction. The
case-based :meth:`RiskAuthorityApplication.issue_envelope` and
:meth:`authorize_action` stay contained; an envelope authorizes no execution
without 5C admission and 5X credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional, Protocol, runtime_checkable

from ..crypto.canonical import to_canonical_obj
from ..crypto.hashing import digest as _digest
from ..domain.enums import GovernanceEventType, RiskCaseState
from ..domain.envelope import ArtifactBinding, EnvelopeConditions, RiskAuthorizationEnvelope
from ..domain.errors import MonotonicityViolationError, RiskAuthorityError
from ..domain.scope import Scope
from ..services.envelope_issuer import DEFAULT_ENVELOPE_TTL, EnvelopeIssuer
from ..services.envelope_signer import EnvelopeSignerPort, ReferenceEnvelopeSigner
from .dependencies import RiskAuthorityApplication
from .evaluation_seam import SeamConfigurationError

__all__ = [
    "VERIFIED",
    "VerifiedArtifactBinding",
    "ArtifactVerificationPort",
    "EnvelopeIssuanceRequest",
    "EnvelopeIssuanceRefusal",
    "EnvelopeIssuanceOutcome",
    "EnvelopeIssuanceSeam",
]

#: The only outcome token a verified binding may carry. A verifier's own vocabulary
#: is projected onto this one word by the composition package; anything else refuses.
VERIFIED = "VERIFIED"


@dataclass(frozen=True)
class VerifiedArtifactBinding:
    """What the verification port reports for one upstream artifact."""

    kind: str
    digest: str
    outcome: str
    resolved_as_of: datetime


@runtime_checkable
class ArtifactVerificationPort(Protocol):
    """Run every upstream verifier at ``as_of`` and report each artifact's binding."""

    @property
    def is_production_authoritative(self) -> bool: ...

    def verify(self, *, as_of: datetime) -> tuple[VerifiedArtifactBinding, ...]: ...


@dataclass(frozen=True)
class EnvelopeIssuanceRequest:
    tenant_id: str
    decision_id: str
    decision_digest: str
    audience: str
    session_id: str
    nonce: str
    envelope_scope: Optional[Scope] = None
    conditions: Optional[EnvelopeConditions] = None
    ttl: Optional[timedelta] = None


class EnvelopeIssuanceRefusal(str, Enum):
    DECISION_NOT_FOUND = "DECISION_NOT_FOUND"
    DECISION_DIGEST_MISMATCH = "DECISION_DIGEST_MISMATCH"
    DECISION_GRANTS_NO_AUTHORITY = "DECISION_GRANTS_NO_AUTHORITY"
    DECISION_EXPIRED = "DECISION_EXPIRED"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"
    VERIFICATION_INCOMPLETE = "VERIFICATION_INCOMPLETE"
    VERIFICATION_NOT_VERIFIED = "VERIFICATION_NOT_VERIFIED"
    INSTANT_MISMATCH = "INSTANT_MISMATCH"
    BINDING_MALFORMED = "BINDING_MALFORMED"
    SCOPE_EXCEEDS_DECISION = "SCOPE_EXCEEDS_DECISION"
    TTL_INVALID = "TTL_INVALID"
    CASE_NOT_READY = "CASE_NOT_READY"


@dataclass(frozen=True)
class EnvelopeIssuanceOutcome:
    issued: bool
    issued_at: datetime
    envelope: Optional[RiskAuthorizationEnvelope] = None
    refusal: Optional[EnvelopeIssuanceRefusal] = None
    detail: str = ""

    @property
    def executable(self) -> bool:
        """Always ``False``: an envelope is authority, never execution (5C, 5X pending)."""

        return False


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


class EnvelopeIssuanceSeam:
    """Compose the kernel into a verification-conditioned envelope issuance."""

    def __init__(
        self,
        *,
        app: RiskAuthorityApplication,
        signer: EnvelopeSignerPort,
        verification: ArtifactVerificationPort,
        required_binding_kinds: tuple[str, ...],
        clock: Callable[[], datetime],
        production: bool,
    ) -> None:
        self._app = app
        self._signer = signer
        self._verification = verification
        self._required = tuple(required_binding_kinds)
        self._clock = clock
        self._production = production
        self._issuer = EnvelopeIssuer(issuer=getattr(app, "issuer", "ugence-risk-authority"))

    # ------------------------------------------------------------------ factories
    @classmethod
    def production(
        cls,
        *,
        app: RiskAuthorityApplication,
        signer: EnvelopeSignerPort,
        verification: ArtifactVerificationPort,
        required_binding_kinds: tuple[str, ...],
        clock: Callable[[], datetime],
    ) -> "EnvelopeIssuanceSeam":
        """Build a production seam. Fails closed on any reference-grade dependency."""

        if getattr(app, "_production_mode", False) is not True:
            raise SeamConfigurationError(
                "production issuance seam requires a RiskAuthorityApplication in production "
                "mode — the application that evaluated the decision (D-5)")
        if isinstance(signer, ReferenceEnvelopeSigner) or (
                getattr(signer, "is_production_authoritative", False) is not True):
            raise SeamConfigurationError(
                "production issuance seam requires a production-authoritative "
                "EnvelopeSignerPort; the in-memory reference signer is refused (D-5)")
        if getattr(verification, "is_production_authoritative", False) is not True:
            raise SeamConfigurationError(
                "production issuance seam requires a production-authoritative "
                "ArtifactVerificationPort")
        kinds = tuple(required_binding_kinds)
        if not kinds or any(not isinstance(k, str) or not k.strip() for k in kinds):
            raise SeamConfigurationError(
                "production issuance seam requires at least one required binding kind; "
                "an envelope conditioned on nothing is not Phase 5 issuance")
        return cls(app=app, signer=signer, verification=verification,
                   required_binding_kinds=kinds, clock=clock, production=True)

    @classmethod
    def reference(
        cls,
        *,
        app: RiskAuthorityApplication,
        key_record,
        verification: ArtifactVerificationPort,
        clock: Callable[[], datetime],
        required_binding_kinds: tuple[str, ...] = (),
    ) -> "EnvelopeIssuanceSeam":
        """A labelled conformance seam over the in-memory reference signer. Never production."""

        if getattr(app, "_production_mode", False) is True:
            raise SeamConfigurationError(
                "the reference issuance seam cannot be built over a production application")
        return cls(app=app, signer=ReferenceEnvelopeSigner(key_record), verification=verification,
                   required_binding_kinds=tuple(required_binding_kinds), clock=clock,
                   production=False)

    @property
    def is_production(self) -> bool:
        return self._production

    # ------------------------------------------------------------------ issue
    def issue(self, request: EnvelopeIssuanceRequest, *, envelope_id: Optional[str] = None
              ) -> EnvelopeIssuanceOutcome:
        if not isinstance(request, EnvelopeIssuanceRequest):
            raise RiskAuthorityError("issue requires an EnvelopeIssuanceRequest")
        now = self._clock()  # the one clock read of this act (5B-2 D-3, D-4)
        if not _is_aware(now):
            raise RiskAuthorityError("the injected clock must return a timezone-aware instant")

        def refuse(reason: EnvelopeIssuanceRefusal, detail: str = "") -> EnvelopeIssuanceOutcome:
            return EnvelopeIssuanceOutcome(issued=False, issued_at=now, refusal=reason, detail=detail)

        # 2. The decision, bound by digest.
        decision = self._app.decisions.get(request.tenant_id, request.decision_id)
        if decision is None:
            return refuse(EnvelopeIssuanceRefusal.DECISION_NOT_FOUND,
                          "no decision under this tenant and id")
        if _digest(to_canonical_obj(decision)) != request.decision_digest:
            return refuse(EnvelopeIssuanceRefusal.DECISION_DIGEST_MISMATCH,
                          "the stored decision does not re-derive the caller's decision_digest")
        # 3. Authority and time.
        if not decision.grants_authority:
            return refuse(EnvelopeIssuanceRefusal.DECISION_GRANTS_NO_AUTHORITY,
                          f"outcome {decision.outcome.value}")
        if decision.expires_at is not None and now > decision.expires_at:
            return refuse(EnvelopeIssuanceRefusal.DECISION_EXPIRED,
                          f"decision expired at {decision.expires_at.isoformat()}")
        # 4. Verification at this instant.
        try:
            reported = tuple(self._verification.verify(as_of=now))
        except Exception as exc:  # noqa: BLE001 — a failing verifier is never a pass
            return refuse(EnvelopeIssuanceRefusal.VERIFICATION_UNAVAILABLE,
                          f"{type(exc).__name__}")
        bindings: list[ArtifactBinding] = []
        seen: set[str] = set()
        for item in reported:
            if not isinstance(item, VerifiedArtifactBinding):
                return refuse(EnvelopeIssuanceRefusal.BINDING_MALFORMED,
                              "verification port returned a foreign binding type")
            if item.kind in seen:
                return refuse(EnvelopeIssuanceRefusal.BINDING_MALFORMED,
                              f"duplicate binding kind {item.kind!r}")
            seen.add(item.kind)
            if item.outcome != VERIFIED:
                return refuse(EnvelopeIssuanceRefusal.VERIFICATION_NOT_VERIFIED,
                              f"{item.kind}: {item.outcome}")
            if not _is_aware(item.resolved_as_of) or item.resolved_as_of != now:
                return refuse(EnvelopeIssuanceRefusal.INSTANT_MISMATCH,
                              f"{item.kind}: verified at another instant than issuance")
            try:
                bindings.append(ArtifactBinding(kind=item.kind, digest=item.digest))
            except ValueError as exc:
                return refuse(EnvelopeIssuanceRefusal.BINDING_MALFORMED, f"{item.kind}: {exc}")
        missing = [k for k in self._required if k not in seen]
        if missing:
            return refuse(EnvelopeIssuanceRefusal.VERIFICATION_INCOMPLETE,
                          f"required binding kinds absent: {missing}")
        # 5. Expiry capped by the decision; not_before is the instant itself.
        ttl = request.ttl if request.ttl is not None else DEFAULT_ENVELOPE_TTL
        if not isinstance(ttl, timedelta) or ttl <= timedelta(0):
            return refuse(EnvelopeIssuanceRefusal.TTL_INVALID, "ttl must be a positive timedelta")
        if decision.expires_at is not None:
            ttl = min(ttl, decision.expires_at - now)
            if ttl <= timedelta(0):
                return refuse(EnvelopeIssuanceRefusal.DECISION_EXPIRED,
                              "no validity remains on the decision at this instant")
        case = self._app.cases.get(request.tenant_id, decision.case_id)
        try:
            envelope = self._issuer.issue(
                envelope_id=envelope_id or self._app._ids.next("rae"),
                decision=decision,
                audience=request.audience,
                subject=case.subject_id if case is not None else decision.authority_principal_id,
                model_id=case.model_id if case is not None else "",
                session_id=request.session_id,
                nonce=request.nonce,
                revocation_state=self._app.revocation,
                now=now,
                model_digest=decision.model_digest,
                envelope_scope=request.envelope_scope,
                conditions=request.conditions,
                ttl=ttl,
                signer=self._signer,
                artifact_bindings=tuple(bindings),
            )
        except MonotonicityViolationError as exc:
            return refuse(EnvelopeIssuanceRefusal.SCOPE_EXCEEDS_DECISION, str(exc))
        except RiskAuthorityError as exc:
            return refuse(EnvelopeIssuanceRefusal.SCOPE_EXCEEDS_DECISION, str(exc)) \
                if "scope" in str(exc).lower() else \
                refuse(EnvelopeIssuanceRefusal.DECISION_GRANTS_NO_AUTHORITY, str(exc))
        # 6. Persist and advance the case, as the contained legacy path does.
        self._app.envelopes.save(envelope)
        if case is not None:
            try:
                case.transition(target=RiskCaseState.ENVELOPE_ISSUED, actor="risk-authority",
                                reason=f"envelope {envelope.envelope_id}", now=now,
                                event_type=GovernanceEventType.ENVELOPE_ISSUED)
                case.transition(target=RiskCaseState.ACTIVE, actor="risk-authority",
                                reason="authority active", now=now)
            except RiskAuthorityError as exc:
                # The envelope is already persisted and signed; the case ledger is
                # advisory bookkeeping. Report the mismatch rather than hide it.
                return EnvelopeIssuanceOutcome(issued=True, issued_at=now, envelope=envelope,
                                               refusal=EnvelopeIssuanceRefusal.CASE_NOT_READY,
                                               detail=str(exc))
            self._app._emit_case_events(case)
            self._app.cases.save(case)
        return EnvelopeIssuanceOutcome(issued=True, issued_at=now, envelope=envelope)
