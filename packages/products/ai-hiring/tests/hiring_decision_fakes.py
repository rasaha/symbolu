"""Deterministic in-test fakes for the shared-capability ports.

These let the ai-hiring package run standalone: the decision plane depends only
on the port Protocols, and these fakes satisfy them without importing any shared
Ugence service. They are test doubles, not the real capabilities.
"""

from __future__ import annotations

from ugence_ai_hiring.hiring_decision.action_request import HiringActionSnapshot
from ugence_ai_hiring.hiring_decision.enums import (
    ActionAuthorizationVerdict,
    AssuranceResult,
    DecisionDisposition,
    ExecutionStatus,
    Trajectory,
)
from ugence_ai_hiring.hiring_decision.ports import (
    ActionAuthorizationOutcome,
    AdmissionOutcome,
    AssuranceCheckResult,
    AssuranceOutcome,
    DecisionAuthorityOutcome,
    EvidenceSubmission,
    ExecutionOutcome,
    ReconciliationOutcome,
)
from ugence_ai_hiring.hiring_decision.refs import ContractRef


class FakeEvidenceAdmissionPort:
    """Admits everything except evidence_ids listed in ``reject``."""

    def __init__(self, reject: frozenset[str] = frozenset()) -> None:
        self._reject = reject

    def admit(self, submissions: tuple[EvidenceSubmission, ...]) -> tuple[AdmissionOutcome, ...]:
        out = []
        for i, s in enumerate(submissions):
            admitted = s.evidence_id not in self._reject
            out.append(
                AdmissionOutcome(
                    evidence_id=s.evidence_id,
                    admitted=admitted,
                    lineage_node_id=f"ln-{s.evidence_id}",
                    reason="" if admitted else "rejected by fake TAP",
                )
            )
        return tuple(out)


class FakeDecisionAuthorityPort:
    """Binds with a fixed disposition and HUMAN authority (stand-in)."""

    def __init__(
        self,
        *,
        disposition: DecisionDisposition = DecisionDisposition.ADVANCE,
        binding: bool = True,
        authority_id: str = "hm-alex",
    ) -> None:
        self._disposition = disposition
        self._binding = binding
        self._authority_id = authority_id

    def adjudicate(self, recommendation_id: str, contract_ref: ContractRef) -> DecisionAuthorityOutcome:
        return DecisionAuthorityOutcome(
            recommendation_id=recommendation_id,
            disposition=self._disposition,
            binding=self._binding,
            authority_id=self._authority_id,
            rationale_job_related="fake DA decision",
        )


class FakeActionAuthorizationPort:
    def __init__(self, verdict: ActionAuthorizationVerdict = ActionAuthorizationVerdict.AUTHORIZED) -> None:
        self._verdict = verdict

    def authorize(self, cer_payload: dict) -> ActionAuthorizationOutcome:
        return ActionAuthorizationOutcome(verdict=self._verdict, reason="fake ActionGate")


class FakeRuntimeAssurancePort:
    def __init__(self, block: frozenset = frozenset()) -> None:
        self._block = block

    def assure(self, cer_payload: dict, checks) -> AssuranceOutcome:
        results = tuple(
            AssuranceCheckResult(check=c, passed=(c not in self._block)) for c in checks
        )
        result = AssuranceResult.ASSURED if all(r.passed for r in results) else AssuranceResult.BLOCKED
        return AssuranceOutcome(result=result, check_results=results)


class FakeReconciliationPort:
    def reconcile(self, case_id: str, review_record_id: str) -> ReconciliationOutcome:
        return ReconciliationOutcome(case_id=case_id, trajectory=Trajectory.ON_TRACK)


class FakeHRISExecutionPort:
    """Echoes the authorized action as executed (RECONCILED path) by default."""

    def __init__(
        self,
        *,
        status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
        mirror: bool = True,
        hris_state: dict | None = None,
    ) -> None:
        self._status = status
        self._mirror = mirror
        self._hris_state = {"worker_id": "W123"} if hris_state is None else hris_state

    def execute(self, cer_payload: dict) -> ExecutionOutcome:
        a = cer_payload["action"]
        executed = None
        if self._mirror and self._status is ExecutionStatus.SUCCEEDED:
            executed = HiringActionSnapshot(
                level=a["level"],
                salary=a["salary_ceiling"],
                salary_currency=a["currency"],
                role_id=cer_payload["subject"]["role_id"],
                location=a["location"],
                employment_type=a["employment_type"],
            )
        return ExecutionOutcome(
            execution_reference="hris-exec-1",
            status=self._status,
            result_digest="result-digest-1",
            executed_action=executed,
            hris_state=dict(self._hris_state),
        )
