"""Fail-closed governance composition engine (RA-4.5 §2, §3, §8, §9).

The single, explicit composition engine. It folds two *additive* governance
inputs (Decision Authority, ActionGate) onto a Risk Authority machine-authority
result and applies the monotone restriction algebra, producing one
:class:`GovernedExecutionDecision`.

Corrected decision rule — GRANT **iff** every check holds (all fail-closed):

    1. RA enforcement evaluated            (else ERROR_NON_EXECUTABLE)
    2. RA authorized the exact action      (envelope verify + exact-action match)
    3. Decision Authority does not veto    (ADVANCE; not HOLD/DEFER/REJECT)
    4. ActionGate does not veto            (ALLOW/…; not DENY/UNKNOWN)
    5. no authority-critical input errored (else ERROR_NON_EXECUTABLE)
    6. effective restrictions leave a non-empty scope

Precedence (highest wins, all fail-closed; plan §3):

    RA ERROR
      > RA DENY / invalid / expired / revoked
      > DA REJECT
      > AG DENY / UNKNOWN
      > DA HOLD / DEFER
      > ERROR / UNAVAILABLE (fail-closed)
      > empty effective scope
      > GRANT

Formal guarantee, by construction:

    FinalAuthority ≤ RiskAuthority          (no governance input upgrades RA)
    FinalScope    ⊆ RiskAuthorityScope      (restriction algebra tightens only)

No governance input — permissive or advisory — can upgrade an RA ``DENY``,
widen scope, or manufacture authority RA did not issue. Execution never proceeds
on ambiguous state.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from .contracts import (
    EffectiveConstraints,
    FinalDisposition,
    GovernanceVetoResult,
    GovernedExecutionDecision,
    ReasonCode,
    RiskAuthorityMachineResult,
    VetoDisposition,
)
from .restrictions import apply_restrictions

__all__ = ["RiskAuthorityCompositionEngine"]


class RiskAuthorityCompositionEngine:
    """Compose RA authority with additive governance vetoes, fail-closed."""

    def compose(
        self,
        *,
        risk_authority: RiskAuthorityMachineResult,
        decision_authority: GovernanceVetoResult,
        actiongate: GovernanceVetoResult,
        correlation_id: str = "",
    ) -> GovernedExecutionDecision:
        """Return the governed execution decision for one request."""

        ra = risk_authority
        da = decision_authority
        ag = actiongate

        source_versions = {
            "risk_authority": ra.source_version,
            "decision_authority": da.source_version,
            "actiongate": ag.source_version,
        }

        # Effective constraints are always computed (for audit), then GRANT is
        # gated on them last. They are RA-bounded: FinalScope ⊆ RiskAuthorityScope.
        effective = apply_restrictions(ra, _restrictions(da, ag))

        disposition, reason_codes, non_executable_reason = self._decide(
            ra, da, ag, effective
        )

        return GovernedExecutionDecision(
            final_disposition=disposition,
            risk_authority_result=ra,
            decision_authority_result=da,
            actiongate_result=ag,
            effective_constraints=effective,
            reason_codes=reason_codes,
            non_executable_reason=non_executable_reason,
            source_versions=source_versions,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    def _decide(
        self,
        ra: RiskAuthorityMachineResult,
        da: GovernanceVetoResult,
        ag: GovernanceVetoResult,
        effective: EffectiveConstraints,
    ) -> tuple[FinalDisposition, tuple[str, ...], str]:
        """Apply the fail-closed precedence order and return the disposition."""

        # 1. Risk Authority could not be evaluated → ERROR (no authority basis).
        if ra.errored:
            return (
                FinalDisposition.ERROR_NON_EXECUTABLE,
                ra.reason_codes,
                "risk authority enforcement unavailable",
            )

        # 2. Risk Authority DENY is absorbing — nothing downstream upgrades it.
        if not ra.authorized:
            return (
                FinalDisposition.DENY,
                ra.reason_codes,
                "risk authority denied the action",
            )

        # --- RA authorized the exact action from here. Governance may subtract. ---

        # 3. Decision Authority organizational veto (REJECT) — terminal DENY.
        if da.disposition is VetoDisposition.DENY:
            return (
                FinalDisposition.DENY,
                da.reason_codes,
                "decision authority vetoed (organizational reject)",
            )

        # 4. ActionGate policy veto (DENY / UNKNOWN) — terminal DENY.
        if ag.disposition is VetoDisposition.DENY:
            return (
                FinalDisposition.DENY,
                ag.reason_codes,
                "actiongate policy vetoed the action",
            )

        # 5. Decision Authority HOLD / DEFER — non-executable governance hold.
        if da.disposition is VetoDisposition.HOLD:
            return (
                FinalDisposition.HOLD_NON_EXECUTABLE,
                da.reason_codes,
                "decision authority requires a hold/deferral",
            )
        # (ActionGate has no HOLD outcome, but treat it uniformly for safety.)
        if ag.disposition is VetoDisposition.HOLD:
            return (
                FinalDisposition.HOLD_NON_EXECUTABLE,
                ag.reason_codes,
                "actiongate requires a hold",
            )

        # 6. An authority-critical governance input errored → ERROR (fail closed).
        if da.disposition is VetoDisposition.ERROR:
            return (
                FinalDisposition.ERROR_NON_EXECUTABLE,
                da.reason_codes,
                "decision authority governance input unavailable",
            )
        if ag.disposition is VetoDisposition.ERROR:
            return (
                FinalDisposition.ERROR_NON_EXECUTABLE,
                ag.reason_codes,
                "actiongate governance input unavailable",
            )

        # 7. Restriction algebra emptied the grant → DENY (no residual authority).
        if effective.is_empty():
            return (
                FinalDisposition.DENY,
                (ReasonCode.EFFECTIVE_SCOPE_EMPTY.value,),
                "governance restrictions left an empty effective scope",
            )

        # 8. All clear — execution eligible (still bounded by effective scope).
        return (
            FinalDisposition.GRANT,
            (ReasonCode.GRANTED.value,),
            "",
        )


def _restrictions(
    da: GovernanceVetoResult, ag: GovernanceVetoResult
) -> Iterable:
    """Collect the tightening restrictions each governance source contributed."""

    return (da.restrictions, ag.restrictions)
