"""Tenant-scoped human-review workflow (M9). A review queue over shadow dispositions, scoped per tenant.
Items enter when a disposition needs human review; reviewers (with shadow:review scope, own tenant only)
claim, view a redacted bundle, and record agree/override with a reason. Overrides are NEVER silent -
they carry a reason and are audited. Shadow-only; a review NEVER enforces or executes an action.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import security, data_controls as dc

# dispositions that route to human review
_REVIEW_TRIGGERS = {"WOULD_ESCALATE", "INDETERMINATE", "WOULD_REJECT"}


@dataclass
class ReviewItem:
    item_id: str
    tenant: str
    final_shadow_disposition: str
    reason_codes: List[str]
    replay_signature: str
    state: str = "queued"                 # queued | claimed | resolved
    reviewer: str = ""
    decision: str = ""                    # agree | override
    override_to: str = ""
    override_reason: str = ""


class ReviewQueue:
    def __init__(self):
        self._items: Dict[str, ReviewItem] = {}
        self._seq = 0

    def maybe_enqueue(self, tenant: str, response) -> Optional[str]:
        d = getattr(response, "final_shadow_disposition", "")
        needs = d in _REVIEW_TRIGGERS or getattr(response, "human_review_state", "") == "required"
        if not needs:
            return None
        self._seq += 1
        iid = f"REV{self._seq:05d}"
        self._items[iid] = ReviewItem(
            item_id=iid, tenant=tenant, final_shadow_disposition=d,
            reason_codes=[dc.redact(rc) for rc in getattr(response, "reason_codes", [])[:10]],
            replay_signature=getattr(response, "replay_signature", ""))
        return iid

    def queue_for(self, token: str, tenant: str) -> List[Dict[str, Any]]:
        acc = security.check_access(token, "shadow:review", tenant)
        if not acc.allowed:
            raise PermissionError(",".join(acc.reason_codes))
        return [self._bundle(i) for i in self._items.values()
                if i.tenant == tenant and i.state != "resolved"]

    def _bundle(self, it: ReviewItem) -> Dict[str, Any]:
        # redacted review bundle - no artifact text, dispositions + codes + signature only
        return {"item_id": it.item_id, "tenant": it.tenant,
                "final_shadow_disposition": it.final_shadow_disposition,
                "reason_codes": it.reason_codes, "replay_signature": it.replay_signature[:16],
                "state": it.state}

    def claim(self, token: str, tenant: str, item_id: str) -> bool:
        acc = security.check_access(token, "shadow:review", tenant)
        p = security.authenticate(token)
        it = self._items.get(item_id)
        if not acc.allowed or it is None or it.tenant != tenant:
            return False
        it.state = "claimed"; it.reviewer = p.principal
        return True

    def resolve(self, token: str, tenant: str, item_id: str, decision: str,
                override_to: str = "", override_reason: str = "") -> Dict[str, Any]:
        acc = security.check_access(token, "shadow:review", tenant)
        it = self._items.get(item_id)
        if not acc.allowed or it is None or it.tenant != tenant:
            return {"ok": False, "reason": "denied_or_missing"}
        if decision == "override" and not override_reason:
            return {"ok": False, "reason": "override_requires_reason"}   # no silent override
        it.state = "resolved"; it.decision = decision
        it.override_to = override_to; it.override_reason = override_reason
        # a review decision is advisory in shadow mode - it is recorded, NEVER enforced/executed
        return {"ok": True, "item_id": item_id, "decision": decision, "override_to": override_to,
                "enforced": False}
