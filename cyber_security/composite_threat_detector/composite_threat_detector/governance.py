"""Resource governance against state-exhaustion (§7).

Deterministic controls layered on top of the ledger's structural caps. When a
limit is reached the analyzer never silently drops evidence: it emits
``UNAVAILABLE`` (or, per policy, escalates), records the exact limit, records any
eviction in the append-only audit log, and preserves enough metadata for later
reconstruction.

Priority retention: when eviction is unavoidable, lower-severity, more-decayed
assemblies are evicted before higher-severity ones. Eviction is audited, never
silent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ledger import StateLimits

_SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def severity_rank(sev: str) -> int:
    return _SEVERITY_RANK.get(sev, 0)


@dataclass
class GovernorDecision:
    admit: bool
    reason: str = ""
    limit: str = ""
    evicted: tuple[str, ...] = ()
    overload: bool = False


@dataclass
class ResourceGovernor:
    """Per-tenant / per-actor quota + candidate-linkage governance."""

    limits: StateLimits
    # per-tenant per-actor assembly-key sets (bounded bookkeeping)
    _actor_assemblies: dict = field(default_factory=dict)
    rejected_events: int = 0
    deferred_events: int = 0
    evictions: int = 0
    overload_events: int = 0

    def check_candidate_linkages(self, n: int) -> GovernorDecision:
        if n > self.limits.max_candidate_linkages_per_event:
            self.rejected_events += 1
            return GovernorDecision(
                admit=False, overload=True,
                reason=f"event produced {n} candidate linkages > "
                       f"max_candidate_linkages_per_event="
                       f"{self.limits.max_candidate_linkages_per_event}",
                limit="max_candidate_linkages_per_event")
        return GovernorDecision(admit=True)

    def check_actor(self, tenant_id: str, actor: str, assembly_key: str) -> GovernorDecision:
        if not actor:
            return GovernorDecision(admit=True)
        key = (tenant_id, actor)
        seen = self._actor_assemblies.setdefault(key, set())
        if assembly_key in seen:
            return GovernorDecision(admit=True)
        if len(seen) >= self.limits.max_assemblies_per_actor:
            self.rejected_events += 1
            return GovernorDecision(
                admit=False, overload=True,
                reason=f"actor {actor!r} exceeds max_assemblies_per_actor="
                       f"{self.limits.max_assemblies_per_actor}",
                limit="max_assemblies_per_actor")
        seen.add(assembly_key)
        return GovernorDecision(admit=True)

    def metrics(self) -> dict:
        return {
            "rejected_events": self.rejected_events,
            "deferred_events": self.deferred_events,
            "evictions": self.evictions,
            "overload_events": self.overload_events,
        }
