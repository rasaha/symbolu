"""The projection from composed governance disposition to runtime disposition.

This is the ONE place a ``FinalDisposition`` becomes a ``GovernanceDisposition``, and
it is the only place in this package where CLEAR can be produced at all. The mapping is
total, closed and non-broadening:

    GRANT                  -> CLEAR
    DENY                   -> BLOCK
    HOLD_NON_EXECUTABLE    -> HOLD, or ESCALATE when an external approval is required
    ERROR_NON_EXECUTABLE   -> BLOCK
    anything else          -> BLOCK

Three refusals are worth stating explicitly, because each closes a way the mapping
could otherwise be widened by accident or by a hostile input:

1. **The disposition must be a real ``FinalDisposition`` member.**
   ``FinalDisposition`` is a ``str`` enum, so the bare string ``"GRANT"`` compares
   equal to ``FinalDisposition.GRANT`` and hashes identically — a plain dict lookup
   would happily accept it from a malformed or spoofed object. ``isinstance`` is
   therefore checked first, and a look-alike is refused.

2. **A decision's self-reported ``executable`` is never trusted on its own.**
   CLEAR requires the disposition to be GRANT *and* ``executable`` to be true. A
   spoofed object claiming ``executable = True`` alongside a DENY disposition is
   refused, because the disposition drives the mapping, not the boolean.

3. **Absent is not permissive.** ``None`` maps to BLOCK like anything else unknown.

Both non-executable outcomes stop the transition; the choice between HOLD and ESCALATE
selects which *stable boundary* the runtime parks at (WAIT versus PAUSE) and neither can
proceed without an explicit ``resume_workflow``. ESCALATE is used where the composition
recorded a required approval, because that is what "pending external authority or
review" means; it is not a weaker outcome than HOLD.
"""
from __future__ import annotations

from typing import Any, Optional, Tuple

from ugence_agent_runtime.governance.interfaces import GovernanceDisposition
from ugence_risk_authority_runtime.contracts import FinalDisposition

__all__ = [
    "project_disposition",
    "requires_external_approval",
    "REASON_NOT_A_FINAL_DISPOSITION",
    "REASON_NOT_EXECUTABLE",
    "REASON_UNKNOWN_DISPOSITION",
]

#: The composed decision carried something that is not a ``FinalDisposition`` member —
#: a bare string, an unrelated enum, or ``None``.
REASON_NOT_A_FINAL_DISPOSITION = "GOVERNANCE_DECISION_NOT_A_FINAL_DISPOSITION"
#: GRANT was claimed but the decision does not report itself executable.
REASON_NOT_EXECUTABLE = "GOVERNANCE_DECISION_GRANT_NOT_EXECUTABLE"
#: A ``FinalDisposition`` member this build has no mapping for (a future member).
REASON_UNKNOWN_DISPOSITION = "GOVERNANCE_DECISION_UNKNOWN_DISPOSITION"

#: The closed, non-broadening mapping. Keyed by identity of the enum member, resolved
#: only after ``isinstance`` has established the value really is one.
_NON_EXECUTABLE = {
    FinalDisposition.DENY: GovernanceDisposition.BLOCK,
    FinalDisposition.ERROR_NON_EXECUTABLE: GovernanceDisposition.BLOCK,
}


def requires_external_approval(decision: Any) -> bool:
    """True when the composition recorded an approval that a human must supply.

    Read defensively: a decision whose constraints cannot be inspected is treated as
    *not* requiring approval, which selects HOLD rather than ESCALATE. Both are
    non-executable, so the fallback cannot widen anything — it only picks the less
    specific of two equally restrictive parkings.
    """
    try:
        constraints = decision.effective_constraints
        return bool(constraints.required_approvals)
    except Exception:  # noqa: BLE001 - a decision we cannot inspect requires no approval
        return False


def project_disposition(
    decision: Any,
) -> Tuple[GovernanceDisposition, Tuple[str, ...]]:
    """Project one composed decision onto a runtime disposition, fail-closed.

    Returns ``(disposition, extra_reason_codes)``. The extra codes explain *why* a
    non-obvious refusal happened; they are additive to whatever the composition itself
    reported and never replace it.
    """
    if decision is None:
        return GovernanceDisposition.BLOCK, (REASON_NOT_A_FINAL_DISPOSITION,)

    # ``getattr(obj, name, default)`` only swallows AttributeError. An object whose
    # ``__getattr__`` raises anything else would propagate out of here and into the
    # runtime's hot path, where a raising hook is indistinguishable from one that was
    # never asked. Read defensively: wreckage is refused, not raised.
    try:
        final = decision.final_disposition
    except Exception:  # noqa: BLE001 - an uninspectable decision is not permission
        return GovernanceDisposition.BLOCK, (REASON_NOT_A_FINAL_DISPOSITION,)

    # (1) A str-enum look-alike must not pass. `"GRANT" == FinalDisposition.GRANT` is
    #     True and hashes the same, so equality and dict lookup are both unsafe here.
    if not isinstance(final, FinalDisposition):
        return GovernanceDisposition.BLOCK, (REASON_NOT_A_FINAL_DISPOSITION,)

    if final is FinalDisposition.GRANT:
        # (2) A self-reported boolean is corroboration, never the basis.
        try:
            executable = decision.executable
        except Exception:  # noqa: BLE001 - same reasoning as above
            return GovernanceDisposition.BLOCK, (REASON_NOT_EXECUTABLE,)
        if executable is not True:
            return GovernanceDisposition.BLOCK, (REASON_NOT_EXECUTABLE,)
        return GovernanceDisposition.CLEAR, ()

    if final is FinalDisposition.HOLD_NON_EXECUTABLE:
        if requires_external_approval(decision):
            return GovernanceDisposition.ESCALATE, ()
        return GovernanceDisposition.HOLD, ()

    mapped = _NON_EXECUTABLE.get(final)
    if mapped is not None:
        return mapped, ()

    # (3) A FinalDisposition member added by a future build. Never guess.
    return GovernanceDisposition.BLOCK, (REASON_UNKNOWN_DISPOSITION,)
