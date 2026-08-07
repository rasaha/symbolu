"""Eligibility — derived only from mandatory gates and contract requirements.

Compatibility scores and the Overall Fit Index must never determine eligibility.
This module imports neither the assessment scores nor the analytics plane; its
sole inputs are gate results and the contract reference. That is the structural
enforcement of *Compatibility ≠ Eligibility*.
"""

from __future__ import annotations

from ..domain.base import DomainModel
from .enums import EligibilityStatus, GateState
from .gates import GateResult
from .refs import ContractRef


class Eligibility(DomainModel):
    """Non-compensatory eligibility determination over mandatory gates only."""

    status: EligibilityStatus
    contract_ref: ContractRef
    evaluated_gate_ids: tuple[str, ...] = ()
    blocking_gate_ids: tuple[str, ...] = ()


def derive_eligibility(
    gate_results: tuple[GateResult, ...], contract_ref: ContractRef
) -> Eligibility:
    """Derive eligibility from gate results alone (no scores, no Overall Fit).

    - any FAIL              → NOT_ELIGIBLE (blocked by the failed gates)
    - else any INDETERMINATE → ELIGIBILITY_PENDING (blocked, fail-closed)
    - else                  → ELIGIBLE
    """
    evaluated = tuple(g.gate_id for g in gate_results)
    failed = tuple(g.gate_id for g in gate_results if g.state is GateState.FAIL)
    indeterminate = tuple(g.gate_id for g in gate_results if g.state is GateState.INDETERMINATE)

    if failed:
        status = EligibilityStatus.NOT_ELIGIBLE
        blocking = failed
    elif indeterminate:
        status = EligibilityStatus.ELIGIBILITY_PENDING
        blocking = indeterminate
    else:
        status = EligibilityStatus.ELIGIBLE
        blocking = ()

    return Eligibility(
        status=status,
        contract_ref=contract_ref,
        evaluated_gate_ids=evaluated,
        blocking_gate_ids=blocking,
    )
