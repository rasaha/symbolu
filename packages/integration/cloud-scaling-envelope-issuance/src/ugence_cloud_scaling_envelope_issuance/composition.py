"""The composition root: one candidate, two verifiers, one seam, one signed envelope.

:class:`CloudScalingEnvelopeIssuance` is what a deployment constructs — once, with the
Risk Authority application that evaluated the decision, an envelope signer, the two
upstream verifiers and the one authoritative clock — and then calls per candidate. Each
call builds one :class:`~.verification.CloudScalingArtifactVerification` for that
candidate and one ``EnvelopeIssuanceSeam`` over it, and hands the seam a request whose
tenant, decision id and decision digest are read off the candidate. The seam does the rest:
one clock read, decision digest recomputed, verifiers run at that instant, envelope signed
with the five bindings, expiry capped by the decision.

What the caller supplies: the candidate, the v2 producer attestation, an audience, a session
id and a nonce. What the caller cannot supply: an instant, a decision, a scope wider than the
decision's, a binding, or a signer other than the one the root was built with.

**Production posture.** :meth:`production` refuses a reference-mode application, the
reference signer, a non-authoritative signer and either verifier built outside production
mode. The seam repeats its own checks on every act.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from risk_authority.api import (
    EnvelopeIssuanceOutcome,
    EnvelopeIssuanceRefusal,
    EnvelopeIssuanceRequest,
    EnvelopeIssuanceSeam,
    RiskAuthorityApplication,
)
from risk_authority.crypto import SigningKeyRecord
from risk_authority.domain import RiskAuthorizationEnvelope
from risk_authority.services import EnvelopeSignerPort, ReferenceEnvelopeSigner
from ugence_cloud_scaling_authorization_contracts import CapacityAuthorizationCandidate
from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityVerifier
from ugence_cloud_scaling_producer_attestation import (
    ProducerAttestationV2,
    ProducerAttestationVerifier,
)

from .errors import EnvelopeIssuanceConfigurationError, EnvelopeIssuanceExactTypeError
from .identifiers import REQUIRED_BINDING_KINDS
from .outcomes import CloudScalingVerificationReport
from .verification import CloudScalingArtifactVerification

__all__ = [
    "CloudScalingEnvelopeIssuance",
    "CloudScalingEnvelopeIssuanceOutcome",
    "CloudScalingEnvelopeIssuanceRequest",
]


def _exact(value: object, expected: type, name: str) -> None:
    if type(value) is not expected:
        raise EnvelopeIssuanceExactTypeError(
            f"{name} must be exactly {expected.__name__} (got {type(value).__name__})"
        )


def _token(name: str, value: object) -> None:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise EnvelopeIssuanceExactTypeError(
            f"{name} must be a non-blank str without surrounding whitespace"
        )


@dataclass(frozen=True)
class CloudScalingEnvelopeIssuanceRequest:
    """What a caller may say. No instant, no decision, no bindings, no scope."""

    candidate: CapacityAuthorizationCandidate
    producer_attestation: ProducerAttestationV2
    audience: str
    session_id: str
    nonce: str
    ttl: Optional[timedelta] = None

    def __post_init__(self) -> None:
        _exact(self.candidate, CapacityAuthorizationCandidate, "candidate")
        _exact(self.producer_attestation, ProducerAttestationV2, "producer_attestation")
        _token("audience", self.audience)
        _token("session_id", self.session_id)
        _token("nonce", self.nonce)
        if self.ttl is not None and (type(self.ttl) is not timedelta or self.ttl <= timedelta(0)):
            raise EnvelopeIssuanceExactTypeError("ttl must be a positive timedelta or None")


@dataclass(frozen=True)
class CloudScalingEnvelopeIssuanceOutcome:
    """The seam's outcome beside the port's report. ``executable`` is permanently ``False``."""

    issued: bool
    issued_at: datetime
    envelope: Optional[RiskAuthorizationEnvelope]
    refusal: Optional[EnvelopeIssuanceRefusal]
    detail: str
    report: Optional[CloudScalingVerificationReport]

    @property
    def executable(self) -> bool:
        """Always ``False``: an envelope is authority, not execution (5C, 5X pending)."""

        return False

    @property
    def grants_authority(self) -> bool:
        """``True`` iff a signed envelope was issued. The envelope, not this object, is it."""

        return self.issued and self.envelope is not None


class CloudScalingEnvelopeIssuance:
    """Compose the ladder into Phase 5 issuance. Construct via ``production`` or ``reference``."""

    def __init__(
        self,
        *,
        app: RiskAuthorityApplication,
        signer: Optional[EnvelopeSignerPort],
        key_record: Optional[SigningKeyRecord],
        producer_verifier: ProducerAttestationVerifier,
        policy_verifier: PolicyAuthenticityVerifier,
        clock: Callable[[], datetime],
        production: bool,
    ) -> None:
        if not isinstance(app, RiskAuthorityApplication):
            raise EnvelopeIssuanceConfigurationError(
                "a RiskAuthorityApplication is required: the instance that evaluated the "
                "decision (ADR D-5)"
            )
        _exact(producer_verifier, ProducerAttestationVerifier, "producer_verifier")
        _exact(policy_verifier, PolicyAuthenticityVerifier, "policy_verifier")
        if not callable(clock):
            raise EnvelopeIssuanceConfigurationError("clock must be a callable returning a datetime")
        if (signer is None) == (key_record is None):
            raise EnvelopeIssuanceConfigurationError(
                "exactly one of signer (production) or key_record (reference) is required"
            )
        self._app = app
        self._signer = signer
        self._key_record = key_record
        self._producer_verifier = producer_verifier
        self._policy_verifier = policy_verifier
        self._clock = clock
        self._production = production

    # ------------------------------------------------------------------ factories
    @classmethod
    def production(
        cls,
        *,
        app: RiskAuthorityApplication,
        signer: EnvelopeSignerPort,
        producer_verifier: ProducerAttestationVerifier,
        policy_verifier: PolicyAuthenticityVerifier,
        clock: Callable[[], datetime],
    ) -> "CloudScalingEnvelopeIssuance":
        """Production composition. Fails closed on any reference-grade dependency."""

        if getattr(app, "_production_mode", False) is not True:
            raise EnvelopeIssuanceConfigurationError(
                "production issuance requires a RiskAuthorityApplication in production mode"
            )
        if isinstance(signer, ReferenceEnvelopeSigner) or (
            getattr(signer, "is_production_authoritative", False) is not True
        ):
            raise EnvelopeIssuanceConfigurationError(
                "production issuance requires a production-authoritative EnvelopeSignerPort; "
                "the in-memory reference signer is refused (ADR D-5)"
            )
        _exact(producer_verifier, ProducerAttestationVerifier, "producer_verifier")
        _exact(policy_verifier, PolicyAuthenticityVerifier, "policy_verifier")
        if producer_verifier.production_mode is not True:
            raise EnvelopeIssuanceConfigurationError(
                "production issuance requires a ProducerAttestationVerifier built with "
                "production_mode=True"
            )
        if policy_verifier.production_mode is not True:
            raise EnvelopeIssuanceConfigurationError(
                "production issuance requires a PolicyAuthenticityVerifier built with "
                "production_mode=True"
            )
        return cls(
            app=app, signer=signer, key_record=None, producer_verifier=producer_verifier,
            policy_verifier=policy_verifier, clock=clock, production=True,
        )

    @classmethod
    def reference(
        cls,
        *,
        app: RiskAuthorityApplication,
        key_record: SigningKeyRecord,
        producer_verifier: ProducerAttestationVerifier,
        policy_verifier: PolicyAuthenticityVerifier,
        clock: Callable[[], datetime],
    ) -> "CloudScalingEnvelopeIssuance":
        """Labelled conformance composition over the reference signer. Never production."""

        if getattr(app, "_production_mode", False) is True:
            raise EnvelopeIssuanceConfigurationError(
                "the reference composition cannot be built over a production application"
            )
        if not isinstance(key_record, SigningKeyRecord):
            raise EnvelopeIssuanceConfigurationError("reference issuance requires a SigningKeyRecord")
        return cls(
            app=app, signer=None, key_record=key_record, producer_verifier=producer_verifier,
            policy_verifier=policy_verifier, clock=clock, production=False,
        )

    @property
    def is_production(self) -> bool:
        return self._production

    @property
    def required_binding_kinds(self) -> tuple[str, ...]:
        return REQUIRED_BINDING_KINDS

    # ------------------------------------------------------------------ the act
    def issue(
        self,
        request: CloudScalingEnvelopeIssuanceRequest,
        *,
        envelope_id: Optional[str] = None,
    ) -> CloudScalingEnvelopeIssuanceOutcome:
        _exact(request, CloudScalingEnvelopeIssuanceRequest, "request")
        port = CloudScalingArtifactVerification(
            candidate=request.candidate,
            attestation=request.producer_attestation,
            producer_verifier=self._producer_verifier,
            policy_verifier=self._policy_verifier,
        )
        if self._production:
            seam = EnvelopeIssuanceSeam.production(
                app=self._app, signer=self._signer, verification=port,
                required_binding_kinds=REQUIRED_BINDING_KINDS, clock=self._clock,
            )
        else:
            seam = EnvelopeIssuanceSeam.reference(
                app=self._app, key_record=self._key_record, verification=port,
                required_binding_kinds=REQUIRED_BINDING_KINDS, clock=self._clock,
            )
        candidate = request.candidate
        outcome: EnvelopeIssuanceOutcome = seam.issue(
            EnvelopeIssuanceRequest(
                tenant_id=candidate.tenant_id,
                decision_id=candidate.decision_id,
                decision_digest=candidate.decision_digest,
                audience=request.audience,
                session_id=request.session_id,
                nonce=request.nonce,
                ttl=request.ttl,
            ),
            envelope_id=envelope_id,
        )
        return CloudScalingEnvelopeIssuanceOutcome(
            issued=outcome.issued,
            issued_at=outcome.issued_at,
            envelope=outcome.envelope,
            refusal=outcome.refusal,
            detail=outcome.detail,
            report=port.report,
        )
