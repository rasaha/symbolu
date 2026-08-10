"""Re-check the current action against the governance-narrowed effective scope
(RA-4.5 F1 hardening).

The restriction algebra (:mod:`ugence_risk_authority_runtime.restrictions`)
produces an :class:`EffectiveConstraints` that is always ``⊆`` the Risk Authority
scope. But a non-empty effective scope is **not** sufficient for GRANT: governance
may narrow an allow/deny set or an amount ceiling so that the *specific* action
Risk Authority authorized is no longer inside the effective scope. Example::

    RA scope tools_allow = {refund.prepare, crm.read}
    governance narrows  → {crm.read}
    current action      = refund.prepare        # non-empty scope, but excluded

Without this re-check the composition would GRANT (the effective scope is
merely non-empty). The engine therefore calls :func:`effective_scope_violations`
before GRANT and denies when the current action is not authorized by the
effective scope.

Semantics are a faithful mirror of the Risk Authority reference enforcer
(``risk_authority.integrations.actiongate.ReferenceActionGate.authorize`` steps
3–7): purpose, tool allow/deny, data allow/deny, destination, and amount
ceiling. These are exactly the dimensions that governance can narrow **and** the
canonical action can be matched against. Envelope-level dimensions RA already
enforced (signature, time, revocation, epoch, tenant/actor/model binding,
conditions, human approval) are **not** governance-narrowable and are not
re-checked here — RA remains their sole authority. Jurisdiction / autonomy /
resource enforcement stays deferred under F-D / #1397 and is deliberately **not**
introduced here (adding it is out of scope for F1).

A differential test (``tests/test_effective_action_recheck.py``) pins these
predicates to the RA reference gate on the shared dimensions, so the mirror can
never drift looser than Risk Authority itself.
"""

from __future__ import annotations

from typing import Optional

from .contracts import EffectiveConstraints

__all__ = ["effective_scope_violations", "effective_scope_authorizes"]


def effective_scope_violations(
    effective: EffectiveConstraints, action: object
) -> list[str]:
    """Return the reasons ``action`` is outside ``effective`` (empty == inside).

    Mirrors ``ReferenceActionGate.authorize`` scope matching (steps 3–7) against
    the *effective* (governance-narrowed) scope rather than the raw RA scope. A
    non-empty return means the current action is no longer authorized after
    governance narrowing → the caller must fail closed (deny).
    """

    reasons: list[str] = []

    purpose = getattr(action, "purpose", None)
    action_type = getattr(action, "action_type", None)
    data_classes = tuple(getattr(action, "data_classes", ()) or ())
    destination = getattr(action, "destination", "") or ""
    amount = getattr(action, "amount_minor_units", None)

    # 3. Purpose must remain in the effective allow set.
    if purpose not in set(effective.purposes):
        reasons.append(f"purpose {purpose!r} outside effective scope")

    # 4. Tool / action type — deny set dominates, then allow set membership.
    if action_type in set(effective.tools_deny):
        reasons.append(f"tool {action_type!r} denied by effective scope")
    elif action_type not in set(effective.tools_allow):
        reasons.append(f"tool {action_type!r} not in effective allow set")

    # 5. Data classes — none denied; all must be in the effective allow set.
    denied_data = set(data_classes) & set(effective.data_deny)
    if denied_data:
        reasons.append(f"prohibited data classes {sorted(denied_data)}")
    extra_data = set(data_classes) - set(effective.data_allow)
    if extra_data:
        reasons.append(f"data classes {sorted(extra_data)} outside effective scope")

    # 6. Destination (only when the action targets one).
    if destination and destination not in set(effective.destinations):
        reasons.append(f"destination {destination!r} outside effective scope")

    # 7. Amount ceiling (only when the action carries an amount).
    if amount is not None:
        limit: Optional[int] = effective.max_amount_minor_units
        if limit is not None and amount > limit:
            reasons.append(f"amount {amount} exceeds effective ceiling {limit}")

    return reasons


def effective_scope_authorizes(
    effective: EffectiveConstraints, action: object
) -> bool:
    """True iff ``action`` is still authorized by the effective scope."""

    return not effective_scope_violations(effective, action)
