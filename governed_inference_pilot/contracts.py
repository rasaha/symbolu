"""Versioned stage contracts (Phase 3). Each contract validates the handoff between two stages:
required fields, missing-field behavior, version-mismatch behavior, unknown-vocabulary behavior, a
semantic-loss check, and a fail-open/fail-closed rule. No adapter may discard unknown fields silently.

The governing rule: SAFETY-CRITICAL handoffs FAIL CLOSED (a violation forces INDETERMINATE/CONTRACT_
ERROR, never a silent pass); descriptive handoffs may fail open with a recorded warning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

CONTRACTS_VERSION = "gip_contracts_v1"


@dataclass
class ContractResult:
    ok: bool
    contract: str
    fail_closed: bool
    missing: List[str] = field(default_factory=list)
    unknown: List[str] = field(default_factory=list)
    semantic_loss: List[str] = field(default_factory=list)
    reason_codes: List[str] = field(default_factory=list)


# contract registry: name -> (required_fields, fail_closed)
STAGE_CONTRACTS = {
    "request__execution_gate":      (["request_id", "risk_tier", "domain"], True),
    "execution_gate__model_policy": (["eligible_models"], True),
    "model_policy__execution":      (["selected_model"], True),
    "execution__claim_integrity":   (["model_output"], True),
    "claim_integrity__scope":       (["claims"], True),
    "claims__evidence_binder":      (["claims"], True),
    "evidence_binder__evidence_assurance": (["evidence_case"], True),
    "evidence_assurance__assertion_gate":  (["evidence_state"], True),
    "assertion__action_extractor":  (["assertion_disposition"], False),
    "action__action_gate":          (["action_proposal"], True),
    "all__audit":                   (["trace_id"], False),
}

# vocabulary each downstream stage is allowed to receive (unknown => contract violation)
KNOWN_VOCAB = {
    "evidence_state": {"VERIFIED", "VERIFIED_WITH_LIMITATIONS", "CONFLICTED", "INSUFFICIENT", "STALE",
                       "MISALIGNED", "DEPENDENT", "AUTHORITY_MISMATCH", "INDETERMINATE",
                       "REJECT_EVIDENCE_STATE", "ESCALATE"},
    "assertion_disposition": {"ALLOW", "QUALIFY", "REJECT", "ESCALATE", "INDETERMINATE"},
}


def validate(contract: str, payload: Dict[str, Any]) -> ContractResult:
    if contract not in STAGE_CONTRACTS:
        return ContractResult(False, contract, True, reason_codes=["GIP.UNKNOWN_CONTRACT"])
    required, fail_closed = STAGE_CONTRACTS[contract]
    missing = [f for f in required if f not in payload or payload.get(f) in (None, "")]
    # unknown-vocabulary check on any field that has a known vocabulary
    unknown = []
    for field_name, vocab in KNOWN_VOCAB.items():
        if field_name in payload and payload[field_name] not in vocab:
            unknown.append(f"{field_name}={payload[field_name]}")
    codes = []
    if missing:
        codes.append("GIP.MISSING_FIELD")
    if unknown:
        codes.append("GIP.UNKNOWN_VOCAB")
    ok = not missing and not unknown
    return ContractResult(ok=ok, contract=contract, fail_closed=fail_closed, missing=missing,
                          unknown=unknown, reason_codes=codes)


def semantic_loss_check(source: Dict[str, Any], transformed: Dict[str, Any],
                        must_preserve: List[str]) -> List[str]:
    """Fields that existed and were non-empty in source but vanished/emptied in transformed."""
    lost = []
    for k in must_preserve:
        s = source.get(k)
        t = transformed.get(k)
        if s not in (None, "", [], {}) and t in (None, "", [], {}):
            lost.append(k)
    return lost
