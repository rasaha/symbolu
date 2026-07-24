"""Phase 9 - Obligation audit + replay.

An immutable audit record for each obligation decision and a deterministic replay signature over the
decision-bearing content, so obligation assignments are reproducible and drift is detectable. No
wall-clock. Stdlib-only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any, Dict

from evidence_obligation import schema as s

AUDIT_VERSION = "evidence_obligation_audit_v1"


def audit_record(o: s.EvidenceObligation) -> Dict[str, Any]:
    d = asdict(o)
    d["audit_version"] = AUDIT_VERSION
    d["replay_signature"] = replay_signature(o)
    return d


def replay_signature(o: s.EvidenceObligation) -> str:
    payload = {
        "claim_id": o.claim_id,
        "claim_type": o.claim_type,
        "risk_tier": o.risk_tier,
        "source_role": o.source_role,
        "evidence_obligation_type": o.evidence_obligation_type,
        "minimum_evidence_standard": o.minimum_evidence_standard,
        "required_source_classes": o.required_source_classes,
        "reason_codes": o.reason_codes,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
