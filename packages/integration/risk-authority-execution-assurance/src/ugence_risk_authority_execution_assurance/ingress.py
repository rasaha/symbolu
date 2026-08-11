"""Trusted effect-observation ingress (spec §4/D-A, §10, §18, §19, §29, §30).

The external effect source is a **trust boundary**. The trust decision happens
*before* reconciliation. Producer authentication is delegated to a deployment
ingress seam (Option B) — mirroring RA-5 trusted-evidence ingress and RA-6/RA-7
F-1. The reference milestone does **NOT** claim per-receipt cryptographic signing
(that would be an overclaim; no such signing exists — spec §4, §19: integrity ≠
authenticity, hash ≠ signature).

An admission does four things, fail-closed and never authority-widening:

  1. rejects a non-``EffectObservation`` and a malformed one (exact type checks);
  2. authenticates the *producer* via the injected :class:`EffectSourceAuthenticator`
     (deployment-owned; the reference stand-in is refused in production, F-1);
  3. checks the observation binds to the *expected* governed execution — the
     intrinsic-tuple guard (wrong tenant/workflow/envelope/action/attempt; §18);
  4. yields a normalized, admitted :class:`~.contracts.EffectObservation`.

A rejected observation yields ``REJECTED`` and can never become a reconciliation
record, touch another authority domain, or mint/widen authority. An absent effect
source yields ``UNVERIFIABLE`` at the assessment layer — never ``MATCHED`` (§27).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Tuple, runtime_checkable

from ugence_decision_authority.execution.status import BusinessOutcome, Finality
from ugence_governance_contracts.contracts.execution import (
    ExecutionBusinessOutcome,
    ExecutionObservation,
)

from .contracts import EXECUTION_ASSURANCE_SCHEMA_VERSION, EffectObservation
from .correlation import ExecutionCorrelator
from .contracts import ExecutionCorrelation

__all__ = [
    "IngressDisposition",
    "IngressDecision",
    "EffectSourceAuthenticator",
    "ReferenceEffectSourceAuthenticator",
    "ReferenceEffectIngressRejectedError",
    "TrustedEffectIngress",
    "normalize_execution_observation",
    "GOVERNANCE_OUTCOME_TO_BUSINESS_OUTCOME",
]


class ReferenceEffectIngressRejectedError(RuntimeError):
    """Raised when a reference effect authenticator is wired into production (F-1)."""


class IngressDisposition(str, Enum):
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class IngressDecision:
    """The audited result of an effect-observation admission — carries no authority."""

    disposition: IngressDisposition
    reasons: Tuple[str, ...] = ()
    observation: Optional[EffectObservation] = None

    @property
    def admitted(self) -> bool:
        return self.disposition is IngressDisposition.ADMITTED


@runtime_checkable
class EffectSourceAuthenticator(Protocol):
    """Authenticate an effect-source producer (spec §4/D-A, Option B).

    Returns ``(authenticated, reasons)``. Identity is established out of band by the
    deployment (mTLS / workload identity / delegated ingress token); the seam only
    *carries* the decision. ``is_reference_authenticator`` marks a conformance
    stand-in production must refuse.
    """

    is_reference_authenticator: bool

    def authenticate(self, obs: EffectObservation) -> Tuple[bool, Tuple[str, ...]]:
        ...


class ReferenceEffectSourceAuthenticator:
    """Reference authenticator — trusts any observation carrying a ``source`` (§4/§19).

    This performs NO real producer authentication: it exists so the ingress →
    reconcile flow is exercisable deterministically. ``is_reference_authenticator =
    True`` and **production composition refuses it** (F-1) — wiring it into
    production would let untrusted external effects become trusted reconciliation
    evidence. It still rejects an observation with no ``source`` (a minimally
    malformed producer identity).
    """

    is_reference_authenticator = True

    def authenticate(self, obs: EffectObservation) -> Tuple[bool, Tuple[str, ...]]:
        if not getattr(obs, "source", ""):
            return (False, ("missing effect source",))
        return (True, ())


#: Deterministic map from the neutral governance-contracts effect outcome to the DA
#: ``BusinessOutcome`` (spec §12 — reuse the existing seam; no parallel set).
GOVERNANCE_OUTCOME_TO_BUSINESS_OUTCOME: dict[ExecutionBusinessOutcome, BusinessOutcome] = {
    ExecutionBusinessOutcome.SUCCEEDED: BusinessOutcome.SUCCEEDED,
    ExecutionBusinessOutcome.FAILED: BusinessOutcome.FAILED,
    ExecutionBusinessOutcome.REJECTED: BusinessOutcome.REJECTED,
    ExecutionBusinessOutcome.PENDING: BusinessOutcome.UNKNOWN,
    ExecutionBusinessOutcome.DUPLICATE: BusinessOutcome.DUPLICATE,
    ExecutionBusinessOutcome.UNKNOWN: BusinessOutcome.UNKNOWN,
}


def normalize_execution_observation(
    gov_obs: ExecutionObservation,
    correlation: ExecutionCorrelation,
    *,
    observation_id: str,
    external_request_id: str = "",
    external_effect_id: str = "",
    source: str = "",
    source_version: str = "",
) -> EffectObservation:
    """Normalize a governance-contracts ``ExecutionObservation`` into an ``EffectObservation``.

    Reuses the neutral effect-observation seam (spec §4/D-A, §12): the binding
    fields come from the governed correlation (never from the untrusted producer),
    and the observed business outcome / finality come from the effect source. A
    ``PENDING`` producer outcome maps to ``UNKNOWN`` business outcome + ``NON_FINAL``
    finality — never fabricated into success.
    """

    outcome = GOVERNANCE_OUTCOME_TO_BUSINESS_OUTCOME.get(
        gov_obs.business_outcome, BusinessOutcome.UNKNOWN
    )
    if gov_obs.business_outcome is ExecutionBusinessOutcome.PENDING:
        finality = Finality.NON_FINAL
    else:
        finality = Finality.FINAL if gov_obs.final is True else Finality.NON_FINAL
    return EffectObservation(
        schema_version=EXECUTION_ASSURANCE_SCHEMA_VERSION,
        observation_id=observation_id,
        tenant_id=correlation.tenant_id,
        workflow_instance_id=correlation.workflow_instance_id,
        envelope_id=correlation.envelope_id,
        authorized_action_digest=correlation.authorized_action_digest,
        attempt_id=correlation.attempt_id,
        external_request_id=external_request_id or correlation.external_request_id,
        business_outcome=outcome,
        provider=correlation.provider,
        external_effect_id=external_effect_id or gov_obs.provider_trace_id,
        observed_parameters=dict(gov_obs.observed_parameters),
        finality=finality,
        source=source,
        source_version=source_version,
    )


class TrustedEffectIngress:
    """The trust gate an effect observation must pass before it can be reconciled.

    Composes an injected :class:`EffectSourceAuthenticator` with binding validation
    and the intrinsic-domain guard. In production mode a reference authenticator is
    refused at construction (F-1); the trust decision always precedes reconciliation.
    """

    def __init__(
        self,
        authenticator: EffectSourceAuthenticator,
        *,
        production_mode: bool = False,
        correlator: Optional[ExecutionCorrelator] = None,
    ) -> None:
        if authenticator is None:
            raise ValueError(
                "TrustedEffectIngress requires an EffectSourceAuthenticator (fail closed)"
            )
        if production_mode and getattr(
            authenticator, "is_reference_authenticator", False
        ):
            raise ReferenceEffectIngressRejectedError(
                "reference EffectSourceAuthenticator refused in production mode "
                "(spec §4/D-A, §19, RA-5/RA-6/RA-7 F-1 symmetry): inject a real "
                "deployment-authenticated effect ingress"
            )
        self._authenticator = authenticator
        self._production_mode = production_mode
        self._correlator = correlator or ExecutionCorrelator()

    @property
    def production_mode(self) -> bool:
        return self._production_mode

    def admit(
        self,
        obs: EffectObservation,
        *,
        correlation: ExecutionCorrelation,
    ) -> IngressDecision:
        """Admit or reject one effect observation against a governed correlation."""

        # 0. A non-observation (defensive against a malformed producer) is rejected.
        if not isinstance(obs, EffectObservation):
            return IngressDecision(
                IngressDisposition.REJECTED, reasons=("not an EffectObservation",)
            )
        if not isinstance(correlation, ExecutionCorrelation):
            return IngressDecision(
                IngressDisposition.REJECTED, reasons=("not an ExecutionCorrelation",)
            )

        # 1. Internal binding well-formedness (malformed ⇒ reject).
        binding_errors = obs.binding_errors()
        if binding_errors:
            return IngressDecision(
                IngressDisposition.REJECTED,
                reasons=("malformed observation",) + binding_errors,
            )

        # 2. Intrinsic domain guard (wrong tenant/workflow/envelope/action/attempt ⇒
        #    reject; I9/§18). Storage partitioning alone is insufficient.
        mismatches = self._correlator.binding_mismatches(correlation, obs)
        if mismatches:
            return IngressDecision(
                IngressDisposition.REJECTED,
                reasons=("binding mismatch",) + mismatches,
            )

        # 3. Producer authentication (untrusted ⇒ reject at the seam).
        try:
            authed, reasons = self._authenticator.authenticate(obs)
        except Exception as exc:  # noqa: BLE001 - an authenticator fault fails closed
            return IngressDecision(
                IngressDisposition.REJECTED,
                reasons=("authenticator error", repr(exc)),
            )
        # Guard a malformed authenticator return: only an exact ``True`` admits
        # (spec §29 — None/1/"true"/() must never be treated as authenticated).
        if authed is not True:
            return IngressDecision(
                IngressDisposition.REJECTED,
                reasons=("untrusted producer",) + tuple(reasons or ()),
            )

        return IngressDecision(IngressDisposition.ADMITTED, observation=obs)
