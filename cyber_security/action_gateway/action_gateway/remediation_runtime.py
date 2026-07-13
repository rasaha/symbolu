"""Runtime glue for the R1 remediation projection (R1.5).

Advisory-only. This module does NOT touch the gate, hashing, tokens, approvals, evidence, or
the decision — it (a) clamps a requested disclosure mode to what the caller is trusted for, so
a privileged mode is never granted by request alone, and (b) bounds the remediation payload
size for transport safety. Everything here runs strictly AFTER a finalized decision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ._ref import remediation as R

DEFAULT_MAX_REQUIRED_CHANGES = 32
DEFAULT_MAX_PAYLOAD_BYTES = 16384

_PRIVILEGED = (R.TRUSTED_PLANNER, R.HUMAN_ONLY, R.FULL)


@dataclass(frozen=True)
class RemediationLimits:
    max_required_changes: int = DEFAULT_MAX_REQUIRED_CHANGES
    max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES


DEFAULT_LIMITS = RemediationLimits()


def normalize_mode(mode) -> str:
    """Normalize a mode string; unknown -> OFF (safe default, never raises at runtime)."""
    if not mode:
        return R.OFF
    m = str(mode).upper().replace("-", "_")
    return m if m in R.DISCLOSURE_MODES else R.OFF


def clamp_mode(requested, trusted: bool) -> str:
    """Effective mode = requested, unless a privileged mode is requested without trust, in
    which case it is clamped down to STANDARD. A privileged mode is NEVER reachable without an
    established trusted caller context."""
    m = normalize_mode(requested)
    if m in _PRIVILEGED and not trusted:
        return R.STANDARD
    return m


def _size(obj) -> int:
    return len(json.dumps(obj, sort_keys=True).encode("utf-8"))


def apply_limits(rem: dict, limits: RemediationLimits = DEFAULT_LIMITS) -> dict:
    """Bound the payload: cap required_changes count, then shed all_unmet_conditions and trim
    required_changes until under max_payload_bytes. Marks truncation honestly. Pure (returns a
    new dict); never touches decision fields."""
    if not rem:
        return rem
    out = dict(rem)
    out["required_changes"] = list(rem.get("required_changes", []))
    out["all_unmet_conditions"] = list(rem.get("all_unmet_conditions", []))
    disc = dict(rem.get("disclosure", {}))
    marks: list[str] = []

    if len(out["required_changes"]) > limits.max_required_changes:
        out["required_changes"] = out["required_changes"][: limits.max_required_changes]
        marks.append(f"required_changes[>{limits.max_required_changes}]")

    if _size(out) > limits.max_payload_bytes and out["all_unmet_conditions"]:
        out["all_unmet_conditions"] = []
        marks.append("all_unmet_conditions:size")
    while _size(out) > limits.max_payload_bytes and out["required_changes"]:
        out["required_changes"] = out["required_changes"][:-1]
        if "required_changes:size" not in marks:
            marks.append("required_changes:size")

    if marks:
        disc["redacted_fields"] = sorted(set(disc.get("redacted_fields", [])) | set(marks))
        disc["truncated"] = True
    out["disclosure"] = disc
    return out
