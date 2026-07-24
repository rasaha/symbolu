"""Observability (M7). Tenant-scoped metrics and events derived from shadow runs. In-memory, no external
sink, no PII (operates on dispositions/reason codes only). Deterministic, shadow-only.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List


class Metrics:
    def __init__(self):
        self._counts: Dict[str, Counter] = defaultdict(Counter)   # tenant -> disposition counts
        self._reason: Dict[str, Counter] = defaultdict(Counter)
        self._events: List[Dict[str, Any]] = []

    def record(self, tenant: str, response) -> None:
        d = getattr(response, "final_shadow_disposition", "UNKNOWN")
        self._counts[tenant][d] += 1
        for rc in getattr(response, "reason_codes", [])[:5]:
            self._reason[tenant][rc.split(":")[0]] += 1
        # event carries NO artifact text - dispositions/codes only
        self._events.append({"tenant": tenant, "disposition": d,
                             "accepted": getattr(response, "accepted", False)})

    def tenant_summary(self, tenant: str) -> Dict[str, Any]:
        c = self._counts[tenant]
        total = sum(c.values())
        unsafe = c.get("WOULD_ALLOW", 0)     # in shadow, an ALLOW on a should-withhold is the watch metric
        return {"tenant": tenant, "total": total, "dispositions": dict(c),
                "allow_rate": round(unsafe / total, 4) if total else 0.0,
                "top_reasons": dict(self._reason[tenant].most_common(5))}

    def pilot_summary(self) -> Dict[str, Any]:
        allt = Counter()
        for c in self._counts.values():
            allt.update(c)
        return {"tenants": list(self._counts), "total": sum(allt.values()),
                "dispositions": dict(allt), "n_events": len(self._events)}


# alert rules over the metrics (detection signals for incidents)
def alerts(metrics: Metrics, tenant: str) -> List[str]:
    s = metrics.tenant_summary(tenant)
    out = []
    if s["total"] >= 10 and s["allow_rate"] > 0.9:
        out.append("ALERT.HIGH_ALLOW_RATE")           # possible governance bypass / mis-tiering
    if s["dispositions"].get("CONTRACT_ERROR", 0) > 0.2 * max(1, s["total"]):
        out.append("ALERT.HIGH_CONTRACT_ERROR")        # integration/adapter problem
    if s["dispositions"].get("PIPELINE_ERROR", 0) > 0:
        out.append("ALERT.PIPELINE_ERROR")
    return out
