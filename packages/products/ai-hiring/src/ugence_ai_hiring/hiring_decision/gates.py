"""Deterministic mandatory-gate evaluation over admitted evidence only.

Fail-closed: a gate with no admitted deciding evidence is ``INDETERMINATE`` and
blocks eligibility. Unadmitted evidence is ignored entirely, so it can never
satisfy a gate. This is a pure, deterministic function of (contract gates,
admitted evidence) — it reads no scores and no Overall Fit Index.
"""

from __future__ import annotations

from pydantic import model_validator

from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..hiring_policy.enums import MandatoryGateType
from ..hiring_policy.workflow_ir import MandatoryGate
from .enums import GateState
from .evidence import AdmittedEvidence

# Each gate type decides on a single canonical boolean fact carried by admitted
# evidence of the gate's declared evidence classes.
GATE_ATTRIBUTE_KEY: dict[MandatoryGateType, str] = {
    MandatoryGateType.REQUIRED_SKILLS: "required_skills_met",
    MandatoryGateType.REQUIRED_CERTIFICATIONS: "certifications_verified",
    MandatoryGateType.WORK_AUTHORIZATION: "work_authorized",
    MandatoryGateType.SECURITY_CLEARANCE: "clearance_active",
    MandatoryGateType.INTERVIEW_COMPLETED: "interview_completed",
    MandatoryGateType.ASSESSMENT_COMPLETED: "assessment_completed",
    MandatoryGateType.REQUIRED_EXPERIENCE: "required_experience_met",
}


class GateResult(DomainModel):
    """The evaluated state of one mandatory gate."""

    gate_id: str
    gate_type: MandatoryGateType
    state: GateState
    deciding_evidence: tuple[str, ...] = ()
    reason: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "GateResult":
        if not self.gate_id.strip():
            raise DomainValidationError("gate_id is required")
        return self


class MandatoryGateEvaluator:
    """Evaluates a contract's mandatory gates against admitted evidence."""

    def evaluate(
        self,
        gates: tuple[MandatoryGate, ...],
        admitted_evidence: tuple[AdmittedEvidence, ...],
    ) -> tuple[GateResult, ...]:
        # Only admitted evidence is ever considered.
        admitted = tuple(e for e in admitted_evidence if e.admitted)
        return tuple(self._evaluate_one(gate, admitted) for gate in gates)

    def _evaluate_one(
        self, gate: MandatoryGate, admitted: tuple[AdmittedEvidence, ...]
    ) -> GateResult:
        key = GATE_ATTRIBUTE_KEY[gate.gate_type]
        allowed_classes = set(gate.predicate.evidence_types)
        deciding = [
            e
            for e in admitted
            if e.evidence_class in allowed_classes and key in e.attributes
        ]
        if not deciding:
            return GateResult(
                gate_id=gate.gate_id,
                gate_type=gate.gate_type,
                state=GateState.INDETERMINATE,
                deciding_evidence=(),
                reason=(
                    "no admitted deciding evidence "
                    f"(need {sorted(c.value for c in allowed_classes)} asserting {key!r})"
                ),
            )
        values = [bool(e.attributes[key]) for e in deciding]
        ids = tuple(e.lineage_node_id for e in deciding)
        if all(values):
            return GateResult(
                gate_id=gate.gate_id,
                gate_type=gate.gate_type,
                state=GateState.PASS,
                deciding_evidence=ids,
                reason=f"{key} satisfied by admitted evidence",
            )
        return GateResult(
            gate_id=gate.gate_id,
            gate_type=gate.gate_type,
            state=GateState.FAIL,
            deciding_evidence=ids,
            reason=f"{key} not satisfied by admitted evidence",
        )
