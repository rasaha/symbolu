"""Module-local canonicalization helpers (stdlib only).

Two encodings, kept apart on purpose.

``canonical_text`` is the Governance Studio backend's own rule for a workflow document
(``serialization/canonical.py``: sorted keys, two-space indent, ``ensure_ascii`` off,
trailing newline). Using it here means the digest a draft records for its document is
byte-for-byte the digest the studio's ``validate_workflow`` operation reports as
``computed_digest`` and the digest the Bring Your Workflow screen computes in the
browser — one digest of record, three independent computations.

``canonical_json`` and ``domain_digest`` are the compact, domain-separated shape the
sibling integration packages use for derived ids and record digests — copied, never
imported. No clock is read anywhere in this package.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .errors import ContractViolation

_NAMESPACE = "workflow_drafts"
_US = "\x1f"


def canonical_text(document: Any) -> str:
    """The studio's canonical encoding of a workflow document."""

    return json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def workflow_digest(document: Any) -> str:
    """``sha256:<hex>`` of :func:`canonical_text`, in the studio's own digest style."""

    return "sha256:" + hashlib.sha256(canonical_text(document).encode("utf-8")).hexdigest()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def domain_digest(domain: str, payload: Any) -> str:
    """Domain-separated SHA-256 in the same preimage shape the sibling packages use."""

    preimage = f"{_NAMESPACE}{_US}{domain}{_US}v1{_US}{canonical_json(payload)}"
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def require_nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{name} must be a non-empty string")
    return value.strip()


def optional_text(value: object, name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ContractViolation(f"{name} must be a string")
    return value.strip()


def bounded_text(value: object, name: str, limit: int, *, required: bool) -> str:
    text = require_nonempty(value, name) if required else optional_text(value, name)
    if len(text) > limit:
        raise ContractViolation(f"{name} exceeds {limit} characters")
    if any(ch in text for ch in ("\x00", "\r", "\n")) and name != "notes":
        raise ContractViolation(f"{name} must be a single line")
    return text
