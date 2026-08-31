"""HiringDecisionService — the action-assurance orchestration spine.

Drives one completed, decided case through:

    build action request → ActionGate authorization → Runtime Assurance
    → HRIS execution handoff → Execution Receipt → Reconciliation

The orchestrator is thin: it sequences and enforces fail-closed guards, and it
reaches every shared capability through a port (TAP/DecisionAuthority upstream;
ActionAuthorization/RuntimeAssurance/HRISExecution/Reconciliation here). It
implements none of those engines.

Ordering is enforced structurally: :meth:`assure` accepts only an
``AuthorizedAction`` (produced solely by :meth:`authorize`), and :meth:`execute`
accepts only a ``ClearedAction`` (produced solely by :meth:`assure`). So runtime
assurance cannot run before authorization, and execution cannot run before
assurance.

Invariants: AI recommendation ≠ binding decision; eligibility ≠ authorization;
authorization ≠ operational clearance; authorized ≠ executed until reconciliation
proves equivalence. The Overall Fit Index is never read here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..common import utc_now
from ..hiring_policy.contract import HiringDecisionContract
from .action_request import CompensationBounds, HiringActionRequest, HiringActionSnapshot
from .decision_case import HiringDecisionCase
from .enums import (
    DecisionDisposition,
    EligibilityStatus,
    RecommendationDisposition,
)
from .errors import (
    ActionAuthorizationDenied,
    ContractBindingError,
    FailClosedError,
    PayloadMutationError,
    RuntimeAssuranceNotClear,
)
from .execution import (
    HiringExecutionReceipt,
    HiringReconciliationRecord,
    build_reconciliation_record,
)
from .ports import (
    ActionAuthorizationOutcome,
    ActionAuthorizationPort,
    AssuranceOutcome,
    ExecutionOutcome,
    HRISExecutionPort,
    ReconciliationPort,
    RuntimeAssurancePort,
)


@dataclass(frozen=True)
class AuthorizedAction:
    """Produced only by :meth:`HiringDecisionService.authorize`."""

    action_request: HiringActionRequest
    outcome: ActionAuthorizationOutcome
    authorized_digest: str
    authorized_at: datetime


@dataclass(frozen=True)
class ClearedAction:
    """Produced only by :meth:`HiringDecisionService.assure`."""

    authorized: AuthorizedAction
    assurance: AssuranceOutcome
    assured_at: datetime


@dataclass(frozen=True)
class ExecutionResult:
    receipt: HiringExecutionReceipt
    outcome: ExecutionOutcome
    authorized_action: HiringActionSnapshot


@dataclass(frozen=True)
class HiringSpineResult:
    action_request: HiringActionRequest
    receipt: HiringExecutionReceipt
    reconciliation: HiringReconciliationRecord


class HiringDecisionService:
    """Thin orchestrator over the shared-capability ports."""

    def __init__(
        self,
        *,
        action_authorization_port: ActionAuthorizationPort,
        runtime_assurance_port: RuntimeAssurancePort,
        execution_port: HRISExecutionPort,
        reconciliation_port: Optional[ReconciliationPort] = None,
    ) -> None:
        self._action_auth = action_authorization_port
        self._runtime = runtime_assurance_port
        self._execution = execution_port
        self._reconciliation = reconciliation_port

    # -- step 1/2: build the action request (fail-closed preconditions) ----
    def build_action_request(
        self, case: HiringDecisionCase, contract: HiringDecisionContract
    ) -> HiringActionRequest:
        # contract must be the one the case was decided under
        if (
            contract.compiled_from.ir_digest != case.contract_ref.ir_digest
            or contract.contract_id != case.contract_ref.contract_id
            or contract.version != case.contract_ref.version
        ):
            raise ContractBindingError("supplied contract does not match the case contract_ref")

        if case.decision is None:
            raise FailClosedError("no binding decision → no action request")
        if case.eligibility is None or case.eligibility.status is not EligibilityStatus.ELIGIBLE:
            status = None if case.eligibility is None else case.eligibility.status.value
            raise FailClosedError(f"not eligible ({status}) → no action")
        if case.recommendation is None:
            raise FailClosedError("no recommendation → no action")
        if case.recommendation.recommendation is not RecommendationDisposition.ADVANCE:
            raise FailClosedError(
                f"recommendation is {case.recommendation.recommendation.value} → no action"
            )
        if case.recommendation.proposed_action is None:
            raise FailClosedError("recommendation has no proposed action → no action")
        if case.decision.disposition is not DecisionDisposition.ADVANCE:
            raise FailClosedError(
                f"binding decision is {case.decision.disposition.value} → no action"
            )

        pa = case.recommendation.proposed_action
        comp = CompensationBounds(
            salary_ceiling=contract.action_constraints.salary_ceiling,
            currency=contract.action_constraints.salary_currency,
        )
        return HiringActionRequest(
            candidate_id=case.candidate_id,
            role_id=case.role_id,
            level=pa.level,
            compensation=comp,
            location=pa.location,
            employment_type=pa.employment_type,
            contract_ref=case.contract_ref,
            decision_id=case.decision.decision_id,
            recommendation_id=case.recommendation.recommendation_id,
        )

    # -- step 3: action authorization (ActionGate) -------------------------
    def authorize(
        self, action_request: HiringActionRequest, *, now: Optional[datetime] = None
    ) -> AuthorizedAction:
        digest = action_request.content_digest
        outcome = self._action_auth.authorize(action_request.to_cer_payload())
        if not outcome.is_authorized():
            raise ActionAuthorizationDenied(
                f"ActionGate denied ({outcome.verdict.value}): {outcome.reason}", outcome=outcome
            )
        if outcome.authorized_action_digest and outcome.authorized_action_digest != digest:
            raise PayloadMutationError(
                "ActionGate authorized a different action digest than presented"
            )
        return AuthorizedAction(action_request, outcome, digest, now or utc_now())

    # -- step 4: runtime assurance (only after authorization) --------------
    def assure(
        self,
        authorized: AuthorizedAction,
        checks: tuple,
        *,
        now: Optional[datetime] = None,
    ) -> ClearedAction:
        outcome = self._runtime.assure(authorized.action_request.to_cer_payload(), checks)
        if not outcome.is_clear():
            raise RuntimeAssuranceNotClear(
                f"runtime assurance not clear; failed={list(outcome.failed_checks())}",
                outcome=outcome,
            )
        return ClearedAction(authorized, outcome, now or utc_now())

    # -- step 5: execution handoff (only after auth AND assurance) ---------
    def execute(
        self,
        case: HiringDecisionCase,
        cleared: ClearedAction,
        *,
        actor: str,
        now: Optional[datetime] = None,
    ) -> ExecutionResult:
        ar = cleared.authorized.action_request
        # fail-closed: reject any mutation of the action after authorization
        if ar.content_digest != cleared.authorized.authorized_digest:
            raise PayloadMutationError("action payload mutated after authorization")

        outcome = self._execution.execute(ar.to_cer_payload())
        ts = now or utc_now()
        assert case.decision is not None  # guaranteed by build_action_request
        receipt = HiringExecutionReceipt(
            decision_case_id=case.case_id,
            contract_ref=case.contract_ref,
            binding_decision_id=case.decision.decision_id,
            binding_authority_id=case.decision.authority_id,
            action_request_id=ar.action_request_id,
            action_request_digest=ar.content_digest,
            authorization_ref=cleared.authorized.outcome.authorization_id or "authorized",
            assurance_ref=cleared.assurance.assurance_id or "assured",
            hris_execution_ref=outcome.execution_reference,
            actor=actor,
            authorized_at=cleared.authorized.authorized_at,
            assured_at=cleared.assured_at,
            executed_at=ts,
            execution_status=outcome.status,
            result_digest=outcome.result_digest,
        )
        return ExecutionResult(receipt=receipt, outcome=outcome, authorized_action=ar.snapshot())

    # -- step 7/8: reconciliation (local record; port is the shared engine) -
    def reconcile(
        self,
        case: HiringDecisionCase,
        execution_result: ExecutionResult,
        *,
        now: Optional[datetime] = None,
    ) -> HiringReconciliationRecord:
        external_ref: Optional[str] = None
        if self._reconciliation is not None:
            ext = self._reconciliation.reconcile(case.case_id, execution_result.receipt.receipt_id)
            external_ref = ext.calibration_proposal_id or f"recon:{ext.case_id}"
        return build_reconciliation_record(
            decision_case_id=case.case_id,
            contract_ref=case.contract_ref,
            receipt_id=execution_result.receipt.receipt_id,
            authorized_action=execution_result.authorized_action,
            outcome=execution_result.outcome,
            external_reconciliation_ref=external_ref,
            now=now,
        )

    # -- full spine --------------------------------------------------------
    def run(
        self,
        case: HiringDecisionCase,
        contract: HiringDecisionContract,
        *,
        actor: str,
        now: Optional[datetime] = None,
    ) -> HiringSpineResult:
        action_request = self.build_action_request(case, contract)
        authorized = self.authorize(action_request, now=now)
        cleared = self.assure(authorized, contract.runtime_assurance_checks, now=now)
        execution_result = self.execute(case, cleared, actor=actor, now=now)
        reconciliation = self.reconcile(case, execution_result, now=now)
        return HiringSpineResult(
            action_request=action_request,
            receipt=execution_result.receipt,
            reconciliation=reconciliation,
        )
