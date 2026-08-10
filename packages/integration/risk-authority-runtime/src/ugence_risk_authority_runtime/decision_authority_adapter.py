"""Decision Authority governance adapter (RA-4.5 §4).

Translates the canonical production Decision Authority
(``ugence-decision-authority``) outcome into an **additive governance veto**,
never a substitute Risk Authority decision.

Mapping (production ``DecisionOutcome`` → composition veto):

    ADVANCE  → NO_VETO   (organizational governance does not object)
    HOLD     → HOLD      (non-executable; resumable after governance resolves)
    DEFER    → HOLD      (non-executable; deferred)
    REJECT   → DENY      (organizational veto; terminal)
    <unknown>→ DENY      (fail closed — an unrecognized outcome never authorizes)
    <missing>→ ERROR     (unavailable / malformed — fail closed, never ALLOW)

This adapter MUST NOT: issue an RA ``Scope``; mint a ``RiskAuthorizationEnvelope``;
derive a machine ``ALLOW``; or weaken an RA ``DENY``. An ``ADVANCE`` means only
"governance does not veto" — the machine capability is still bounded entirely by
Risk Authority (plan §10).

The production Decision Authority's binding-authority holder is a human,
committee, or delegated policy — never an AI model (its ``AuthorityType``
excludes AI by construction), which is exactly the governance semantics worth
composing (segregation of duties, required human approvals).
"""

from __future__ import annotations

from typing import Optional, Union

from .contracts import (
    EMPTY_RESTRICTIONS,
    GovernanceRestrictions,
    GovernanceVetoResult,
    ReasonCode,
    VetoDisposition,
)

__all__ = [
    "DecisionAuthorityGovernanceAdapter",
    "DecisionAuthorityUnavailable",
    "SOURCE",
]

SOURCE = "decision_authority"


class DecisionAuthorityUnavailable(Exception):
    """Raised/handled when the Decision Authority governance input is missing.

    The adapter treats this as ``ERROR`` (fail closed): a required governance
    input could not be obtained, so execution must not proceed.
    """


# Canonical production outcome *values* (``ugence_decision_authority`` ships the
# enum ``decisions.status.DecisionOutcome`` with exactly these members). We match
# on the string value so the adapter does not force an import of the pydantic-
# backed kernel aggregate just to read an outcome name, and so a plain string
# outcome (e.g. from a serialized kernel response) maps identically.
_ADVANCE = "ADVANCE"
_HOLD = "HOLD"
_REJECT = "REJECT"
_DEFER = "DEFER"

_OUTCOME_TO_VETO = {
    _ADVANCE: (VetoDisposition.NO_VETO, ReasonCode.DA_ADVANCE_NO_VETO),
    _HOLD: (VetoDisposition.HOLD, ReasonCode.DA_HOLD),
    _DEFER: (VetoDisposition.HOLD, ReasonCode.DA_DEFER),
    _REJECT: (VetoDisposition.DENY, ReasonCode.DA_REJECT),
}


def _outcome_value(outcome: object) -> Optional[str]:
    """Extract the outcome's string value, accepting an enum or a raw string."""

    if outcome is None:
        return None
    value = getattr(outcome, "value", outcome)
    if isinstance(value, str):
        return value
    return None


class DecisionAuthorityGovernanceAdapter:
    """Adapt a Decision Authority outcome into a :class:`GovernanceVetoResult`."""

    def __init__(self, *, source_version: str = "") -> None:
        self._source_version = source_version

    def to_veto(
        self,
        outcome: object,
        *,
        required_approvals: frozenset[str] = frozenset(),
        raw_reason_codes: tuple[str, ...] = (),
    ) -> GovernanceVetoResult:
        """Translate a resolved Decision Authority ``outcome`` into a veto result.

        ``outcome`` may be the production ``DecisionOutcome`` enum, its string
        value, or ``None`` (treated as a malformed / missing outcome → ERROR).
        ``required_approvals`` (e.g. committee / SoD approvals the organization
        mandates) are carried as a strengthening obligation — they can only add
        to the required-approval set, never remove one.
        """

        value = _outcome_value(outcome)
        restrictions = (
            GovernanceRestrictions(required_approvals=required_approvals)
            if required_approvals
            else EMPTY_RESTRICTIONS
        )

        if value is None:
            return GovernanceVetoResult(
                source=SOURCE,
                disposition=VetoDisposition.ERROR,
                reason_codes=(ReasonCode.DA_MALFORMED.value,),
                restrictions=restrictions,
                source_version=self._source_version,
                raw_outcome=str(outcome),
                raw_reason_codes=raw_reason_codes,
            )

        mapped = _OUTCOME_TO_VETO.get(value)
        if mapped is None:
            # An outcome we do not recognize never authorizes → fail closed DENY.
            return GovernanceVetoResult(
                source=SOURCE,
                disposition=VetoDisposition.DENY,
                reason_codes=(ReasonCode.DA_UNKNOWN_OUTCOME.value,),
                restrictions=restrictions,
                source_version=self._source_version,
                raw_outcome=value,
                raw_reason_codes=raw_reason_codes,
            )

        disposition, reason = mapped
        return GovernanceVetoResult(
            source=SOURCE,
            disposition=disposition,
            reason_codes=(reason.value,),
            restrictions=restrictions,
            source_version=self._source_version,
            raw_outcome=value,
            raw_reason_codes=raw_reason_codes,
        )

    def unavailable(self, detail: str = "") -> GovernanceVetoResult:
        """Build the fail-closed ERROR result for an unreachable Decision Authority."""

        return GovernanceVetoResult(
            source=SOURCE,
            disposition=VetoDisposition.ERROR,
            reason_codes=(ReasonCode.DA_UNAVAILABLE.value,),
            source_version=self._source_version,
            raw_outcome="",
            raw_reason_codes=((detail,) if detail else ()),
        )
