"""Data classification, permitted-use, redaction/minimization, secrets/encryption interfaces, and
retention/deletion/export controls (M5). NON-ENFORCING, shadow-only. Deterministic, stdlib-only. No
real keys, no real crypto, no real data egress - interfaces and controls only.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---- classification & permitted use -------------------------------------------------------------
CLASSES = ("public", "internal", "confidential", "restricted")
_RESTRICTED_MARKERS = re.compile(r"\b(ssn|social security|patient|pii|phi|credit card|password|secret)\b", re.I)
_CONFIDENTIAL_MARKERS = re.compile(r"\b(salary|revenue|contract|acquisition|roadmap)\b", re.I)

# permitted-use matrix: a request's declared clearance (data_sensitivity) -> the artifact classes it
# may process. Higher clearance handles more; a restricted artifact needs restricted clearance.
_CLEARANCE_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
_PERMITTED = {
    "public": {"public"},
    "internal": {"public", "internal"},
    "confidential": {"public", "internal", "confidential"},
    "restricted": {"public", "internal", "confidential", "restricted"},
}


def classify(text: str) -> str:
    if _RESTRICTED_MARKERS.search(text or ""):
        return "restricted"
    if _CONFIDENTIAL_MARKERS.search(text or ""):
        return "confidential"
    return "internal"


def permitted_use(artifact_class: str, request_sensitivity: str) -> bool:
    """The request's declared data_sensitivity must be cleared to handle the artifact's class."""
    return artifact_class in _PERMITTED.get(request_sensitivity, set())


# ---- redaction & minimization -------------------------------------------------------------------
_REDACT_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b\d{16}\b"), "[CARD]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    (re.compile(r"(?i)\b(password|secret|token)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
]


def redact(text: str) -> str:
    out = text or ""
    for rx, repl in _REDACT_PATTERNS:
        out = rx.sub(repl, out)
    return out


# fields retained in a minimized shadow record (data minimization: keep only what governance needs)
_MINIMAL_FIELDS = ("request_id", "tenant_id", "risk_tier", "domain", "final_shadow_disposition",
                   "stage_dispositions", "reason_codes")


def minimize(record: Dict[str, Any]) -> Dict[str, Any]:
    return {k: record[k] for k in _MINIMAL_FIELDS if k in record}


# ---- secrets & encryption interfaces (stubs; NO real keys) --------------------------------------
@dataclass
class SecretRef:
    key_id: str
    provider: str = "pilot-vault-stub"       # interface only; no real KMS


def encrypt_at_rest(data: str, ref: SecretRef) -> Dict[str, Any]:
    """Interface stub: returns a hashed 'ciphertext' handle, NOT real encryption. Documents the boundary
    where a real KMS/envelope-encryption would sit."""
    handle = hashlib.sha256((ref.key_id + "|" + data).encode()).hexdigest()
    return {"ciphertext_handle": handle, "key_id": ref.key_id, "algorithm": "STUB-NOT-REAL",
            "note": "interface only; real deployment must use a KMS"}


# ---- retention / deletion / export --------------------------------------------------------------
@dataclass
class RetentionPolicy:
    tenant: str
    max_records: int = 1000
    ttl_events: int = 90          # symbolic units, not days (determinism)


class TenantDataStore:
    """In-memory, tenant-scoped store with retention, deletion, and export controls. Shadow-only."""

    def __init__(self):
        self._data: Dict[str, List[Dict[str, Any]]] = {}

    def put(self, tenant: str, record: Dict[str, Any], policy: RetentionPolicy) -> None:
        recs = self._data.setdefault(tenant, [])
        recs.append(minimize(record))
        # retention: drop oldest beyond max_records
        if len(recs) > policy.max_records:
            del recs[0:len(recs) - policy.max_records]

    def get(self, tenant: str, principal_tenant: str) -> List[Dict[str, Any]]:
        if principal_tenant not in (tenant, "*"):
            raise PermissionError("cross_tenant_read_denied")
        return list(self._data.get(tenant, []))

    def delete_tenant(self, tenant: str) -> int:
        n = len(self._data.get(tenant, []))
        self._data.pop(tenant, None)
        return n                              # right-to-erasure: full tenant purge

    def export(self, tenant: str, principal_tenant: str, redact_text: bool = True) -> List[Dict[str, Any]]:
        recs = self.get(tenant, principal_tenant)
        # export is minimized + redacted by default
        return [minimize(r) for r in recs]
