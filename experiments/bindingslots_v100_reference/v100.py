#!/usr/bin/env python3
"""V100 always-verify decision logic (torch-free, deterministic).

For every query V100 performs EXACTLY ONE external-table read, compares the frozen neural prediction
to the current valid record, and returns a *verified* answer with provenance — or FAILS CLOSED
(abstains) whenever verification status cannot be established. At 100% legitimate write coverage V100
is reliability-equivalent to the table-only ceiling T0; it reads the table on every query and is NOT a
table-avoiding fast path or a latency optimization.

This module holds only the pure classification + response construction. The single read itself is
performed by ``v100_table.V100Table.read_for_verification`` (one SQL read, reason-aware). The model is
never trained or modified here — neural predictions arrive as already-computed token ids.
"""
from __future__ import annotations

import json

# Every result lands in EXACTLY ONE of these categories (abstention is never merged with incorrect).
CATEGORIES = (
    "verified_agreement_correct",
    "verified_correction_correct",
    "verified_return_incorrect",
    "abstained_missing_record",
    "abstained_invalid_record",
    "abstained_table_unavailable",
    "abstained_integrity_failure",
    "system_failure",
)

# Provenance that MUST be present and non-empty for a return to count as verified. Missing any field
# is an integrity failure -> fail closed.
REQUIRED_PROVENANCE = (
    "source_event_id", "evidence_reference", "version", "value_type",
    "authorization_scope", "session_id", "tenant_id", "memory_key",
)

# read_for_verification status -> abstention category (fail-closed mapping)
_INVALID_STATUSES = {"expired": "abstained_invalid_record",
                     "deleted": "abstained_invalid_record",
                     "stale": "abstained_invalid_record",
                     "missing": "abstained_missing_record",
                     "unauthorized": "abstained_integrity_failure"}


def provenance_complete(prov) -> bool:
    return isinstance(prov, dict) and all(prov.get(k) not in (None, "") for k in REQUIRED_PROVENANCE)


def _abstain(category, neural_pred, reason):
    return {"category": category, "status": "abstained", "answer": None, "verified": False,
            "corrected": False, "disagreement": None, "neural_pred": str(neural_pred),
            "table_value": None, "version": None, "provenance": None, "reason": reason}


def classify(*, neural_pred, target, read):
    """Classify one V100 query outcome from an already-performed single verification read.

    ``read`` is a mapping with keys: status ('ok'/'missing'/'expired'/'deleted'/'stale'/'unauthorized'),
    and — when status=='ok' — typed_value, version, provenance. ``target`` is the ground-truth value
    used ONLY to score correctness after the mechanical decision is made (never consulted to decide the
    return). Fail-closed: any non-'ok' status or incomplete provenance -> abstain.
    """
    neural = str(neural_pred)
    tgt = str(target)
    status = read.get("status")

    if status != "ok":
        cat = _INVALID_STATUSES.get(status, "abstained_integrity_failure")
        return _abstain(cat, neural, reason=status)

    prov = read.get("provenance")
    if not provenance_complete(prov):
        return _abstain("abstained_integrity_failure", neural, reason="incomplete_provenance")

    table_value = str(read.get("typed_value"))
    disagreement = (neural != table_value)
    # V100 always returns the validated table value (the current record), never the raw neural token.
    answer = table_value
    correct = (table_value == tgt)

    if not correct:
        # Only reachable if the stored record itself is wrong (does not happen at legitimate 100%
        # coverage with correct facts). Recorded honestly as an incorrect verified return.
        category = "verified_return_incorrect"
        vstatus = "verified_correction" if disagreement else "verified_agreement"
    elif disagreement:
        category = "verified_correction_correct"
        vstatus = "verified_correction"
    else:
        category = "verified_agreement_correct"
        vstatus = "verified_agreement"

    return {"category": category, "status": vstatus, "answer": answer, "verified": True,
            "corrected": bool(disagreement), "disagreement": bool(disagreement),
            "neural_pred": neural, "table_value": table_value, "version": read.get("version"),
            "provenance": prov, "reason": None}


def response_object(decision):
    """The externally-returned response object for a query (what a caller would receive). Provenance and
    version accompany every verified return; abstentions carry status + reason and never a fabricated
    answer."""
    return {
        "answer": decision["answer"],
        "status": decision["status"],
        "verified": decision["verified"],
        "corrected": decision["corrected"],
        "version": decision["version"],
        "provenance": decision["provenance"],
        "reason": decision["reason"],
    }


def serialize(decision) -> str:
    """Deterministic serialization of the final response object (used for end-to-end latency + as the
    on-the-wire form)."""
    return json.dumps(response_object(decision), sort_keys=True, separators=(",", ":"))
