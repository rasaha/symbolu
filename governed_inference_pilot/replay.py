"""Replay engine (Phase 6). Deterministic. Compares a stored audit trace against a re-run (or another
trace) and detects drift. NEVER calls live models - replay operates on stored fixtures/traces only.

Modes:
  - exact:            re-run must reproduce the replay signature byte-for-byte
  - policy:           re-run with original stage evidence; dispositions must match
  - adapter_version:  compare two traces produced by different adapter versions
  - component_version:compare two traces produced by different component versions
  - disposition_only: compare only the final + per-stage dispositions (ignore reason-code detail)
  - failure_injection:replay a trace where a fault was injected; must remain fail-closed
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .audit import AuditTrace


@dataclass
class ReplayResult:
    mode: str
    deterministic: bool
    drift: List[str] = field(default_factory=list)
    detail: Dict[str, Any] = field(default_factory=dict)


def _event_map(trace: AuditTrace) -> Dict[str, Dict[str, Any]]:
    return {e.stage: {"disposition": e.disposition, "shadow_outcome": e.shadow_outcome,
                      "reason_codes": e.reason_codes} for e in trace.events}


def compare(baseline: AuditTrace, candidate: AuditTrace, mode: str = "exact") -> ReplayResult:
    drift: List[str] = []
    detail: Dict[str, Any] = {}

    # missing artifacts / hash mismatch
    if baseline.request_snapshot != candidate.request_snapshot and mode != "policy":
        drift.append("input_drift")
    if baseline.source_artifact_hashes != candidate.source_artifact_hashes:
        drift.append("hash_mismatch")
    if baseline.component_versions != candidate.component_versions and mode not in (
            "component_version", "adapter_version"):
        drift.append("component_drift")
    if baseline.policy_versions != candidate.policy_versions and mode != "adapter_version":
        drift.append("policy_drift")

    bmap, cmap = _event_map(baseline), _event_map(candidate)
    # vocabulary drift: a stage disposition that changed value
    for stage in set(bmap) | set(cmap):
        b = bmap.get(stage)
        c = cmap.get(stage)
        if b is None or c is None:
            drift.append(f"missing_stage:{stage}")
            continue
        if b["disposition"] != c["disposition"] or b["shadow_outcome"] != c["shadow_outcome"]:
            drift.append(f"disposition_drift:{stage}")
            detail[stage] = {"baseline": b, "candidate": c}
        elif mode not in ("disposition_only",) and b["reason_codes"] != c["reason_codes"]:
            drift.append(f"reason_code_drift:{stage}")

    if mode == "exact":
        sig_ok = baseline.replay_signature == candidate.replay_signature
        if not sig_ok:
            drift.append("signature_mismatch")
        detail["signatures"] = {"baseline": baseline.replay_signature,
                                "candidate": candidate.replay_signature}

    if mode == "failure_injection":
        # a fault must not produce a permissive outcome
        if candidate.final_shadow_disposition in ("WOULD_ALLOW",):
            drift.append("unsafe_fallback_under_fault")

    deterministic = not any(d.startswith(("signature_mismatch", "disposition_drift", "input_drift"))
                            for d in drift)
    return ReplayResult(mode=mode, deterministic=deterministic, drift=drift, detail=detail)


def self_replay(trace: AuditTrace) -> ReplayResult:
    """Exact replay of a trace against itself: must be perfectly deterministic (a sanity gate)."""
    return compare(trace, trace, mode="exact")
