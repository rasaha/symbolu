"""The ordered preconditions. The order is the enforcement, not a presentation choice.

The owner's correction of 2026-09-13 fixes the sequence, because the earlier version
reported the missing live transport first and that reads as "authorize it and it will
run". It is the other way round: the transport is the *last* thing outstanding, and a
run blocked on the designations must say so before it says anything about a transport.

    1. CONFIGURATION                    the configuration validates, and names exactly
                                        the one designated destination
    2. EXECUTION_POSTURE                not a developer machine, a browser, a CI runner,
                                        a shared host or a production workflow
    3. STEP8_DESIGNATIONS               all seventeen obligations supplied
    4. STEP8_INDEPENDENT_VERIFICATION   and someone other than the provisioner checked them
    5. LIVE_SYNTHETIC_VALIDATION_       the owner's separate explicit authorization for
       AUTHORIZATION                    this controlled live call, within the ceilings
    6. LIVE_VENDOR_EGRESS               the egress flag is enabled
    7. LIVE_TRANSPORT                   a live transport exists to dispatch with

Every gate is evaluated on every run so the report lists everything outstanding, but
what they *authorize* is strictly ordered, and :attr:`GateReport.first_blocked` is the
one a refusal leads with. Nothing is composed — no Google client, no custody adapter, no
transport — until gates 1 to 6 have passed; see :mod:`meu_validation_job.composition`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Tuple

from ugence_model_egress_custody_gcp import (
    designation_attestation_refusal, designation_completeness_refusal)
from ugence_model_egress_unit import (
    COMMISSIONING_LIMITS,
    LIVE_VENDOR_EGRESS,
    NOT_GIVEN,
    OPENAI_RESPONSES,
    PRODUCTION_FORM_CUSTODY_ADAPTER,
    ExecutionPosture,
    ExecutionPostureRefused,
    LiveSyntheticValidationAuthorization,
    check_execution_posture,
)

from .version import GENUINE_DISPATCH_IMPLEMENTED

__all__ = ["GATES", "GATES_BEFORE_COMPOSITION", "GateOutcome", "GateReport", "evaluate_gates",
           "CONFIGURATION", "EXECUTION_POSTURE", "STEP8_DESIGNATIONS",
           "STEP8_INDEPENDENT_VERIFICATION", "LIVE_AUTHORIZATION", "LIVE_EGRESS", "LIVE_TRANSPORT"]

CONFIGURATION = "CONFIGURATION"
EXECUTION_POSTURE = "EXECUTION_POSTURE"
STEP8_DESIGNATIONS = "STEP8_DESIGNATIONS"
STEP8_INDEPENDENT_VERIFICATION = "STEP8_INDEPENDENT_VERIFICATION"
LIVE_AUTHORIZATION = "LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION"
LIVE_EGRESS = "LIVE_VENDOR_EGRESS"
LIVE_TRANSPORT = "LIVE_TRANSPORT"

#: In the order a run must satisfy them. Index order is the refusal order.
GATES: Tuple[str, ...] = (CONFIGURATION, EXECUTION_POSTURE, STEP8_DESIGNATIONS,
                          STEP8_INDEPENDENT_VERIFICATION, LIVE_AUTHORIZATION,
                          LIVE_EGRESS, LIVE_TRANSPORT)

#: Every gate that must pass before ANY component is composed: before a Google client is
#: built, before a custody adapter exists, before a transport exists, and therefore
#: before any Secret Manager materialization can be attempted. The transport gate is not
#: among them, because composing the transport is what it guards.
GATES_BEFORE_COMPOSITION: Tuple[str, ...] = GATES[:GATES.index(LIVE_TRANSPORT)]

PASSED = "PASSED"
BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class GateOutcome:
    gate: str
    status: str
    reason: str = ""

    def as_record(self) -> dict:
        return {"gate": self.gate, "status": self.status, "reason": self.reason}


@dataclass(frozen=True)
class GateReport:
    outcomes: Tuple[GateOutcome, ...]

    def __post_init__(self) -> None:
        if tuple(o.gate for o in self.outcomes) != GATES:
            raise ValueError("a gate report carries every gate, in the order GATES declares")

    def status(self, gate: str) -> str:
        return next(o.status for o in self.outcomes if o.gate == gate)

    def reason(self, gate: str) -> str:
        return next(o.reason for o in self.outcomes if o.gate == gate)

    @property
    def blocked(self) -> Tuple[str, ...]:
        """Blocked gates, in GATES order."""

        return tuple(o.gate for o in self.outcomes if o.status != PASSED)

    @property
    def first_blocked(self) -> Optional[str]:
        """The earliest outstanding gate. This is what a refusal leads with."""

        return self.blocked[0] if self.blocked else None

    @property
    def may_compose_components(self) -> bool:
        """Whether a Google client, a custody adapter or a transport may be built at all."""

        return all(self.status(gate) == PASSED for gate in GATES_BEFORE_COMPOSITION)

    #: A credential is materialized only by a composed custody adapter, so the two
    #: questions have one answer: a run that may not compose may not read.
    may_materialize_a_credential = may_compose_components

    @property
    def may_dispatch_a_genuine_call(self) -> bool:
        return all(o.status == PASSED for o in self.outcomes)

    def as_record(self) -> list:
        return [o.as_record() for o in self.outcomes]


def _configuration(config) -> GateOutcome:
    """The configuration already validated itself at load; this records that, and
    re-checks the one value that decides where a call could ever go."""

    if config.endpoint != OPENAI_RESPONSES.url:
        return GateOutcome(CONFIGURATION, BLOCKED,
                           f"the endpoint is not the one designated destination {OPENAI_RESPONSES.url} (LP-3)")
    if str(config.environment).strip().lower() != "non-production":
        return GateOutcome(CONFIGURATION, BLOCKED,
                           "this job runs in the non-production commissioning scope only (LP-7, LP-8)")
    limits = COMMISSIONING_LIMITS
    return GateOutcome(CONFIGURATION, PASSED,
                       f"validated for {config.environment}, endpoint {config.endpoint}; ceilings: synthetic "
                       f"non-sensitive input only, at most {limits.max_genuine_calls} calls, "
                       f"USD {limits.budget_usd_cents // 100}, concurrency {limits.concurrency}, "
                       f"{limits.max_input_tokens}/{limits.max_output_tokens} tokens, store={limits.store}, "
                       f"tools={limits.tools}, streaming={limits.streaming}, background={limits.background}")


def _posture(config, variables: Mapping[str, str]) -> GateOutcome:
    try:
        check_execution_posture(ExecutionPosture(
            posture="DEPLOYED_MEU_INSTANCE",
            instance_reference=config.instance_reference,
            workload_identity_principal=config.workload_identity_principal,
            custody_adapter=PRODUCTION_FORM_CUSTODY_ADAPTER,
            environment=config.environment), variables=variables)
    except ExecutionPostureRefused as refused:
        return GateOutcome(EXECUTION_POSTURE, BLOCKED, str(refused))
    return GateOutcome(EXECUTION_POSTURE, PASSED,
                       "the deployed MEU instance, under its non-human workload identity, "
                       "through the production-form custody adapter, in a non-production environment")


def _designations(designation_record: Mapping[str, Any]) -> GateOutcome:
    why = designation_completeness_refusal((designation_record or {}).get("step8_required_values"))
    if why is not None:
        return GateOutcome(STEP8_DESIGNATIONS, BLOCKED, why)
    return GateOutcome(STEP8_DESIGNATIONS, PASSED, "all seventeen obligations are supplied")


def _independent_verification(designation_record: Mapping[str, Any]) -> GateOutcome:
    step8 = (designation_record or {}).get("step8_required_values")
    why = designation_attestation_refusal(step8)
    if why is not None:
        return GateOutcome(STEP8_INDEPENDENT_VERIFICATION, BLOCKED, why)
    checked_by = str(step8["attestation"]["independently_checked_by"]).strip()
    return GateOutcome(STEP8_INDEPENDENT_VERIFICATION, PASSED,
                       f"independently verified by {checked_by}")


def _authorization(validation_record: Mapping[str, Any],
                   authorization_record: Optional[Mapping[str, Any]]) -> GateOutcome:
    pinned = (validation_record or {}).get("live_synthetic_validation_authorization")
    if pinned in (None, "", NOT_GIVEN):
        return GateOutcome(LIVE_AUTHORIZATION, BLOCKED,
                           "the canonical record pins no authorization (NOT_GIVEN); a controlled live call needs "
                           "the owner's separate explicit, typed, immutable, consumable "
                           "LiveSyntheticValidationAuthorization (commissioning ADR §0.6)")
    if authorization_record is None:
        return GateOutcome(LIVE_AUTHORIZATION, BLOCKED,
                           "the canonical record pins an authorization digest but no authorization record was "
                           "supplied to this run")
    try:
        authorization = LiveSyntheticValidationAuthorization.from_record(authorization_record)
    except Exception as exc:  # noqa: BLE001 - a typed refusal, never the record's content
        return GateOutcome(LIVE_AUTHORIZATION, BLOCKED,
                           f"the authorization record is not a valid authorization ({type(exc).__name__})")
    if authorization.digest() != pinned:
        return GateOutcome(LIVE_AUTHORIZATION, BLOCKED,
                           "the supplied authorization is not the one the canonical record pins")
    if str(pinned) in list((validation_record or {}).get("revoked_authorization_digests") or []):
        return GateOutcome(LIVE_AUTHORIZATION, BLOCKED, "the pinned authorization is revoked")
    limits = COMMISSIONING_LIMITS
    for field_name, ceiling in (("max_calls", limits.max_genuine_calls),
                                ("budget_usd_cents", limits.budget_usd_cents),
                                ("max_input_tokens", limits.max_input_tokens),
                                ("max_output_tokens", limits.max_output_tokens),
                                ("concurrency", limits.concurrency),
                                ("max_retries", limits.max_retries)):
        value = getattr(authorization, field_name, None)
        if isinstance(value, int) and value > ceiling:
            return GateOutcome(LIVE_AUTHORIZATION, BLOCKED,
                               f"the authorization's {field_name} exceeds the commissioning ceiling "
                               f"({value} > {ceiling}); a limit an authorization could raise is not a limit")
    if authorization.synthetic_non_sensitive_only is not True:
        return GateOutcome(LIVE_AUTHORIZATION, BLOCKED,
                           "the authorization does not declare synthetic_non_sensitive_only")
    return GateOutcome(LIVE_AUTHORIZATION, PASSED,
                       f"the canonical authorization is present for exactly {authorization.max_calls} call(s), "
                       f"within every commissioning ceiling")


def _egress() -> GateOutcome:
    if LIVE_VENDOR_EGRESS is not True:
        return GateOutcome(LIVE_EGRESS, BLOCKED,
                           "LIVE_VENDOR_EGRESS is False: live vendor egress is not enabled in any installed "
                           "distribution, so no component that could reach a vendor may be composed")
    return GateOutcome(LIVE_EGRESS, PASSED, "live vendor egress is enabled")  # pragma: no cover


def _transport() -> GateOutcome:
    if GENUINE_DISPATCH_IMPLEMENTED:  # pragma: no cover - False in this slice
        return GateOutcome(LIVE_TRANSPORT, PASSED, "a live transport exists")
    return GateOutcome(LIVE_TRANSPORT, BLOCKED,
                       "no live Responses transport exists in any installed distribution; the genuine dispatch "
                       "path is the next slice and is not what an authorization unblocks")


def evaluate_gates(config, *, designation_record: Mapping[str, Any],
                   validation_record: Mapping[str, Any],
                   authorization_record: Optional[Mapping[str, Any]] = None,
                   variables: Mapping[str, str], now: datetime) -> GateReport:
    """Every gate, in order, each evaluated whether or not an earlier one blocked.

    Evaluating them all is what lets one run tell an operator everything outstanding.
    Acting on them is ordered: :attr:`GateReport.first_blocked` is the refusal, and
    :attr:`GateReport.may_compose_components` is false until gates 1 to 6 all pass.
    """

    return GateReport((
        _configuration(config),
        _posture(config, variables),
        _designations(designation_record),
        _independent_verification(designation_record),
        _authorization(validation_record, authorization_record),
        _egress(),
        _transport(),
    ))
