"""The MEU's ledger kinds, and the schema that refuses content-bearing keys.

D-4 (``SPEC_MODEL_EGRESS_UNIT.md`` §4.4): *"The append-only audit ledger may retain only
identifiers, digests, references, enumerated outcomes, metering and provenance. For
Model Egress Unit ledger kinds, enforce this through a kind-specific schema that refuses
content-bearing keys."* The control plane's ``LedgerEntry`` accepts any canonical
mapping; this module is the kind-specific refusal it asked for, applied before a
payload ever reaches an entry.

The exchange holds content, briefly. The ledger never does. A payload for one of these
kinds is refused if it carries a key outside the kind's allowlist, a key that names
content anywhere in its nesting, or a string long enough to *be* content.
"""

from __future__ import annotations

from typing import Any, Mapping

from .records import EgressResult

__all__ = [
    "MEU_LEDGER_KINDS",
    "CONTENT_BEARING_KEYS",
    "MAX_LEDGER_STRING",
    "LedgerKindViolation",
    "ledger_payload",
    "result_ledger_payload",
]

#: Every kind the unit appends. A payload under any other ``meu.`` kind is refused.
MEU_LEDGER_KINDS: Mapping[str, frozenset] = {
    "meu.request_submitted": frozenset({
        "request_id", "tenant_id", "correlation_id", "request_digest", "content_digest",
        "minimized_context_digest", "exchange_schema_version", "authorized_vendor",
        "authorized_model", "clearance_ref", "clearance_digest", "policy_id", "reservation_id",
        "submitted_at", "not_valid_after", "unit_count", "token_count",
    }),
    "meu.result_recorded": frozenset({
        "request_id", "tenant_id", "correlation_id", "recorded_at", "outcome", "adapter_id",
        "provenance", "content_digest", "refusal_reason", "result_digest", "trust",
    }),
    "meu.content_purged": frozenset({
        "request_id", "tenant_id", "correlation_id", "purged_at", "request_digest",
        "result_digest", "content_digest", "outcome", "acknowledged_at", "reservation_id",
        "authorized_vendor", "authorized_model", "provenance",
    }),
    "meu.credential_leased": frozenset({
        "kind", "request_digest", "tenant_id", "vendor", "credential_profile",
        "custody_authority_id", "observed_at", "outcome", "lease_id", "secret_version_ref",
        "expires_at", "is_production_authoritative", "refusal",
    }),
    "meu.credential_refused": frozenset({
        "kind", "request_digest", "tenant_id", "vendor", "credential_profile",
        "custody_authority_id", "observed_at", "outcome", "lease_id", "secret_version_ref",
        "expires_at", "is_production_authoritative", "refusal",
    }),
}

#: Keys that name content or a credential, refused at any depth, in any case.
CONTENT_BEARING_KEYS = frozenset({
    "payload", "text", "prompt", "response", "content", "minimized_context", "units",
    "messages", "input", "output", "completion", "answer", "body", "secret", "credential",
    "api_key", "apikey", "token", "bearer", "authorization", "password", "private_key",
    "client_secret", "cookie", "session",
})

#: Longer than any identifier, digest, reference or enumerated value the unit writes.
MAX_LEDGER_STRING = 512


class LedgerKindViolation(ValueError):
    """A payload that the MEU's ledger kinds refuse."""


def _walk(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, inner in value.items():
            if not isinstance(key, str):
                raise LedgerKindViolation(f"{path}: keys must be strings")
            if key.lower() in CONTENT_BEARING_KEYS:
                raise LedgerKindViolation(
                    f"{path}.{key}: a content-bearing key never reaches the ledger (D-4)")
            _walk(inner, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, inner in enumerate(value):
            _walk(inner, f"{path}[{index}]")
    elif isinstance(value, str):
        if len(value) > MAX_LEDGER_STRING:
            raise LedgerKindViolation(
                f"{path}: a {len(value)}-character string is content, not a reference")
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise LedgerKindViolation(f"{path}: {type(value).__name__} is not a ledger value")


def ledger_payload(kind: str, payload: Mapping[str, Any]) -> dict:
    """The payload as the ledger may hold it, or a :class:`LedgerKindViolation`."""

    allowed = MEU_LEDGER_KINDS.get(kind)
    if allowed is None:
        raise LedgerKindViolation(f"{kind!r} is not a Model Egress Unit ledger kind")
    if not isinstance(payload, Mapping):
        raise LedgerKindViolation(f"{kind}: payload must be a mapping")
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise LedgerKindViolation(f"{kind}: keys {unknown} are outside the kind's schema")
    _walk(payload, kind)
    return dict(payload)


def result_ledger_payload(result: EgressResult) -> dict:
    """What the ledger holds for a result: everything the result digest binds, and
    never the payload. The content digest stands in for the content."""

    body = result.digest_body()
    body["recorded_at"] = result.recorded_at.isoformat()
    body["result_digest"] = result.digest()
    return ledger_payload("meu.result_recorded", body)
