"""Policy lifecycle + approval controls (§8).

Deterministic, audited state machine. No single actor may author AND publish an
enforced high-consequence policy; each transition records who approved it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..canonical import digest

LIFECYCLE_STATES = (
    "DRAFT", "VALIDATING", "SHADOW_APPROVED", "SHADOW_ACTIVE",
    "ENFORCEMENT_CANDIDATE", "ENFORCED", "SUSPENDED", "RETIRED",
)

# from -> {to: required_approver_role or None}
_TRANSITIONS = {
    "DRAFT": {"VALIDATING": None, "RETIRED": "control_owner"},
    "VALIDATING": {"SHADOW_APPROVED": "business_owner", "DRAFT": None,
                   "RETIRED": "control_owner"},
    "SHADOW_APPROVED": {"SHADOW_ACTIVE": "technical_owner", "DRAFT": None},
    "SHADOW_ACTIVE": {"ENFORCEMENT_CANDIDATE": "control_owner", "SUSPENDED": None,
                      "RETIRED": "control_owner"},
    "ENFORCEMENT_CANDIDATE": {"ENFORCED": "risk", "SHADOW_ACTIVE": None,
                              "SUSPENDED": None},
    "ENFORCED": {"SUSPENDED": None, "RETIRED": "control_owner"},
    "SUSPENDED": {"SHADOW_ACTIVE": "control_owner", "RETIRED": "control_owner"},
    "RETIRED": {},
}


class LifecycleError(Exception):
    pass


@dataclass
class LifecycleLog:
    entries: list = field(default_factory=list)

    def digest(self) -> str:
        return digest(self.entries, domain="CTD-POLICY-LIFECYCLE")


def transition(current: str, target: str, *, actor: str, actor_roles,
               author: str, at: str, log: "LifecycleLog | None" = None) -> LifecycleLog:
    """Validate + record a lifecycle transition (§8)."""
    log = log or LifecycleLog()
    if current not in LIFECYCLE_STATES:
        raise LifecycleError(f"unknown current state {current!r}")
    allowed = _TRANSITIONS.get(current, {})
    if target not in allowed:
        raise LifecycleError(f"invalid transition {current} -> {target}")
    required_role = allowed[target]
    roles = set(actor_roles)
    if required_role and required_role not in roles:
        raise LifecycleError(
            f"transition {current} -> {target} requires role '{required_role}', "
            f"actor {actor!r} has {sorted(roles)}")
    # segregation: the author of an enforced high-consequence policy may not publish it
    if target in ("ENFORCEMENT_CANDIDATE", "ENFORCED") and actor == author:
        raise LifecycleError(
            f"actor {actor!r} authored this policy and may not also publish it to "
            f"{target} (segregation of duties)")
    log.entries.append({"from": current, "to": target, "actor": actor,
                        "required_role": required_role, "at": at})
    return log
