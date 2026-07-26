"""Deterministic multi-policy provider resolution (Tasks 7, 8, 10).

Four explicit policies — FIXED, ORDERED, CAPABILITY_REQUIRED, BOUNDED_FALLBACK —
built on the framework's compatibility/capability/health primitives. Selection is
deterministic (ordered by preference then provider id — never dictionary
traversal), auditable (a full SelectionRecord), and provider-neutral (it never
sees a provider result). Because selection happens strictly before invocation,
substantive governance results can never influence it — governance shopping is
structurally impossible here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from governance_providers.version import is_contract_compatible, TARGET_KERNEL_MAJOR

from .catalog import CatalogEntry, ProviderCatalog


class ResolutionPolicy(str, Enum):
    FIXED = "FIXED"
    ORDERED = "ORDERED"
    CAPABILITY_REQUIRED = "CAPABILITY_REQUIRED"
    BOUNDED_FALLBACK = "BOUNDED_FALLBACK"


@dataclass(frozen=True)
class SelectionRequest:
    kind: str
    policy: ResolutionPolicy
    fixed_id: str = ""
    preference_order: tuple = ()
    required_capabilities: tuple = ()
    allow_fallback: bool = False
    allow_degraded: bool = False


@dataclass
class SelectionRecord:
    request_id: str
    provider_kind: str
    resolution_policy: str
    candidate_provider_ids: tuple
    candidate_versions: dict
    candidate_health: dict
    candidate_compatibility: dict
    required_capabilities: tuple
    rejection_reasons: dict
    selected_provider_id: Optional[str]
    selected_provider_version: Optional[str]
    fallback_used: bool
    fallback_reason: str
    resolution_fingerprint: str = ""

    @property
    def resolved(self) -> bool:
        return self.selected_provider_id is not None


def _eligibility(entry: CatalogEntry, req: SelectionRequest) -> Optional[str]:
    """Return a rejection reason, or None if the candidate is eligible."""
    st = entry.state
    if entry.kind != req.kind:
        return "WRONG_KIND"
    if not st.enabled:
        return "DISABLED"
    if not (st.compatible and is_contract_compatible(st.contract_version)):
        return "INCOMPATIBLE"
    if st.health == "UNAVAILABLE":
        return "UNHEALTHY_UNAVAILABLE"
    if st.health == "DEGRADED" and not req.allow_degraded:
        return "DEGRADED_NOT_ALLOWED"
    if not set(req.required_capabilities) <= set(entry.capabilities):
        return "MISSING_CAPABILITY"
    return None


def _ordered(candidates: list, req: SelectionRequest) -> list:
    order = {pid: i for i, pid in enumerate(req.preference_order)}
    return sorted(candidates, key=lambda e: (order.get(e.provider_id, len(order)), e.provider_id))


def select(catalog: ProviderCatalog, req: SelectionRequest, *, request_id: str
           ) -> tuple:
    candidates = _ordered(catalog.list_by_kind(req.kind), req)
    reasons: dict = {}
    eligible: list = []
    for e in candidates:
        r = _eligibility(e, req)
        if r is None:
            eligible.append(e)
        else:
            reasons[e.provider_id] = r

    selected: Optional[CatalogEntry] = None
    fallback_used = False
    fallback_reason = ""
    eligible_ids = [e.provider_id for e in eligible]

    if req.policy is ResolutionPolicy.FIXED:
        selected = next((e for e in eligible if e.provider_id == req.fixed_id), None)
        # a fixed policy never falls back
    elif req.policy is ResolutionPolicy.ORDERED:
        selected = eligible[0] if eligible else None
    elif req.policy is ResolutionPolicy.CAPABILITY_REQUIRED:
        # eligibility already enforces required capabilities
        selected = eligible[0] if eligible else None
    elif req.policy is ResolutionPolicy.BOUNDED_FALLBACK:
        preferred_id = req.preference_order[0] if req.preference_order else req.fixed_id
        preferred = next((e for e in eligible if e.provider_id == preferred_id), None)
        if preferred is not None:
            selected = preferred
        elif req.allow_fallback and eligible:
            selected = eligible[0]
            fallback_used = True
            fallback_reason = reasons.get(preferred_id, "PREFERRED_NOT_ELIGIBLE")

    record = SelectionRecord(
        request_id=request_id, provider_kind=req.kind, resolution_policy=req.policy.value,
        candidate_provider_ids=tuple(e.provider_id for e in candidates),
        candidate_versions={e.provider_id: e.version for e in candidates},
        candidate_health={e.provider_id: e.state.health for e in candidates},
        candidate_compatibility={e.provider_id: bool(e.state.compatible
                                                     and is_contract_compatible(e.state.contract_version))
                                 for e in candidates},
        required_capabilities=tuple(req.required_capabilities),
        rejection_reasons=reasons,
        selected_provider_id=selected.provider_id if selected else None,
        selected_provider_version=selected.version if selected else None,
        fallback_used=fallback_used, fallback_reason=fallback_reason)
    record.resolution_fingerprint = _fingerprint(record)
    return selected, record


def _fingerprint(rec: SelectionRecord) -> str:
    payload = json.dumps({
        "kind": rec.provider_kind, "policy": rec.resolution_policy,
        "candidates": sorted(rec.candidate_provider_ids),
        "versions": rec.candidate_versions, "health": rec.candidate_health,
        "compat": rec.candidate_compatibility,
        "required": sorted(rec.required_capabilities),
        "rejections": rec.rejection_reasons,
        "selected": rec.selected_provider_id, "fallback": rec.fallback_used,
        "fallback_reason": rec.fallback_reason,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
