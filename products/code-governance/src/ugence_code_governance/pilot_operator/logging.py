"""Structured, redacted pilot-operator logging.

Logs are JSON-compatible dicts with stable event types + reason codes and pilot
correlation fields. Central redaction removes credential-bearing values and drops
prohibited payloads (raw GitHub bodies, raw identity profiles, private incident
notes, source code). Redaction is case- and separator-insensitive and does NOT
mangle legitimate fields like ``token_count`` or ``credential_policy_ref``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

REDACTED = "[REDACTED]"

_SECRET_WORDS = ("authorization", "cookie", "token", "access_token", "api_key", "apikey",
                 "secret", "private_key", "privatekey", "credential", "password", "passwd",
                 "bearer")
#: Keys ending in one of these are benign metadata, not secret values.
_SAFE_SUFFIXES = ("_count", "_ref", "_policy", "_policy_ref", "_result", "_results",
                  "_scanner", "_classification", "_name", "_names", "_kind", "_id",
                  "_version", "_status", "_refs")
_SAFE_KEYS = {"token_count", "secret_scanner_result", "credential_policy_ref",
              "credential_resolver_ref", "credential_references", "environment_variable_name",
              "reviewer_role", "reference_id", "resolver_kind"}
#: Keys whose values are prohibited payloads and are dropped entirely.
_DROP_KEYS = {"response_body", "raw_response", "body", "source_code", "identity_profile",
              "incident_notes", "raw_identity", "diff"}


def _normalize(key: str) -> str:
    return key.lower().replace("-", "_").replace(" ", "_")


def is_secret_key(key: str) -> bool:
    """Whether a field name should have its value redacted."""
    norm = _normalize(key)
    if norm in _SAFE_KEYS:
        return False
    if not any(w in norm for w in _SECRET_WORDS):
        return False
    if norm.endswith(_SAFE_SUFFIXES):
        return False
    return True


def redact(value: Any) -> Any:
    """Recursively redact secret values and drop prohibited payloads."""
    if isinstance(value, Mapping):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if _normalize(str(k)) in _DROP_KEYS:
                continue
            out[str(k)] = REDACTED if is_secret_key(str(k)) else redact(v)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


@dataclass
class PilotLogger:
    """Collects structured, redacted operator log events (JSON-compatible)."""

    pilot_id: str
    run_id: str
    tenant_id: str
    events: List[Dict[str, Any]] = field(default_factory=list)

    def log(self, *, level: str, event_type: str, status: str = "", reason_code: str = "",
            correlation: str = "", **fields: Any) -> Dict[str, Any]:
        """Emit one structured, redacted log event."""
        record = {
            "level": level, "event_type": event_type, "status": status,
            "reason_code": reason_code, "correlation": correlation,
            "pilot_id": self.pilot_id, "run_id": self.run_id, "tenant_id": self.tenant_id,
        }
        record.update(fields)
        redacted = redact(record)
        self.events.append(redacted)
        return redacted


__all__ = ["REDACTED", "is_secret_key", "redact", "PilotLogger"]
