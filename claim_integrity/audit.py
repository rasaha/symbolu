"""Audit-record serialization (Phase 9). A deterministic, replayable record of what a decomposition
did to a given input - input spans, produced claims, per-claim dispositions, and reason codes. No
timestamps (determinism/replay); ordering is stable.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from . import validation


def record(example: Dict[str, Any], produced: List[str]) -> Dict[str, Any]:
    aud = validation.audit(example, produced)
    return {
        "schema": "ci_audit_v1",
        "example_id": example["example_id"],
        "partition": example["partition"],
        "domain": example["domain"],
        "risk_class": example.get("risk_class", "low"),
        "input_text": example["original_text"],
        "produced_claims": list(produced),
        "example_disposition": aud["example_disposition"],
        "per_claim": aud["per_claim"],
    }


def serialize(rec: Dict[str, Any]) -> str:
    return json.dumps(rec, indent=2, sort_keys=True)
