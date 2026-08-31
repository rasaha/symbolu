"""ActionGate policy adapter (RA-4.5 §6, §11).

Translates the canonical production ActionGate provider
(``ugence-actiongate-provider``) outcome into a **supplementary action-policy
veto / restriction** — never a substitute for Risk Authority enforcement.

Mapping (native ``ActionGateOutcome`` → composition veto):

    ALLOW                   → NO_VETO
    ALLOW_WITH_CONSTRAINTS  → NO_VETO + tightening constraints
    DENY                    → DENY
    UNKNOWN                 → DENY   (fail closed — its one fail-closed axis)
    <missing/malformed>     → ERROR  (fail closed, never ALLOW)

The provider's sole competency is an ``action_type`` policy lookup. It verifies
**none** of: signature, tenant, actor, model, scope, expiry, revocation, epoch,
or exact payload — those remain Risk Authority-owned (plan §1.3). This adapter
therefore never treats an ActionGate ``ALLOW`` as having validated any of them.

Emitted typed constraints are folded in only in the *tightening* direction
(plan §11):

    maximum_amount   → GovernanceRestrictions.max_amount_minor_units  (min with RA)
    execution_deadline / expiry_seconds → expires_at                  (earliest with RA)
    required_approval→ required_approvals                              (union / strengthen)
    allowed_region   → recorded as an obligation ONLY — NOT mapped onto RA
                       jurisdiction enforcement (that is F-D / #1397; no silent map)
    <other>          → recorded as obligations (audit); never widen authority
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .contracts import (
    GovernanceRestrictions,
    GovernanceVetoResult,
    ReasonCode,
    VetoDisposition,
)

__all__ = ["ActionGatePolicyAdapter", "SOURCE"]

SOURCE = "actiongate"

# Native outcome values (``ugence_actiongate_provider.core.ActionGateOutcome``).
_ALLOW = "ALLOW"
_DENY = "DENY"
_ALLOW_WITH_CONSTRAINTS = "ALLOW_WITH_CONSTRAINTS"
_UNKNOWN = "UNKNOWN"


def _outcome_value(outcome: object) -> Optional[str]:
    if outcome is None:
        return None
    value = getattr(outcome, "value", outcome)
    return value if isinstance(value, str) else None


def _parse_amount(value: str) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


class ActionGatePolicyAdapter:
    """Adapt an ActionGate decision into a :class:`GovernanceVetoResult`."""

    def __init__(self, *, source_version: str = "") -> None:
        self._source_version = source_version

    def to_veto(
        self,
        decision: object,
        *,
        now: Optional[datetime] = None,
    ) -> GovernanceVetoResult:
        """Translate an ActionGate ``decision`` into a veto / restriction result.

        ``decision`` is the native ``ActionGateDecision`` (``outcome`` +
        ``constraints`` + ``obligations`` + ``expiry_seconds`` + ``reason_codes``),
        or ``None`` (treated as malformed / missing → ERROR). ``now`` is required
        only to convert a relative ``expiry_seconds`` into an absolute instant.
        """

        if decision is None:
            return GovernanceVetoResult(
                source=SOURCE,
                disposition=VetoDisposition.ERROR,
                reason_codes=(ReasonCode.AG_MALFORMED.value,),
                source_version=self._source_version,
                raw_outcome="",
            )

        value = _outcome_value(getattr(decision, "outcome", decision))
        raw_reason_codes = tuple(getattr(decision, "reason_codes", ()) or ())

        if value == _DENY:
            return GovernanceVetoResult(
                source=SOURCE,
                disposition=VetoDisposition.DENY,
                reason_codes=(ReasonCode.AG_DENY.value,),
                source_version=self._source_version,
                raw_outcome=value,
                raw_reason_codes=raw_reason_codes,
            )

        if value == _UNKNOWN:
            # UNKNOWN never authorizes — the provider's one fail-closed axis.
            return GovernanceVetoResult(
                source=SOURCE,
                disposition=VetoDisposition.DENY,
                reason_codes=(ReasonCode.AG_UNKNOWN.value,),
                source_version=self._source_version,
                raw_outcome=value,
                raw_reason_codes=raw_reason_codes,
            )

        if value not in (_ALLOW, _ALLOW_WITH_CONSTRAINTS):
            # Any unrecognized outcome is malformed → ERROR (fail closed).
            return GovernanceVetoResult(
                source=SOURCE,
                disposition=VetoDisposition.ERROR,
                reason_codes=(ReasonCode.AG_MALFORMED.value,),
                source_version=self._source_version,
                raw_outcome=str(value),
                raw_reason_codes=raw_reason_codes,
            )

        # ALLOW / ALLOW_WITH_CONSTRAINTS → no veto, but fold in tightening
        # restrictions (which can only narrow the effective authority).
        restrictions = self._extract_restrictions(decision, now=now)
        reason = (
            ReasonCode.AG_ALLOW_WITH_CONSTRAINTS
            if value == _ALLOW_WITH_CONSTRAINTS
            else ReasonCode.AG_ALLOW_NO_VETO
        )
        return GovernanceVetoResult(
            source=SOURCE,
            disposition=VetoDisposition.NO_VETO,
            reason_codes=(reason.value,),
            restrictions=restrictions,
            source_version=self._source_version,
            raw_outcome=value,
            raw_reason_codes=raw_reason_codes,
        )

    def unavailable(self, detail: str = "") -> GovernanceVetoResult:
        """Build the fail-closed ERROR result for an unreachable ActionGate."""

        return GovernanceVetoResult(
            source=SOURCE,
            disposition=VetoDisposition.ERROR,
            reason_codes=(ReasonCode.AG_UNAVAILABLE.value,),
            source_version=self._source_version,
            raw_outcome="",
            raw_reason_codes=((detail,) if detail else ()),
        )

    # ------------------------------------------------------------------
    def _extract_restrictions(
        self, decision: object, *, now: Optional[datetime]
    ) -> GovernanceRestrictions:
        max_amount: Optional[int] = None
        expires_at: Optional[datetime] = None
        required_approvals: set[str] = set()
        obligations: list[tuple[str, str]] = []

        # Relative expiry → absolute (only tightens; the engine still min()s it
        # against the RA envelope expiry, so it can never extend RA validity).
        expiry_seconds = getattr(decision, "expiry_seconds", None)
        if expiry_seconds is not None and now is not None:
            try:
                expires_at = now + timedelta(seconds=int(expiry_seconds))
            except (TypeError, ValueError, OverflowError):
                expires_at = None

        for constraint in getattr(decision, "constraints", ()) or ():
            ctype = getattr(constraint, "type", "")
            cvalue = getattr(constraint, "value", "")
            if ctype == "maximum_amount":
                amount = _parse_amount(cvalue)
                if amount is not None:
                    max_amount = amount if max_amount is None else min(max_amount, amount)
            elif ctype == "execution_deadline":
                # Absolute deadline if parseable; otherwise recorded as obligation.
                deadline = _parse_iso(cvalue)
                if deadline is not None:
                    expires_at = (
                        deadline if expires_at is None else min(expires_at, deadline)
                    )
                else:
                    obligations.append((ctype, str(cvalue)))
            elif ctype == "required_approval":
                required_approvals.add(str(cvalue) or "required_approval")
            else:
                # allowed_region, parameter_restriction, rate_limit, single_use,
                # and any extension type → recorded as governance obligations.
                # NB: allowed_region is deliberately NOT mapped onto RA
                # jurisdiction enforcement (F-D / #1397) — no silent mapping.
                obligations.append((str(ctype), str(cvalue)))

        for obligation in getattr(decision, "obligations", ()) or ():
            otype = getattr(obligation, "type", "")
            ovalue = getattr(obligation, "value", "")
            obligations.append((str(otype), str(ovalue)))

        return GovernanceRestrictions(
            max_amount_minor_units=max_amount,
            expires_at=expires_at,
            required_approvals=frozenset(required_approvals),
            obligations=tuple(obligations),
        )


def _parse_iso(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
