"""ActionGate adapter (read-only, shadow). Maps a proposed action to a shadow authorization disposition
based on required authority, reversibility, and risk. Conservative: an irreversible high/critical action
requiring an authority the request does not grant is BLOCKED; a reversible constrained action is
CONSTRAINED; ambiguous proposals are INDETERMINATE. Never performs the action."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import AdapterResult

_STAGE = "action_gate"


def run(action: Optional[Dict[str, Any]], request: Dict[str, Any]) -> AdapterResult:
    if action is None:
        return AdapterResult(_STAGE, "action_shadow_v1", "NO_ACTION", ["GIP.ACTION_ABSENT"])
    if action.get("ambiguous"):
        return AdapterResult(_STAGE, "action_shadow_v1", "INDETERMINATE", ["GIP.ACTION_AMBIGUOUS"],
                             source_repr={"action": action})
    granted = set(request.get("action_permissions", []))
    required = action.get("required_authority", "")
    reversibility = action.get("reversibility", "reversible")
    risk = action.get("risk", "low")
    if required and required not in granted and (reversibility == "irreversible" or risk in ("high", "critical")):
        disp = "BLOCK"; code = "ACT.AUTHORITY_MISSING_IRREVERSIBLE"
    elif risk in ("high", "critical"):
        disp = "CONSTRAIN"; code = "ACT.HIGH_RISK_CONSTRAINED"
    elif required and required not in granted:
        disp = "ESCALATE"; code = "ACT.AUTHORITY_REVIEW"
    else:
        disp = "PERMIT"; code = "ACT.PERMITTED"
    return AdapterResult(
        _STAGE, "action_shadow_v1", disp, [code],
        source_repr={"action": action, "granted": sorted(granted)},
        transformed_repr={"disposition": disp}, extra={"action_disposition": disp})
