"""Authoritative trust-binding re-check for trusted control results (RA-5 §8).

Storage-partition isolation (the ``(tenant, case)`` dict key in
``persistence.in_memory``) is **insufficient**: a trusted :class:`ControlResult`
carries its own binding tuple and must be re-checked against the *current*
decision context before it can satisfy a required control. RA is the
authoritative re-checker (defense in depth); the Control-Assurance evaluator also
binds, but RA never trusts that alone.

The ratified binding relation (RA-5 spec §8.1) — a trusted result ``R`` is usable
for case ``K`` iff **every** clause holds, else it fails closed (treated as
``MISSING``, never ``PASS``):

    R.tenant_id           == K.tenant_id
  ∧ R.risk_case_id        == K.case_id
  ∧ R.workflow_ir_digest  == K.workflow_ir_digest
  ∧ R.policy_digest       == K.policy_digest
  ∧ R.control_id          ∈ K.required_controls
  ∧ every e ∈ R.evidence_ids is ADMITTED under the case context
  ∧ R.is_current(now) ∧ every backing evidence is_current(now)

This module is stdlib-only and imports no provider/integration code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from .controls import ControlResult

__all__ = [
    "CaseBindingContext",
    "AdmittedContext",
    "binding_violations",
    "usable_control_results",
]


@dataclass(frozen=True)
class CaseBindingContext:
    """The exact decision context a trusted result must be bound to (RA-5 §8)."""

    tenant_id: str
    case_id: str
    workflow_ir_digest: str
    policy_digest: str
    required_controls: frozenset[str]


@dataclass(frozen=True)
class AdmittedContext:
    """The admitted-evidence set available for a case, keyed by evidence id.

    ``valid_until`` per evidence id lets RA enforce freshness monotonicity
    (RA-5 §7.1): a result may not outlive the evidence it rests on. An evidence
    id absent from this map was never admitted in-context ⇒ any result citing it
    fails closed.
    """

    valid_until_by_id: Mapping[str, "datetime | None"]

    def admitted(self, evidence_id: str) -> bool:
        return evidence_id in self.valid_until_by_id

    def evidence_current(self, evidence_id: str, now: datetime) -> bool:
        vu = self.valid_until_by_id.get(evidence_id)
        return vu is None or now <= vu


def binding_violations(
    result: ControlResult,
    context: CaseBindingContext,
    admitted: AdmittedContext,
    now: datetime,
) -> tuple[str, ...]:
    """Return the binding-clause failures for ``result`` under ``context``.

    An empty tuple means the result is usable for the case. Any non-empty
    result means fail-closed: the caller must treat the control as unsatisfied
    (``MISSING``), never coerce it to ``PASS``.
    """

    reasons: list[str] = []

    # Production results must carry the full binding tuple. A result missing any
    # binding field is a reference/synthetic artifact and can never be trusted in
    # a production decision context.
    if not result.has_production_bindings():
        reasons.append("result missing production trust-binding fields")

    if result.tenant_id != context.tenant_id:
        reasons.append(
            f"tenant mismatch: result={result.tenant_id!r} case={context.tenant_id!r}"
        )
    if result.risk_case_id != context.case_id:
        reasons.append(
            f"case mismatch: result={result.risk_case_id!r} case={context.case_id!r}"
        )
    if result.workflow_ir_digest != context.workflow_ir_digest:
        reasons.append("workflow_ir_digest mismatch")
    if result.policy_digest != context.policy_digest:
        reasons.append("policy_digest mismatch")
    if result.control_id not in context.required_controls:
        reasons.append(
            f"control_id {result.control_id!r} not in required controls"
        )

    # Every backing evidence id must have been admitted in-context and must still
    # be current, and the result must not outlive its evidence (§7.1).
    if not result.evidence_ids:
        reasons.append("trusted result carries no backing evidence ids")
    for eid in result.evidence_ids:
        if not admitted.admitted(eid):
            reasons.append(f"evidence {eid!r} not in admitted set for this context")
            continue
        if not admitted.evidence_current(eid, now):
            reasons.append(f"backing evidence {eid!r} is stale")

    if not result.is_current(now):
        reasons.append("trusted result validity window has elapsed")

    return tuple(reasons)


def usable_control_results(
    results: tuple[ControlResult, ...],
    context: CaseBindingContext,
    admitted: AdmittedContext,
    now: datetime,
) -> tuple[ControlResult, ...]:
    """Return only the results that satisfy the full binding relation.

    Results that fail any clause are dropped here so that RA's non-compensatory
    gate then sees the control as ``MISSING`` (fail closed). A dropped ``PASS``
    can never mint authority; a retained ``FAIL`` still governs (F-E preserved).
    """

    return tuple(
        r for r in results if not binding_violations(r, context, admitted, now)
    )
