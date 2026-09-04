"""The composition root: one presented capacity action, one gate, one seam, one verdict.

:class:`CloudScalingActionAdmission` is what a deployment constructs — once, with the Risk
Authority application standing on the durable store that holds the envelope, and the one
authoritative clock — and then calls per action. Each call maps the presented target scope
onto the fixed D-2 ``CanonicalAction``, builds one :class:`CapacityActionGate` over the
presented artifacts and one ``ActionAdmissionSeam`` over it, and hands the seam a request.
The seam does the rest: one clock read, the envelope from the store, kernel verification,
the derived authorization id, replay, the port, persistence and the event.

What the caller supplies: an envelope id, the target scope, the candidate digest, the
session id, satisfied conditions. What the caller cannot supply: an instant, an action, a
binding, a decision, or a gate other than this package's.

**Production posture.** :meth:`production` refuses a reference-mode application; the seam
repeats its own checks on every act.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from risk_authority.api import (
    ActionAdmissionOutcome,
    ActionAdmissionRefusal,
    ActionAdmissionRequest,
    ActionAdmissionSeam,
    RiskAuthorityApplication,
)
from risk_authority.domain.actions import ActionAuthorization, CanonicalAction
from ugence_cloud_scaling_authorization_contracts import ExecutionTargetScope, is_canonical_digest

from .errors import ActionAdmissionConfigurationError, ActionAdmissionExactTypeError
from .gate import CapacityActionGate
from .mapping import capacity_action_to_canonical

__all__ = [
    "CapacityAdmissionRequest",
    "CapacityAdmissionOutcome",
    "CloudScalingActionAdmission",
]


def _token(name: str, value: object) -> None:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ActionAdmissionExactTypeError(
            f"{name} must be a non-blank str without surrounding whitespace")


@dataclass(frozen=True)
class CapacityAdmissionRequest:
    """What a caller may say. No instant, no action, no binding, no decision."""

    tenant_id: str
    envelope_id: str
    target_scope: ExecutionTargetScope
    candidate_digest: str
    session_id: str
    satisfied_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _token("tenant_id", self.tenant_id)
        _token("envelope_id", self.envelope_id)
        _token("session_id", self.session_id)
        if type(self.target_scope) is not ExecutionTargetScope:
            raise ActionAdmissionExactTypeError("target_scope must be exactly an ExecutionTargetScope")
        if not is_canonical_digest(self.candidate_digest):
            raise ActionAdmissionExactTypeError("candidate_digest must be a sha256:-prefixed digest")
        if self.target_scope.tenant_id != self.tenant_id:
            raise ActionAdmissionExactTypeError("target_scope.tenant_id must equal the request tenant_id")
        if not isinstance(self.satisfied_conditions, tuple) or any(
            type(c) is not str for c in self.satisfied_conditions
        ):
            raise ActionAdmissionExactTypeError("satisfied_conditions must be a tuple of str")


@dataclass(frozen=True)
class CapacityAdmissionOutcome:
    """The seam's outcome beside the action it ruled on. ``executable`` is permanently ``False``."""

    admitted_at: datetime
    action: Optional[CanonicalAction]
    authorization: Optional[ActionAuthorization]
    refusal: Optional[ActionAdmissionRefusal]
    detail: str

    @property
    def admitted(self) -> bool:
        return self.authorization is not None and self.authorization.authorized

    @property
    def replayed(self) -> bool:
        from risk_authority.domain.enums import AuthorizationDisposition

        return (self.authorization is not None
                and self.authorization.disposition is AuthorizationDisposition.REPLAYED)

    @property
    def executable(self) -> bool:
        """Always ``False``: admission is not execution (5X, 5D pending)."""

        return False


class CloudScalingActionAdmission:
    """Compose the ladder into Phase 5C admission. Construct via ``production`` or ``reference``."""

    def __init__(self, *, app: RiskAuthorityApplication, clock: Callable[[], datetime],
                 production: bool) -> None:
        if not isinstance(app, RiskAuthorityApplication):
            raise ActionAdmissionConfigurationError(
                "a RiskAuthorityApplication standing on the store that holds the envelope is required")
        if not callable(clock):
            raise ActionAdmissionConfigurationError("clock must be a callable returning a datetime")
        self._app = app
        self._clock = clock
        self._production = production

    @classmethod
    def production(cls, *, app: RiskAuthorityApplication, clock: Callable[[], datetime]
                   ) -> "CloudScalingActionAdmission":
        if getattr(app, "_production_mode", False) is not True:
            raise ActionAdmissionConfigurationError(
                "production admission requires a RiskAuthorityApplication in production mode")
        return cls(app=app, clock=clock, production=True)

    @classmethod
    def reference(cls, *, app: RiskAuthorityApplication, clock: Callable[[], datetime]
                  ) -> "CloudScalingActionAdmission":
        if getattr(app, "_production_mode", False) is True:
            raise ActionAdmissionConfigurationError(
                "the reference composition cannot be built over a production application")
        return cls(app=app, clock=clock, production=False)

    @property
    def is_production(self) -> bool:
        return self._production

    def admit(self, request: CapacityAdmissionRequest) -> CapacityAdmissionOutcome:
        if type(request) is not CapacityAdmissionRequest:
            raise ActionAdmissionExactTypeError("admit requires a CapacityAdmissionRequest")
        gate = CapacityActionGate(target_scope=request.target_scope,
                                  candidate_digest=request.candidate_digest)
        seam = (ActionAdmissionSeam.production(app=self._app, gate=gate, clock=self._clock)
                if self._production
                else ActionAdmissionSeam.reference(app=self._app, gate=gate, clock=self._clock))
        # The seam loads and verifies the envelope itself; the mapping needs it first, so an
        # unknown envelope is reported exactly as the seam would report it, before any clock read.
        envelope = self._app.envelopes.get(request.tenant_id, request.envelope_id)
        if envelope is None:
            outcome = seam.issue(_probe_request(request))
            return CapacityAdmissionOutcome(admitted_at=outcome.admitted_at, action=None,
                                            authorization=None, refusal=outcome.refusal,
                                            detail=outcome.detail)
        action = capacity_action_to_canonical(envelope, request.target_scope)
        outcome: ActionAdmissionOutcome = seam.issue(ActionAdmissionRequest(
            tenant_id=request.tenant_id, envelope_id=request.envelope_id, action=action,
            session_id=request.session_id, satisfied_conditions=request.satisfied_conditions))
        return CapacityAdmissionOutcome(admitted_at=outcome.admitted_at, action=action,
                                        authorization=outcome.authorization,
                                        refusal=outcome.refusal, detail=outcome.detail)


def _probe_request(request: CapacityAdmissionRequest) -> ActionAdmissionRequest:
    """A well-formed seam request for an envelope the store does not hold, so the seam's own
    ``ENVELOPE_NOT_FOUND`` refusal (and its one clock read) is what the caller sees."""

    scope = request.target_scope
    return ActionAdmissionRequest(
        tenant_id=request.tenant_id, envelope_id=request.envelope_id,
        action=CanonicalAction(tenant_id=request.tenant_id, actor_id="-", model_id="-",
                               action_type=scope.action_type, target_id=scope.digest(),
                               purpose="cloud_scaling.capacity_action"),
        session_id=request.session_id, satisfied_conditions=request.satisfied_conditions)
