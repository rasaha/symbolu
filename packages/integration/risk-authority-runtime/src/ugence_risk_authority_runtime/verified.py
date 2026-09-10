"""The verified production path: envelope → binding → internal verified result (D-A…D-C).

    THE TYPE IN THIS MODULE IS NOT PROOF. THE CHECKS ARE.

Read that first, because the shape of this module invites the opposite reading.
:class:`VerifiedRiskAuthorityResult` is an *internal verified-flow marker*: it exists so a
reference-produced verdict cannot be accidentally mixed into the production composition
path. It is emphatically **not** a second Risk Authority, not an attestation authority, and
not a signature format. Trust comes from one place and one place only — a successfully
verified, signed ``RiskAuthorizationEnvelope`` and the binding checks below.

Why this module exists
----------------------
Before it, every consumer built its own :class:`RiskAuthorityMachineResult` and handed it to
``RiskAuthorityCompositionEngine.compose``. The engine type-checked nothing, the result
carried no envelope reference, and ``source_version`` read identically whether a production
gate or the reference gate produced it. A deployment could therefore assert ``ALLOW`` and
the composition layer's ``FinalAuthority ≤ RiskAuthority`` invariant would hold only if that
assertion happened to be honest.

The ruling (ADR §2, §8/D-A): a deployment-supplied result is non-authoritative regardless of
its Python type or any posture field it carries. The runtime must verify the envelope itself
and derive the result from it.

The load-bearing observation is that nothing new had to be invented. Risk Authority's own
``ActionAuthorization`` (``risk_authority.domain.actions``) already binds ``envelope_id``,
``action_digest``, ``decision``, ``tenant_id`` and ``expires_at``; it is already what
``ActionGatePort.authorize`` returns; and the RA-4.5 adapter was already receiving it and
discarding everything but the decision and reason codes. This module stops discarding it.

The eight binding checks (D-A)
------------------------------
Run in order, each fail-closed, none skippable:

1. the envelope verifies through the canonical :class:`EnvelopeVerifier` — signature, key,
   issuer, ``not_before`` / ``expires_at``, tenant, session, revocation and epoch;
2. temporal validity re-asserted at the **injected trusted clock** the verifier was given
   (the caller supplies the clock, never a bare timestamp read here);
3. ``authorization.envelope_id`` equals the verified envelope's;
4. ``authorization.action_digest`` equals the presented canonical action's digest;
5. ``authorization.tenant_id``, when carried, agrees with the envelope's;
6. the presented action's ``tenant_id`` agrees with the envelope's;
7. the effective verdict is exactly ``ActionGateDecision.AUTHORIZED`` for an ALLOW — any
   other value is a DENY, and a decision that is not an ``ActionGateDecision`` at all is a
   typed refusal, never a pass;
8. the envelope's policy bindings are present and structurally intact
   (``workflow_ir_digest`` — the policy identity the decision was bound to).

A failure in 1 is ``DENY`` (Risk Authority refused). A failure in 3–6 or 8 is
``BindingViolation`` → ``ERROR`` (the evidence does not cohere; this is not an authoritative
negative about the request). This distinction is deliberate: a mismatched binding must never
be recorded as "Risk Authority denied", because Risk Authority was never coherently asked.

Envelope digest (D-C)
---------------------
``envelope_digest`` is ``sha256_hex(envelope.signing_payload())`` — the repository's
established algorithm and identifier (``sha256:<hex>``), computed here at the binding site
over the exact canonical signing bytes. ``envelope_id`` is *not* content-addressed to that
payload (it is a caller-supplied parameter of ``EnvelopeIssuer.issue``), so the computed
digest is retained rather than reusing the id. Nothing is added to the stdlib-only RA leaf.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from risk_authority.crypto import KeyRing
from risk_authority.crypto.hashing import sha256_hex
from risk_authority.domain import (
    ActionGateDecision,
    CanonicalAction,
    RiskAuthorizationEnvelope,
)
from risk_authority.domain.actions import ActionAuthorization
from risk_authority.integrations import RuntimeIdentity
from risk_authority.services.envelope_verifier import EnvelopeVerifier
from risk_authority.services.revocation import RevocationState

from .contracts import (
    ReasonCode,
    RiskAuthorityDisposition,
    RiskAuthorityMachineResult,
)

__all__ = [
    "BindingViolation",
    "VerifiedRiskAuthorityResult",
    "verify_and_bind",
]


class BindingViolation(Exception):
    """The authority evidence does not cohere — fail closed, never a verdict.

    Raised only for internal inconsistency between the envelope, the presented action and
    the returned :class:`ActionAuthorization`. It is **not** a denial: a denial is Risk
    Authority's authoritative answer to a coherent question, and a binding violation means
    no coherent question was asked.
    """


# A module-private token. It makes accidental construction of a verified result outside
# this module awkward, and that is *all* it does — ADR §8/D-B is explicit that neither the
# constructor nor the exact type is cryptographic proof. Anyone determined to forge one
# can; the point is that no one does so by accident while wiring a deployment.
_MINT = object()


@dataclass(frozen=True)
class VerifiedRiskAuthorityResult:
    """A composition input derived from a verified envelope (D-B).

    Produced **only** by :func:`verify_and_bind`. Never exposed through
    ``GovernanceInputSource`` and never constructed by a consumer. Carries the derived
    :class:`RiskAuthorityMachineResult` the composition engine consumes, plus the binding
    evidence that justifies it.
    """

    result: RiskAuthorityMachineResult
    envelope_id: str
    #: ``sha256:<hex>`` over the envelope's canonical signing payload (D-C).
    envelope_digest: str
    action_digest: str
    authorization_id: str
    #: The policy identity the envelope's decision was bound to.
    workflow_ir_digest: str
    #: The binding decision the envelope was issued from.
    decision_id: str
    authority_epoch: int
    not_before: datetime
    expires_at: datetime
    #: The trusted instant the binding was evaluated at.
    verified_at: datetime
    #: ``True`` only when a production-authoritative gate produced the authorization.
    #: A reference/test enforcer stamps ``False``, and the production composition path
    #: refuses it — this is how ADR §8/D-E's "reference-produced results cannot enter the
    #: verified production composition path" is made true rather than asserted.
    production: bool = False
    _token: object = None

    def __post_init__(self) -> None:
        if self._token is not _MINT:
            raise BindingViolation(
                "VerifiedRiskAuthorityResult is minted only by verify_and_bind(); "
                "a consumer-constructed instance carries no verification and is refused")

    @property
    def authorized(self) -> bool:
        return self.result.disposition is RiskAuthorityDisposition.ALLOW


def _machine_result(
    *,
    disposition: RiskAuthorityDisposition,
    reason: ReasonCode,
    envelope: RiskAuthorizationEnvelope,
    action: CanonicalAction,
    raw: tuple[str, ...],
    source_version: str,
    include_action: bool,
) -> RiskAuthorityMachineResult:
    return RiskAuthorityMachineResult(
        disposition=disposition,
        reason_codes=(reason.value,),
        envelope_id=envelope.envelope_id,
        action_digest=action.digest,
        action=action if include_action else None,
        scope=envelope.scope,
        expires_at=envelope.expires_at,
        source_version=source_version,
        raw_reason_codes=raw,
    )


def verify_and_bind(
    *,
    envelope: RiskAuthorizationEnvelope,
    authorization: ActionAuthorization,
    action: CanonicalAction,
    identity: RuntimeIdentity,
    key_ring: KeyRing,
    revocation_state: RevocationState,
    now: datetime,
    source_version: str = "",
    production: bool = False,
    verifier: Optional[EnvelopeVerifier] = None,
) -> VerifiedRiskAuthorityResult:
    """Verify the envelope, bind the authorization to it, and derive the result (D-A).

    ``now`` is the trusted instant, supplied by the composition root's clock. This function
    reads no clock of its own, so a caller cannot be given one verdict and record another.

    Raises :class:`BindingViolation` when the evidence does not cohere. Returns a
    ``DENY``-carrying result when Risk Authority coherently refused.
    """

    if type(envelope) is not RiskAuthorizationEnvelope:
        raise BindingViolation("envelope must be exactly a RiskAuthorizationEnvelope")
    if type(action) is not CanonicalAction:
        raise BindingViolation("action must be exactly a CanonicalAction")
    if type(authorization) is not ActionAuthorization:
        raise BindingViolation("authorization must be exactly an ActionAuthorization")
    if not isinstance(now, datetime):
        raise BindingViolation("now must be a datetime from the composition root's clock")

    envelope_digest = sha256_hex(envelope.signing_payload())  # (D-C)

    # (3)-(6) Binding coherence, before any verdict is read. A mismatch here means the
    # evidence describes a different action, envelope or tenant than the one presented.
    if authorization.envelope_id != envelope.envelope_id:
        raise BindingViolation(
            f"authorization names envelope {authorization.envelope_id!r}, "
            f"presented envelope is {envelope.envelope_id!r}")
    if authorization.action_digest != action.digest:
        raise BindingViolation(
            f"authorization names action digest {authorization.action_digest!r}, "
            f"presented action digests to {action.digest!r}")
    if authorization.tenant_id and authorization.tenant_id != envelope.tenant_id:
        raise BindingViolation(
            f"authorization names tenant {authorization.tenant_id!r}, "
            f"envelope is {envelope.tenant_id!r}")
    if action.tenant_id != envelope.tenant_id:
        raise BindingViolation(
            f"action names tenant {action.tenant_id!r}, envelope is {envelope.tenant_id!r}")
    if not isinstance(authorization.decision, ActionGateDecision):
        raise BindingViolation("authorization.decision must be an ActionGateDecision")

    # (8) Policy identity must be present. An envelope whose decision names no policy
    # cannot support a claim that policy was honored.
    workflow_ir_digest = getattr(envelope.bindings, "workflow_ir_digest", "")
    if not workflow_ir_digest:
        raise BindingViolation("envelope carries no workflow_ir_digest (policy identity)")

    # (2) Temporal validity first, so exact expiry always names itself.
    #
    # The half-open window ``[not_before, expires_at)`` is also enforced inside the
    # canonical verifier, which would refuse at ``now == expires_at`` as a generic
    # RA_ENVELOPE_INVALID. Asking the question here first means the boundary instant
    # yields the stable, typed RA_EXPIRED outcome instead of depending on which check
    # happens to fire, and it guarantees no GRANT is ever minted whose effective
    # ``expires_at`` equals the evaluation instant. This does not reimplement the
    # verifier: the verifier still runs below and still owns signature, key, tenant,
    # revocation and epoch, and the conformance suite asserts the two agree at every
    # boundary instant.
    if not envelope.is_temporally_valid(now):
        return _bind(
            _machine_result(
                disposition=RiskAuthorityDisposition.DENY,
                reason=ReasonCode.RA_EXPIRED,
                envelope=envelope, action=action,
                raw=("envelope outside [not_before, expires_at) at the trusted instant",),
                source_version=source_version, include_action=False),
            envelope=envelope, envelope_digest=envelope_digest, action=action,
            authorization=authorization, workflow_ir_digest=workflow_ir_digest, now=now,
            production=production)

    # (1) The canonical verification path. Never reimplemented here.
    verification = (verifier or EnvelopeVerifier()).verify(
        envelope=envelope,
        key_ring=key_ring,
        revocation_state=revocation_state,
        now=now,
        expected_tenant=identity.tenant_id,
        expected_audience=getattr(identity, "audience", None) or None,
        expected_session=getattr(identity, "session_id", None) or None,
    )
    if not verification.valid:
        return _bind(
            _machine_result(
                disposition=RiskAuthorityDisposition.DENY,
                reason=ReasonCode.RA_ENVELOPE_INVALID,
                envelope=envelope, action=action,
                raw=tuple(verification.reasons), source_version=source_version,
                include_action=False),
            envelope=envelope, envelope_digest=envelope_digest, action=action,
            authorization=authorization, workflow_ir_digest=workflow_ir_digest, now=now,
            production=production)

    # (7) The effective verdict. Only AUTHORIZED is an ALLOW; everything else is a DENY.
    authorized = authorization.decision is ActionGateDecision.AUTHORIZED
    return _bind(
        _machine_result(
            disposition=(RiskAuthorityDisposition.ALLOW if authorized
                         else RiskAuthorityDisposition.DENY),
            reason=(ReasonCode.RA_ALLOW if authorized else ReasonCode.RA_DENY),
            envelope=envelope, action=action,
            raw=tuple(authorization.reason_codes), source_version=source_version,
            include_action=authorized),
        envelope=envelope, envelope_digest=envelope_digest, action=action,
        authorization=authorization, workflow_ir_digest=workflow_ir_digest, now=now,
        production=production)


def _bind(
    result: RiskAuthorityMachineResult,
    *,
    envelope: RiskAuthorizationEnvelope,
    envelope_digest: str,
    action: CanonicalAction,
    authorization: ActionAuthorization,
    workflow_ir_digest: str,
    now: datetime,
    production: bool,
) -> VerifiedRiskAuthorityResult:
    return VerifiedRiskAuthorityResult(
        result=result,
        envelope_id=envelope.envelope_id,
        envelope_digest=envelope_digest,
        action_digest=action.digest,
        authorization_id=authorization.authorization_id,
        workflow_ir_digest=workflow_ir_digest,
        decision_id=envelope.decision_id,
        authority_epoch=getattr(envelope.bindings, "authority_epoch", 0),
        not_before=envelope.not_before,
        expires_at=envelope.expires_at,
        verified_at=now,
        production=production,
        _token=_MINT,
    )
