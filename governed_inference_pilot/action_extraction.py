"""Action proposal extraction (Phase 12). Extracts ONLY explicit proposed actions. Does not infer an
action from advice/analysis. Ambiguous proposals are marked INDETERMINATE. Deterministic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# explicit imperative action verbs (advice/analysis verbs are deliberately excluded)
_ACTION_VERBS = ("transfer", "delete", "deploy", "disable", "enable", "grant", "revoke", "send",
                 "purchase", "terminate", "refund", "escalate", "shut down", "restart")


@dataclass
class ExtractedAction:
    found: bool
    ambiguous: bool = False
    action: Optional[Dict[str, Any]] = None
    reason_codes: List[str] = field(default_factory=list)


def extract(model_output: str, declared_action: Optional[Dict[str, Any]]) -> ExtractedAction:
    """Prefer an explicit declared action fixture; else scan for an explicit imperative. Advice text
    ('should consider', 'is recommended') never yields an action."""
    if declared_action is not None:
        return ExtractedAction(found=True, action=declared_action, reason_codes=["ACT.EXPLICIT"])
    text = model_output.lower()
    hits = [v for v in _ACTION_VERBS if re.search(rf"\b{re.escape(v)}\b", text)]
    if not hits:
        return ExtractedAction(found=False, reason_codes=["GIP.ACTION_ABSENT"])
    # an imperative buried in advisory framing is ambiguous
    advisory = any(w in text for w in ("consider", "recommended", "may want", "could"))
    if advisory:
        return ExtractedAction(found=True, ambiguous=True,
                               action={"action_type": hits[0], "ambiguous": True},
                               reason_codes=["GIP.ACTION_AMBIGUOUS"])
    return ExtractedAction(found=True, action={"action_type": hits[0], "reversibility": "reversible",
                                               "risk": "medium", "required_authority": ""},
                           reason_codes=["ACT.EXPLICIT_IMPERATIVE"])
