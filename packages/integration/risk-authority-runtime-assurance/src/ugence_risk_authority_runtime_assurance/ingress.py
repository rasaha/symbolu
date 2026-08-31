"""Telemetry trust ingress seam (spec §10/D7).

Telemetry is a **new trust boundary**. The trust decision happens *before*
assessment. Producer authentication is delegated to a deployment ingress seam
(Option B) — mirroring RA-5 trusted-evidence ingress and RA-6 lifecycle-write
authorization. The reference milestone does **NOT** claim cryptographic per-event
telemetry signing (that would be an overclaim; no such signing exists).

An admission does three things, fail-closed and never authority-widening:

  1. authenticates the *producer* via the injected :class:`TelemetryAuthenticator`
     (deployment-owned; the reference stand-in is refused in production, F-1);
  2. validates the observation's internal bindings
     (:meth:`~.contracts.TrajectoryObservation.binding_errors`);
  3. checks the observation binds to the *expected* authority domain — the
     wrong-tenant / wrong-workflow / wrong-envelope guard (invariant I7).

Ordering / duplicate / replay handling lives in the observer (§13); the ingress
is the trust gate. A rejected observation yields ``IGNORE_EVENT`` and can never
touch another authority domain or mint/widen authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Tuple, runtime_checkable

from .contracts import AssessmentOutcome, TrajectoryObservation

__all__ = [
    "IngressDisposition",
    "IngressDecision",
    "ExpectedBinding",
    "TelemetryAuthenticator",
    "ReferenceTelemetryAuthenticator",
    "ReferenceIngressRejectedError",
    "TrustedTelemetryIngress",
]


class ReferenceIngressRejectedError(RuntimeError):
    """Raised when a reference telemetry authenticator is wired into production (F-1)."""


class IngressDisposition(str, Enum):
    """How an ingress admission resolved."""

    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class IngressDecision:
    """The audited result of a telemetry admission — carries no authority."""

    disposition: IngressDisposition
    outcome: AssessmentOutcome
    reasons: Tuple[str, ...] = ()
    observation: Optional[TrajectoryObservation] = None

    @property
    def admitted(self) -> bool:
        return self.disposition is IngressDisposition.ADMITTED


@dataclass(frozen=True)
class ExpectedBinding:
    """The authority domain an observation must bind to (invariant I7).

    Supplied by the caller that already knows which authority is being assessed
    (e.g. from the envelope under which the workflow instance runs). Any field left
    as ``None`` is not constrained; a set field that mismatches the observation is a
    hard rejection.
    """

    tenant_id: Optional[str] = None
    workflow_instance_id: Optional[str] = None
    envelope_id: Optional[str] = None

    def mismatches(self, obs: TrajectoryObservation) -> Tuple[str, ...]:
        reasons: list[str] = []
        if self.tenant_id is not None and obs.tenant_id != self.tenant_id:
            reasons.append("wrong tenant")
        if (
            self.workflow_instance_id is not None
            and obs.workflow_instance_id != self.workflow_instance_id
        ):
            reasons.append("wrong workflow")
        if self.envelope_id is not None and obs.envelope_id != self.envelope_id:
            reasons.append("wrong envelope")
        return tuple(reasons)


@runtime_checkable
class TelemetryAuthenticator(Protocol):
    """Authenticate a telemetry producer (spec §10, Option B).

    Returns ``(authenticated, reasons)``. Identity is established out of band by
    the deployment (mTLS / workload identity / trusted process-local channel); the
    seam only *carries* the decision. ``is_reference_authenticator`` marks a
    conformance stand-in production must refuse.
    """

    is_reference_authenticator: bool

    def authenticate(self, obs: TrajectoryObservation) -> Tuple[bool, Tuple[str, ...]]:
        ...


class ReferenceTelemetryAuthenticator:
    """Reference authenticator — trusts any observation carrying a ``source``.

    This performs NO real producer authentication: it exists so the ingress →
    observe → assess flow is exercisable deterministically. ``is_reference_authenticator
    = True`` and **production composition refuses it** — wiring it into production
    would reopen the telemetry trust boundary. It nonetheless still rejects an
    observation with no ``source`` (a minimally malformed producer identity).
    """

    is_reference_authenticator = True

    def authenticate(self, obs: TrajectoryObservation) -> Tuple[bool, Tuple[str, ...]]:
        if not obs.source:
            return (False, ("missing telemetry source",))
        return (True, ())


class TrustedTelemetryIngress:
    """The trust gate an observation must pass before it can influence assessment.

    Composes an injected :class:`TelemetryAuthenticator` with binding validation
    and the expected-domain guard. In production mode a reference authenticator is
    refused at construction (F-1); the trust decision always precedes assessment.
    """

    def __init__(
        self,
        authenticator: TelemetryAuthenticator,
        *,
        production_mode: bool = False,
    ) -> None:
        if authenticator is None:
            raise ValueError(
                "TrustedTelemetryIngress requires a TelemetryAuthenticator (fail closed)"
            )
        if production_mode and getattr(
            authenticator, "is_reference_authenticator", False
        ):
            raise ReferenceIngressRejectedError(
                "reference TelemetryAuthenticator refused in production mode "
                "(spec §10/D7, RA-5/RA-6 F-1 symmetry): inject a real "
                "deployment-authenticated ingress"
            )
        self._authenticator = authenticator
        self._production_mode = production_mode

    @property
    def production_mode(self) -> bool:
        return self._production_mode

    def admit(
        self,
        obs: TrajectoryObservation,
        *,
        expected: Optional[ExpectedBinding] = None,
    ) -> IngressDecision:
        """Admit or reject one observation, fail-closed."""

        # A non-observation (defensive against a malformed producer) is ignored.
        if not isinstance(obs, TrajectoryObservation):
            return IngressDecision(
                IngressDisposition.REJECTED,
                AssessmentOutcome.IGNORE_EVENT,
                reasons=("not a TrajectoryObservation",),
            )

        # 1. Internal binding well-formedness (malformed ⇒ ignore).
        binding_errors = obs.binding_errors()
        if binding_errors:
            return IngressDecision(
                IngressDisposition.REJECTED,
                AssessmentOutcome.IGNORE_EVENT,
                reasons=("malformed observation",) + binding_errors,
            )

        # 2. Expected authority-domain guard (wrong tenant/workflow/envelope ⇒ reject; I7).
        if expected is not None:
            mismatches = expected.mismatches(obs)
            if mismatches:
                return IngressDecision(
                    IngressDisposition.REJECTED,
                    AssessmentOutcome.IGNORE_EVENT,
                    reasons=("binding mismatch",) + mismatches,
                )

        # 3. Producer authentication (untrusted ⇒ reject at the seam).
        try:
            authed, reasons = self._authenticator.authenticate(obs)
        except Exception as exc:  # noqa: BLE001 - an authenticator fault fails closed
            return IngressDecision(
                IngressDisposition.REJECTED,
                AssessmentOutcome.IGNORE_EVENT,
                reasons=("authenticator error", repr(exc)),
            )
        # Guard a malformed authenticator return: only an exact ``True`` admits.
        if authed is not True:
            return IngressDecision(
                IngressDisposition.REJECTED,
                AssessmentOutcome.IGNORE_EVENT,
                reasons=("untrusted producer",) + tuple(reasons or ()),
            )

        return IngressDecision(
            IngressDisposition.ADMITTED,
            AssessmentOutcome.NO_SIGNAL,
            observation=obs,
        )
