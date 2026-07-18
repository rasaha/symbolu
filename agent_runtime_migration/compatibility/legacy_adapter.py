"""Additive compatibility adapter: legacy shapes -> new runtime contracts.

DUCK-TYPED on purpose: it does NOT import ``agentic.agentic_framework`` (whose
package __init__ pulls research-signal code). It accepts any object shaped like the
legacy ``GoalState`` / ``ActionItem`` (attributes or dict keys) and converts it into
the new ``Goal`` + planned ``Action`` list.

Rules:
* action types the trusted risk map marks GOVERNED become GOVERNED_CONSEQUENTIAL and
  are routed through CER -> AI Control Plane; the legacy action MUST carry the CER
  envelope sections (actuation/authority/state_binding/policy_ref) in its parameters,
  else conversion fails EXPLICITLY (unsupported legacy behavior is not silently run);
* everything else becomes LOCAL_READ_ONLY;
* it never preserves duplicate governance authority and never executes anything.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from ..contracts.action import Action, RiskClass
from ..contracts.errors import ContractError
from ..contracts.goal import Goal
from .warnings import deprecated


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


# legacy action_type -> (risk_class, cer_profile). Governed entries require envelope sections.
DEFAULT_RISK_MAP: Dict[str, tuple] = {
    "kubernetes.scale": (RiskClass.GOVERNED_CONSEQUENTIAL, "kubernetes.scale.v1"),
    "kubernetes.rollout": (RiskClass.GOVERNED_CONSEQUENTIAL, "kubernetes.rollout.v1"),
    "database.mutation": (RiskClass.GOVERNED_CONSEQUENTIAL, "database.mutation.v1"),
    # everything else defaults to local read-only
}

_ENVELOPE_KEYS = ("actuation", "authority", "state_binding", "policy_ref")


def to_action(legacy_action: Any, *,
              risk_map: Optional[Dict[str, tuple]] = None) -> Action:
    risk_map = risk_map or DEFAULT_RISK_MAP
    action_id = _attr(legacy_action, "action_id") or "legacy-action"
    action_type = _attr(legacy_action, "action_type", "generate")
    params: Dict[str, Any] = dict(_attr(legacy_action, "parameters", {}) or {})

    mapping = risk_map.get(action_type)
    if mapping and mapping[0] is RiskClass.GOVERNED_CONSEQUENTIAL:
        _rc, profile = mapping
        missing = [k for k in _ENVELOPE_KEYS if k not in params]
        if missing:
            raise ContractError(
                f"legacy governed action {action_id!r} ({action_type}) cannot be migrated: "
                f"missing CER envelope sections {missing}. It must be re-expressed with "
                "actuation/authority/state_binding/policy_ref to be governed (not silently run).")
        return Action(action_id=action_id, kind=action_type, tool_name=action_type,
                      risk_class=RiskClass.GOVERNED_CONSEQUENTIAL, profile=profile, arguments=params)

    # local read-only fallback (formatting/parsing/read-only retrieval)
    return Action(action_id=action_id, kind=action_type, tool_name=action_type,
                  risk_class=RiskClass.LOCAL_READ_ONLY, arguments=params)


def to_goal(legacy_goal: Any, *, goal_id: str = "legacy-goal",
            risk_map: Optional[Dict[str, tuple]] = None) -> Goal:
    """Convert a legacy GoalState-shaped object into a new Goal carrying a plan."""
    deprecated("legacy GoalState/ActionItem", "agent_runtime_migration.contracts.Goal/Action")
    objective = _attr(legacy_goal, "purpose") or _attr(legacy_goal, "objective") or "legacy goal"
    purpose_type = _attr(legacy_goal, "purpose_type", "task")
    if purpose_type not in ("informational", "task", "analysis", "creative"):
        purpose_type = "task"
    legacy_actions = _attr(legacy_goal, "actions", []) or []
    plan: List[Action] = [to_action(a, risk_map=risk_map) for a in legacy_actions]
    return Goal(goal_id=goal_id, objective=objective, purpose_type=purpose_type,
                metadata={"plan": plan, "migrated_from": "agentic.agentic_framework"})
