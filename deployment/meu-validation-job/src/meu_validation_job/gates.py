"""The ordered preconditions, evaluated every run and reported whatever the mode.

Each gate is evaluated even when an earlier one blocked, because an operator reading the
report wants to know everything that is outstanding, not just the first thing. What the
gates *authorize* is strictly ordered, though: credential materialization needs the
posture and the designation; a genuine call needs all five.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Tuple

from ugence_model_egress_custody_gcp import DesignationRefused, check_designation_accepted
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

__all__ = ["GATES", "GateOutcome", "GateReport", "evaluate_gates"]

EXECUTION_POSTURE = "EXECUTION_POSTURE"
STEP8_DESIGNATION = "STEP8_DESIGNATION"
LIVE_AUTHORIZATION = "LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION"
COMMISSIONING_CEILINGS = "COMMISSIONING_CEILINGS"
LIVE_TRANSPORT = "LIVE_TRANSPORT"

#: In the order a run must satisfy them.
GATES: Tuple[str, ...] = (EXECUTION_POSTURE, STEP8_DESIGNATION, LIVE_AUTHORIZATION,
                          COMMISSIONING_CEILINGS, LIVE_TRANSPORT)

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

    def status(self, gate: str) -> str:
        return next(o.status for o in self.outcomes if o.gate == gate)

    @property
    def blocked(self) -> Tuple[str, ...]:
        return tuple(o.gate for o in self.outcomes if o.status != PASSED)

    @property
    def may_materialize_a_credential(self) -> bool:
        """Posture, designation AND the canonical authorization.

        The authorization gates materialization and not only dispatch, because there is
        no reason to read the real provider credential except to make the authorized
        call: a run that may not call may not read. Requiring it here means a lapse in
        the dispatch path cannot turn into a credential that was fetched anyway.
        """

        return all(self.status(g) == PASSED
                   for g in (EXECUTION_POSTURE, STEP8_DESIGNATION, LIVE_AUTHORIZATION))

    @property
    def may_dispatch_a_genuine_call(self) -> bool:
        return all(o.status == PASSED for o in self.outcomes)

    def as_record(self) -> list:
        return [o.as_record() for o in self.outcomes]


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


def _designation(designation_record: Mapping[str, Any]) -> GateOutcome:
    try:
        accepted = check_designation_accepted((designation_record or {}).get("step8_required_values"))
    except DesignationRefused as refused:
        return GateOutcome(STEP8_DESIGNATION, BLOCKED, str(refused))
    return GateOutcome(STEP8_DESIGNATION, PASSED,
                       f"seventeen obligations supplied and independently verified by {accepted.attested_by}")


def _authorization(validation_record: Mapping[str, Any],
                   authorization_record: Optional[Mapping[str, Any]]) -> GateOutcome:
    pinned = (validation_record or {}).get("live_synthetic_validation_authorization")
    if pinned in (None, "", NOT_GIVEN):
        return GateOutcome(LIVE_AUTHORIZATION, BLOCKED,
                           "the canonical record pins no authorization (NOT_GIVEN); a genuine call needs the "
                           "owner's typed, immutable, consumable LiveSyntheticValidationAuthorization "
                           "(commissioning ADR §0.6)")
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
    return GateOutcome(LIVE_AUTHORIZATION, PASSED,
                       f"the canonical authorization is present for {authorization.max_calls} call(s)")


def _ceilings(config, authorization_record: Optional[Mapping[str, Any]]) -> GateOutcome:
    limits = COMMISSIONING_LIMITS
    if config.endpoint != OPENAI_RESPONSES.url:
        return GateOutcome(COMMISSIONING_CEILINGS, BLOCKED,
                           f"the endpoint is not the one designated destination {OPENAI_RESPONSES.url}")
    ceilings = (f"synthetic non-sensitive input only; at most {limits.max_genuine_calls} calls; "
                f"USD {limits.budget_usd_cents / 100:.0f}; concurrency {limits.concurrency}; "
                f"{limits.max_input_tokens} input and {limits.max_output_tokens} output tokens; "
                f"store={limits.store}; tools={limits.tools}; streaming={limits.streaming}; "
                f"background={limits.background}")
    if authorization_record is not None:
        for field_name, ceiling in (("max_calls", limits.max_genuine_calls),
                                    ("budget_usd_cents", limits.budget_usd_cents),
                                    ("max_input_tokens", limits.max_input_tokens),
                                    ("max_output_tokens", limits.max_output_tokens),
                                    ("concurrency", limits.concurrency),
                                    ("max_retries", limits.max_retries)):
            value = authorization_record.get(field_name)
            if isinstance(value, int) and value > ceiling:
                return GateOutcome(COMMISSIONING_CEILINGS, BLOCKED,
                                   f"the authorization's {field_name} exceeds the commissioning ceiling "
                                   f"({value} > {ceiling}); a limit an authorization could raise is not a limit")
        if authorization_record.get("synthetic_non_sensitive_only") is not True:
            return GateOutcome(COMMISSIONING_CEILINGS, BLOCKED,
                               "the authorization does not declare synthetic_non_sensitive_only")
    return GateOutcome(COMMISSIONING_CEILINGS, PASSED, ceilings)


def _transport() -> GateOutcome:
    if GENUINE_DISPATCH_IMPLEMENTED or LIVE_VENDOR_EGRESS:  # pragma: no cover - both are False in this slice
        return GateOutcome(LIVE_TRANSPORT, PASSED, "a live transport exists")
    return GateOutcome(LIVE_TRANSPORT, BLOCKED,
                       "no live Responses transport exists in any installed distribution and "
                       "LIVE_VENDOR_EGRESS is False; the genuine dispatch path is the next slice")


def evaluate_gates(config, *, designation_record: Mapping[str, Any],
                   validation_record: Mapping[str, Any],
                   authorization_record: Optional[Mapping[str, Any]] = None,
                   variables: Mapping[str, str], now: datetime) -> GateReport:
    """Every gate, in order, each evaluated whether or not an earlier one blocked."""

    return GateReport((
        _posture(config, variables),
        _designation(designation_record),
        _authorization(validation_record, authorization_record),
        _ceilings(config, authorization_record),
        _transport(),
    ))
