"""Control-Assurance port (RA-5 spec §4, §5) — owned by ``risk_authority``.

Three distinct trust questions, three owners; they never blur (RA-5 §4):

* **Evidence Admission** — "may this evidence enter the assurance process?"
  (provenance / integrity / freshness) — behind :class:`EvidenceAdmissionPort`.
* **Control Assurance** — "does the admitted evidence satisfy control C?" — behind
  the :class:`ControlAssurancePort` defined *here*.
* **Risk Authority** — "given trusted results for required controls, what machine
  authority may be issued?" — keeps its non-compensatory aggregation rule
  (``domain.controls``) unchanged.

The port is deliberately provider-neutral, minimal, and stdlib-compatible: Risk
Authority depends only on this contract, never on a production evaluator. The
concrete evaluator (candidate: an adapted ``ugence-tap-provider``) is supplied by
the RA-5 integration package and injected. The port **consumes** admitted
evidence + a control identity + the exact control evaluation context, and
**produces** a trusted :class:`ControlResult`. It never produces a
``RiskDecision`` or an authorization envelope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional, Protocol, runtime_checkable

from ..domain.controls import ControlResult
from ..domain.enums import ControlStatus
from ..domain.evidence import ControlEvidenceRecord

__all__ = [
    "ControlAssuranceRequest",
    "ControlAssuranceResult",
    "ControlAssurancePort",
    "ControlAssuranceError",
    "ReferenceControlAssurance",
]


class ControlAssuranceError(Exception):
    """A Control-Assurance evaluator failure (fail-closed → UNKNOWN, §11)."""


@dataclass(frozen=True)
class ControlAssuranceRequest:
    """Everything an evaluator needs to assure exactly one control (RA-5 §8).

    Carries the binding tuple so the produced result can be intrinsically bound,
    and only *admitted* evidence (each item ``EvidenceState.ADMITTED`` and
    current) — the evaluator neither admits nor invents evidence.
    """

    tenant_id: str
    risk_case_id: str
    workflow_ir_digest: str
    policy_digest: str
    control_id: str
    subject_id: str
    admitted_evidence: tuple[ControlEvidenceRecord, ...]
    now: datetime
    context: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ControlAssuranceResult:
    """A trusted, intrinsically-bound control result plus evaluator attribution.

    The wrapped :class:`ControlResult` is the trusted artifact RA consumes; the
    surrounding fields record whether the evaluator actually ran (``available``)
    and its native detail, so the runtime can distinguish a genuine ``FAIL``
    (DENY) from an evaluator outage (ERROR_NON_EXECUTABLE) per §11.
    """

    control_result: ControlResult
    engine_id: str
    engine_version: str
    available: bool = True
    detail: str = ""
    raw_outcome: str = ""

    @property
    def status(self) -> ControlStatus:
        return self.control_result.status


@runtime_checkable
class ControlAssurancePort(Protocol):
    """Evaluate whether admitted evidence satisfies one required control."""

    def evaluate(self, request: ControlAssuranceRequest) -> ControlAssuranceResult: ...


def bind_control_result(
    request: ControlAssuranceRequest,
    *,
    status: ControlStatus,
    engine_id: str,
    engine_version: str,
    reason: str = "",
    valid_until: Optional[datetime] = None,
) -> ControlResult:
    """Construct a trusted :class:`ControlResult` bound to ``request``'s context.

    Freshness monotonicity (RA-5 §7.1): the result's ``valid_until`` is clamped to
    at most the earliest ``valid_until`` of its backing admitted evidence — a
    result may never outlive the evidence it rests on. ``evidence_ids`` are taken
    only from the admitted evidence actually supplied.
    """

    evidence_valids = [
        e.valid_until for e in request.admitted_evidence if e.valid_until is not None
    ]
    evidence_floor = min(evidence_valids) if evidence_valids else None
    if valid_until is None:
        effective_valid = evidence_floor
    elif evidence_floor is None:
        effective_valid = valid_until
    else:
        effective_valid = min(valid_until, evidence_floor)

    return ControlResult(
        control_id=request.control_id,
        status=status,
        evidence_ids=tuple(e.evidence_id for e in request.admitted_evidence),
        evaluated_at=request.now,
        valid_until=effective_valid,
        reason=reason,
        tenant_id=request.tenant_id,
        risk_case_id=request.risk_case_id,
        workflow_ir_digest=request.workflow_ir_digest,
        policy_digest=request.policy_digest,
        assurance_engine=engine_id,
        assurance_version=engine_version,
    )


class ReferenceControlAssurance:
    """A deterministic, stdlib-only reference evaluator (conformance mode).

    It is **not** the production evaluator (that is the TAP control-assurance
    adapter in the RA-5 integration package). It exists so the trusted-evidence
    production *flow* — admit → assure → bind → re-check → aggregate — can be
    exercised deterministically without a provider dependency.

    Fail-closed rules it honors, mirroring the ratified mapping (§9):

    * no admitted evidence for the control ⇒ ``MISSING`` (never PASS);
    * otherwise the status is taken from an explicit per-control oracle
      (``status_by_control``); absent an entry it defaults to ``PASS`` **only**
      because every supplied evidence item is admitted and current (the caller
      constructed a fully-supported reference scenario).

    The produced result is fully bound to the request context and its freshness
    is clamped to the backing evidence (§7.1).
    """

    def __init__(
        self,
        status_by_control: Optional[Mapping[str, ControlStatus]] = None,
        *,
        engine_id: str = "reference-control-assurance",
        engine_version: str = "1",
    ) -> None:
        self._status_by_control = dict(status_by_control or {})
        self._engine_id = engine_id
        self._engine_version = engine_version

    def evaluate(self, request: ControlAssuranceRequest) -> ControlAssuranceResult:
        current = [
            e
            for e in request.admitted_evidence
            if e.is_admitted() and e.is_current(request.now)
        ]
        if not current:
            result = bind_control_result(
                request,
                status=ControlStatus.MISSING,
                engine_id=self._engine_id,
                engine_version=self._engine_version,
                reason="no admitted, current evidence for control",
            )
            return ControlAssuranceResult(
                control_result=result,
                engine_id=self._engine_id,
                engine_version=self._engine_version,
                available=True,
                detail="missing_evidence",
                raw_outcome="MISSING",
            )

        status = self._status_by_control.get(request.control_id, ControlStatus.PASS)
        result = bind_control_result(
            request,
            status=status,
            engine_id=self._engine_id,
            engine_version=self._engine_version,
            reason=f"reference assurance status={status.value}",
        )
        return ControlAssuranceResult(
            control_result=result,
            engine_id=self._engine_id,
            engine_version=self._engine_version,
            available=True,
            detail="reference",
            raw_outcome=status.value,
        )
