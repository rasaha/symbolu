"""Deterministic, offline-verifiable pilot evidence pack.

The pack binds every artifact by fingerprint, contains references rather than
unnecessary raw source data, excludes credentials / raw authorization headers /
private incident notes / unnecessary identity data, and verifies offline. It fails
verification when modified or incomplete. It never enables enforcement.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple

from ..fingerprints import domain_hash

PACK_VERSION = "code_governance.pilot_evidence_pack.v1"
DOMAIN_EVIDENCE_PACK = "cg.pilot_study.evidence_pack.v1"

_SECTIONS = ("manifest", "pre_pilot_freeze", "amendments", "candidate_selection", "evaluations",
             "evidence_classification", "reviewer_protocol", "annotations", "checkpoints",
             "adverse_cases", "metrics", "calibration", "replay", "security", "integrity",
             "limitations", "readiness_verdict")
#: Patterns that must never appear in a credential-safe evidence pack.
_CREDENTIAL_PATTERNS = (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
                        re.compile(r"[Bb]earer\s+[A-Za-z0-9._-]{16,}"))
_PROHIBITED_KEYS = ("authorization", "cookie", "access_token", "api_key", "private_key",
                    "raw_response", "response_body", "incident_notes")


def _fingerprint_body(body: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in body.items() if k not in ("pack_fingerprint", "verification_manifest")}


def build_pilot_evidence_pack(
    *, pilot_id: str, tenant_id: str, sections: Mapping[str, List[Mapping[str, Any]]],
    evidence_status: str, readiness_verdict: str, limitations: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """Assemble a deterministic evidence pack from fingerprinted section entries."""
    body: Dict[str, Any] = {
        "pack_version": PACK_VERSION, "pilot_id": pilot_id, "tenant_id": tenant_id,
        "evidence_status": evidence_status, "readiness_verdict": readiness_verdict,
        "execution_status": "DISABLED", "limitations": list(limitations),
    }
    for name in _SECTIONS:
        body[name] = [dict(e) for e in sections.get(name, [])]
    body["verification_manifest"] = {
        "sections": {name: [e.get("record_id") or e.get("fingerprint")
                            for e in body[name]] for name in _SECTIONS},
        "counts": {name: len(body[name]) for name in _SECTIONS},
    }
    body["pack_fingerprint"] = domain_hash(DOMAIN_EVIDENCE_PACK, _fingerprint_body(body))
    return body


@dataclass(frozen=True)
class EvidencePackVerification:
    ok: bool
    issues: Tuple[str, ...] = ()


def verify_pilot_evidence_pack(pack: Mapping[str, Any]) -> EvidencePackVerification:
    """Verify an evidence pack entirely offline (no store connection)."""
    issues: List[str] = []
    if pack.get("pack_version") != PACK_VERSION:
        return EvidencePackVerification(False, ("unsupported pack version",))
    if pack.get("execution_status") != "DISABLED":
        issues.append("execution-disabled marker missing/altered")

    # Pack fingerprint (recompute over the body minus fingerprint + manifest).
    if domain_hash(DOMAIN_EVIDENCE_PACK, _fingerprint_body(pack)) != pack.get("pack_fingerprint"):
        issues.append("pack fingerprint mismatch")

    # Inventory: declared counts must match section lengths (missing/extra records).
    vm = pack.get("verification_manifest", {})
    counts = vm.get("counts", {})
    for name in _SECTIONS:
        section = pack.get(name, [])
        if counts.get(name) != len(section):
            issues.append(f"section {name} inventory mismatch")

    # Credential safety: no credential-like values or prohibited keys anywhere.
    serialized = json.dumps(pack, default=str)
    for pat in _CREDENTIAL_PATTERNS:
        if pat.search(serialized):
            issues.append("credential-like value present in evidence pack")
            break
    low = serialized.lower()
    for key in _PROHIBITED_KEYS:
        if f'"{key}"' in low:
            issues.append(f"prohibited key {key!r} present in evidence pack")

    return EvidencePackVerification(ok=not issues, issues=tuple(issues))


__all__ = ["PACK_VERSION", "build_pilot_evidence_pack", "verify_pilot_evidence_pack",
           "EvidencePackVerification"]
