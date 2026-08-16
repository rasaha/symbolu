"""Canonical serialization and the UVI **policy-body digest** definition.

One serialization function is used for every digest and every signed payload in
this package, so a digest depends only on canonical meaning, never on transport
encoding. The rules mirror the discipline already established by the merged
contracts (sorted keys, tight separators, ``sha-256``, enums by value, bare
lowercase 64-hex output — the exact shape ``PolicyReference.content_digest``
validates) and the stricter normalization of the repository's existing
authority canonicalizer (UTC-normalized RFC 3339 timestamps, NFC strings,
``float`` rejected outright).

The policy-body digest
----------------------
The merged UVI policy contracts declare ``content_digest`` to be "the
authority-attested digest of the policy *content*" and deliberately leave the
computation to the Policy Authority: nothing in ``uvi-policy-contracts``
computes it, and its own ``canonical_digest()`` helper is a generic
whole-object fingerprint, never defined as the content digest. This module
supplies the missing definition. It does **not** introduce a competing one.

The definition is a single-pass exclusion, not a fixed point and not a
sentinel:

    policy_body_digest(P) = sha256( canonical_json( {
        "domain":      "ugence.uvi.policy-authority/policy-body/v1",
        "policy_type": <exact runtime dataclass name>,
        "body":        canonical(P) with the single path
                       ``metadata.content_digest`` REMOVED from the mapping,
    } ) )

Consequences, each of which is proven by a test:

* every governed content field **and** every metadata identity field
  (``policy_id``, ``policy_family``, ``version``, ``scope``, ``tenant_id``,
  ``lifecycle_state``, the effective period, the issuer/approval/supersession
  references and ``created_at``) is bound;
* the one self-referential field is removed rather than blanked, so no
  placeholder value participates and no iteration to a fixed point is needed —
  the digest is computable in one pass and setting ``content_digest`` to the
  result cannot change the result;
* signature bytes never appear in a policy artifact, so the body digest is
  structurally incapable of depending on a signature;
* an equal normalized policy always yields equal bytes; a list and the tuple it
  normalizes to are indistinguishable (the contracts normalize on construction);
* the exact runtime dataclass name is bound, so two different families can
  never produce identical body bytes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import unicodedata
from dataclasses import fields, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Mapping

from .errors import PolicyAuthorityError

__all__ = [
    "POLICY_BODY_DIGEST_DOMAIN",
    "to_canonical_obj",
    "canonical_dumps",
    "canonical_bytes",
    "sha256_hex",
    "canonical_policy_body_bytes",
    "canonical_policy_body_digest",
]

#: Domain tag bound into every policy-body digest.
POLICY_BODY_DIGEST_DOMAIN = "ugence.uvi.policy-authority/policy-body/v1"

_TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _normalize_str(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _format_datetime(value: datetime) -> str:
    # Normalized to UTC before formatting, so two representations of the same
    # instant render byte-identically regardless of the source ``tzinfo``.
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return aware.strftime(_TIMESTAMP_FMT)


def to_canonical_obj(value: Any) -> Any:
    """Recursively convert ``value`` into a JSON-canonical structure.

    The result contains only ``dict`` (string keys), ``list``, ``str``, ``int``,
    ``bool`` and ``None`` — the primitives ``json.dumps`` renders
    deterministically. ``float`` is rejected: no UVI policy field carries one,
    and admitting binary floats would make a digest platform-dependent.
    """

    # ``bool`` before ``int`` (bool subclasses int); ``float`` rejected before
    # any numeric handling.
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise PolicyAuthorityError(
            "float is not canonicalizable — a governed value must be an exact "
            "integer or a string"
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return _normalize_str(value)
    if isinstance(value, bytes):
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    if isinstance(value, Enum):
        return to_canonical_obj(value.value)
    if isinstance(value, datetime):
        return _format_datetime(value)
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            _normalize_str(f.name): to_canonical_obj(getattr(value, f.name))
            for f in fields(value)
        }
    if isinstance(value, Mapping):
        return {_normalize_str(str(k)): to_canonical_obj(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        # Ordered collections preserve order (order is semantic in every UVI
        # policy collection). A caller-owned list and the tuple the contracts
        # normalize it into therefore canonicalize identically.
        return [to_canonical_obj(v) for v in value]
    raise PolicyAuthorityError(f"type {type(value)!r} is not canonicalizable")


def canonical_dumps(value: Any) -> str:
    """Return the canonical compact JSON string for ``value``."""

    return json.dumps(
        to_canonical_obj(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_bytes(value: Any) -> bytes:
    """Return the canonical UTF-8 byte stream for ``value``."""

    return canonical_dumps(value).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return the bare lowercase 64-char sha-256 hex digest of ``data``.

    Bare hex (no ``sha256:`` prefix) so the output is directly comparable with
    ``PolicyReference.content_digest``, which the contracts validate against
    ``^[0-9a-f]{64}$``.
    """

    return hashlib.sha256(data).hexdigest()


def canonical_policy_body_bytes(policy: Any) -> bytes:
    """Return the canonical body bytes of a UVI policy artifact.

    See the module docstring for the exact definition. Raises if ``policy`` is
    not a dataclass carrying a ``metadata`` mapping with a ``content_digest``
    field — the authority never digests a shape it does not recognize.
    """

    if not is_dataclass(policy) or isinstance(policy, type):
        raise PolicyAuthorityError("policy body digest requires a policy dataclass instance")

    body = to_canonical_obj(policy)
    metadata = body.get("metadata") if isinstance(body, dict) else None
    if not isinstance(metadata, dict) or "content_digest" not in metadata:
        raise PolicyAuthorityError(
            "policy body digest requires a PolicyArtifactMetadata envelope carrying "
            "content_digest"
        )

    # Remove — not blank — the single self-referential path. Nothing stands in
    # its place, so no sentinel value participates in the digest.
    body = dict(body)
    body["metadata"] = {k: v for k, v in metadata.items() if k != "content_digest"}

    return canonical_bytes(
        {
            "domain": POLICY_BODY_DIGEST_DOMAIN,
            "policy_type": type(policy).__name__,
            "body": body,
        }
    )


def canonical_policy_body_digest(policy: Any) -> str:
    """Return the 64-hex canonical body digest of a UVI policy artifact."""

    return sha256_hex(canonical_policy_body_bytes(policy))
