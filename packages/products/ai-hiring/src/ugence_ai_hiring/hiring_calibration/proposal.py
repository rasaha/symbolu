"""Calibration proposal generation, provenance, and governed recompile.

Calibration **never** directly modifies weights, gates, thresholds, or model
parameters. It emits a governed :class:`CalibrationProposal` describing a
*proposed* change to a future policy version. An approved proposal is routed back
through the Step-1 :class:`HiringPolicyCompiler` on a human-edited policy,
producing a **new** versioned ``HiringWorkflowIR`` and ``HiringDecisionContract``
— the active contract is never mutated in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..domain.base import DomainModel
from ..hiring_decision.enums import CalibrationTarget
from ..hiring_decision.refs import ContractRef
from ..hiring_decision.reviews import CalibrationProposal
from ..hiring_policy.compiler import HiringPolicyCompiler
from ..hiring_policy.contract import HiringDecisionContract, project_contract
from ..hiring_policy.enums import LifecycleStatus
from ..hiring_policy.policy import HiringPolicy
from ..hiring_policy.signing import Signer
from ..hiring_policy.workflow_ir import HiringWorkflowIR
from .enums import CalibrationDirection, ProposalStatus
from .errors import CalibrationApprovalError, NoCalibrationSignalError
from .report import HiringCalibrationReport

# A calibration cell must exceed this |delta| to count as a systematic signal.
SIGNAL_DELTA = 10.0


class CalibrationProvenance(DomainModel):
    """Explicit provenance chain:

    decision cases → execution receipts → post-hire reviews → calibration report
    → calibration proposal → next policy/contract version.
    """

    decision_case_ids: tuple[str, ...]
    execution_receipt_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    report_id: str
    proposal_id: str
    current_contract_ref: ContractRef
    next_contract_version: int


def build_provenance(
    report: HiringCalibrationReport, proposal: CalibrationProposal
) -> CalibrationProvenance:
    return CalibrationProvenance(
        decision_case_ids=report.case_ids,
        execution_receipt_ids=report.receipt_ids,
        review_ids=report.review_ids,
        report_id=report.report_id,
        proposal_id=proposal.proposal_id,
        current_contract_ref=proposal.contract_ref,
        next_contract_version=proposal.proposed_contract_version,
    )


def generate_calibration_proposal(
    report: HiringCalibrationReport,
    *,
    required_approver: str,
    policy_id: str,
) -> CalibrationProposal:
    """Derive a governed proposal from a report's deltas + missing-evidence patterns.

    Reads calibration error and missing evidence only — never the Overall Fit
    Index. Raises :class:`NoCalibrationSignalError` when nothing warrants a change.
    """
    targets: set[CalibrationTarget] = set()
    findings: list[str] = []

    # Systematic over/underprediction → threshold/weight change.
    over_under: dict[str, list[str]] = {}
    for d in report.deltas:
        if d.delta is not None and abs(d.delta) >= SIGNAL_DELTA and d.direction in (
            CalibrationDirection.OVERPREDICTION,
            CalibrationDirection.UNDERPREDICTION,
        ):
            over_under.setdefault(d.dimension, []).append(
                f"{d.horizon.value}/{d.confidence_band.value} Δ={d.delta:+.1f}"
            )
    for dim, cells in sorted(over_under.items()):
        targets.add(CalibrationTarget.CONFIDENCE_THRESHOLDS)
        targets.add(CalibrationTarget.DIMENSION_WEIGHTS)
        findings.append(f"{dim}: systematic miscalibration [{'; '.join(cells)}]")

    # Persistent missing evidence → evidence-requirement change.
    for dim, count in sorted(report.missing_evidence.items()):
        if count >= 1:
            targets.add(CalibrationTarget.EVIDENCE_REQUIREMENTS)
            findings.append(f"{dim}: {count} missing-evidence observation(s)")

    if not targets:
        raise NoCalibrationSignalError(
            "no systematic calibration signal in this cohort; no policy change proposed"
        )

    ck = report.cohort_key
    contract_ref = ContractRef(
        contract_id=ck.contract_id, version=ck.contract_version, ir_digest=ck.ir_digest
    )
    next_version = ck.contract_version + 1
    rationale = "Cohort calibration signal: " + "; ".join(findings)
    proposed_change = "Proposed targets: " + ", ".join(sorted(t.value for t in targets))
    impact_summary = (
        f"Affects role {ck.role_id} policy {policy_id}; recompile contract "
        f"{ck.contract_id} v{ck.contract_version} → v{next_version}. Advisory only until approved."
    )

    return CalibrationProposal(
        source_case_id=report.case_ids[0],
        source_case_ids=report.case_ids,
        contract_ref=contract_ref,
        targets=tuple(sorted(targets, key=lambda t: t.value)),
        rationale=rationale,
        recompile_policy_id=policy_id,
        proposed_contract_version=next_version,
        status=ProposalStatus.PROPOSED.value,
        affected_role_id=ck.role_id,
        report_id=report.report_id,
        supporting_evidence=(report.report_id, *report.review_ids, *report.receipt_ids),
        proposed_change=proposed_change,
        impact_summary=impact_summary,
        required_approver=required_approver,
    )


@dataclass(frozen=True)
class RecompileResult:
    workflow_ir: HiringWorkflowIR
    contract: HiringDecisionContract
    proposal: CalibrationProposal
    provenance: Optional[CalibrationProvenance] = None


class CalibrationApprovalService:
    """Governs approval and the recompile back through the Step-1 PWC."""

    def __init__(self, compiler: Optional[HiringPolicyCompiler] = None) -> None:
        self._compiler = compiler or HiringPolicyCompiler()

    def approve(self, proposal: CalibrationProposal, *, approver: str) -> CalibrationProposal:
        if proposal.status not in (ProposalStatus.PROPOSED.value, ProposalStatus.IN_REVIEW.value):
            raise CalibrationApprovalError(
                f"cannot approve a proposal in status {proposal.status!r}"
            )
        if proposal.required_approver and approver != proposal.required_approver:
            raise CalibrationApprovalError(
                f"approver {approver!r} is not the required approver "
                f"{proposal.required_approver!r}"
            )
        return proposal.model_copy(
            update={"status": ProposalStatus.APPROVED.value, "approved_by": approver}
        )

    def reject(self, proposal: CalibrationProposal, *, approver: str) -> CalibrationProposal:
        return proposal.model_copy(
            update={"status": ProposalStatus.REJECTED.value, "approved_by": approver}
        )

    def recompile(
        self,
        proposal: CalibrationProposal,
        updated_policy: HiringPolicy,
        *,
        job_definition_id: str,
        report: Optional[HiringCalibrationReport] = None,
        signer: Optional[Signer] = None,
        status: LifecycleStatus = LifecycleStatus.PUBLISHED,
    ) -> RecompileResult:
        """Recompile an APPROVED proposal's human-edited policy into a NEW version.

        Enforces approval-before-recompile, policy identity, and version
        advancement. Produces new artifacts; never mutates the active contract.
        """
        if proposal.status != ProposalStatus.APPROVED.value:
            raise CalibrationApprovalError(
                "recompile requires an APPROVED proposal (no automatic policy mutation)"
            )
        if updated_policy.policy_id != proposal.recompile_policy_id:
            raise CalibrationApprovalError(
                "updated policy id does not match the proposal's recompile_policy_id"
            )

        new_ir = self._compiler.compile(updated_policy)
        new_contract = project_contract(
            new_ir,
            job_definition_id=job_definition_id,
            version=proposal.proposed_contract_version,
            status=status,
            signer=signer,
        )
        if new_contract.version <= proposal.contract_ref.version:
            raise CalibrationApprovalError(
                "recompiled contract must advance the version"
            )

        recompiled = proposal.model_copy(update={"status": ProposalStatus.RECOMPILED.value})
        provenance = build_provenance(report, recompiled) if report is not None else None
        return RecompileResult(
            workflow_ir=new_ir,
            contract=new_contract,
            proposal=recompiled,
            provenance=provenance,
        )
