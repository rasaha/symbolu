"""Evidence & simulation envelopes bound to an action_hash (spec §13).

Evidence generated for one action cannot be accepted for another (bound_to
check). Simulation evidence is STRUCTURED — never a SAFE/UNSAFE boolean.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import canon_profile as cp
from . import hashing, jcs
from .errors import EvidenceBindingError, GateError

_FIDELITY_ORDER = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
_FORBIDDEN_SIM_KEYS = {"safe", "unsafe", "verdict", "ok", "pass", "allow"}


def _parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def content_digest(content, *, domain: str = "EVIDENCE",
                   algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID) -> str:
    return hashing.domain_digest(domain, jcs.canonicalize(content), algorithm_id=algorithm_id)


def build_evidence(
    *, bound_to: str, producer: str, generated_at: str, valid_until: str,
    evidence_version: str, kind: str, fidelity_or_confidence, content: dict,
    is_simulation: bool = False, algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
) -> dict:
    domain = "SIMULATION" if is_simulation else "EVIDENCE"
    if is_simulation:
        # structured only: reject boolean verdict fields
        for k in content:
            if k.lower() in _FORBIDDEN_SIM_KEYS and isinstance(content[k], bool):
                raise GateError(f"simulation evidence must be structured, not a "
                                f"SAFE/UNSAFE boolean (key {k!r})")
    payload = {
        "bound_to": bound_to,
        "producer": producer,
        "generated_at": generated_at,
        "valid_until": valid_until,
        "evidence_version": evidence_version,
        "kind": kind,
        "fidelity_or_confidence": fidelity_or_confidence,
        "content_digest": content_digest(content, domain=domain, algorithm_id=algorithm_id),
    }
    ev_hash = hashing.domain_digest(domain, jcs.canonicalize(payload), algorithm_id=algorithm_id)
    return {"payload": payload, "evidence_hash": ev_hash, "domain": domain,
            "hash_algorithm_id": algorithm_id}


def verify_binding(evidence: dict, action_hash: str) -> bool:
    if evidence["payload"]["bound_to"] != action_hash:
        raise EvidenceBindingError("evidence bound to a different action")
    return True


def is_fresh(evidence: dict, now: str) -> bool:
    return _parse_ts(now) < _parse_ts(evidence["payload"]["valid_until"])


def fidelity_at_least(evidence: dict, minimum: str) -> bool:
    f = evidence["payload"]["fidelity_or_confidence"]
    if not isinstance(f, str) or f not in _FIDELITY_ORDER:
        return False
    return _FIDELITY_ORDER[f] >= _FIDELITY_ORDER[minimum]
