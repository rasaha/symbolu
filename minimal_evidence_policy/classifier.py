"""Phase 8 - Minimal-policy classifier entry point + audit/replay.

classify(item) returns a validated Decision and never raises. If the item lacks derived metadata (raw
text, e.g. the internal pilot), a small surface metadata deriver populates it - the metadata derivation
is a shared surface step; the obligation LOGIC lives in policy.py/invariants.py.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any, Dict

from minimal_evidence_policy import policy, schema as s
from minimal_evidence_policy import ground_truth as _gt   # surface metadata deriver (not the obligation)

AUDIT_VERSION = "minimal_evidence_audit_v1"
_META_FIELDS = ("claim_family", "risk_tier", "source_role", "claim_actionability", "temporal_sensitivity")


def _ensure_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    if all(item.get(f) for f in ("claim_family", "risk_tier")):
        return item
    md = _gt.derive_metadata(item.get("text", ""), item.get("source_path", ""),
                             item.get("source_kind", "doc"))
    return {**md, **item}   # explicit item fields win


def classify(item: Dict[str, Any], ablate: frozenset = frozenset()) -> s.Decision:
    try:
        it = _ensure_metadata(item)
        d = policy.assign(it, ablate=ablate)
    except Exception as e:  # fail-closed
        return s.Decision(claim_id=item.get("artifact_id", "claim"), risk_floor=s.ER,
                          final_obligation=s.ER, review_required=True,
                          reason_codes=[f"CLASSIFIER.EXCEPTION:{type(e).__name__}"])
    return d


def audit_record(d: s.Decision) -> Dict[str, Any]:
    r = asdict(d)
    r["audit_version"] = AUDIT_VERSION
    r["replay_signature"] = replay_signature(d)
    return r


def replay_signature(d: s.Decision) -> str:
    payload = {"claim_id": d.claim_id, "risk_floor": d.risk_floor,
               "final_obligation": d.final_obligation, "modifiers": d.modifiers_applied,
               "invariants": d.invariants_triggered, "reason_codes": d.reason_codes}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
