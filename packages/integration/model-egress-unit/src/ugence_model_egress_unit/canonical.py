"""Versioned, domain-separated canonicalization for the egress exchange.

One encoder produces the bytes behind one digest path. There is no second
serializer, no legacy digest and no encoding a caller can select — two functions
of the payload are not one function.

This mirrors the rule-set already ratified for ``ugence.benchmark-registry`` and
``ugence_policy_authority``. It is a *new* domain, not a change to an existing
one: no digest computed by any other package moves because this module exists.

Exact encoding rules (canonicalization ``v1``)
----------------------------------------------
* **Serialization**: UTF-8 JSON via ``json.dumps`` with ``sort_keys=True``,
  ``separators=(",", ":")`` and ``ensure_ascii=False``. The digest input is
  exactly those UTF-8 bytes.
* **Field inclusion is total.** Every field of the record is included, always,
  by declared name. Nothing is dropped when empty or ``None``. A conditional
  omission would let two different payloads share one byte sequence — which is
  the difference between "a digest over the request" and "a digest over most of
  the request".
* **``None`` is JSON ``null``**, so ``None`` and ``""`` are distinct digests.
* **Datetimes** must be timezone-aware, are normalized with
  ``astimezone(timezone.utc)`` and rendered ``%Y-%m-%dT%H:%M:%S.%fZ``, which
  preserves microseconds. A naive datetime is rejected: a value with no offset
  does not name an instant, and guessing UTC would silently invent one.
* **Strings must already be NFC.** Non-canonical input is rejected, never
  normalized — silent normalization would map two structurally different
  payloads onto one digest.
* **``bool`` before ``int``**, since ``bool`` subclasses ``int`` in Python.
* **``float`` is rejected outright**, which subsumes ``nan`` and the infinities.
  Nothing in this exchange is a real number; token counts are integers.
* **Unknown types fail closed.** There is no ``default=`` hook and no ``str()``
  fallback: an unrecognized type raises. A permissive fallback would make the
  digest a function of a Python object's ``repr`` — including its ``id()`` for
  any default one — which is not a function of the payload at all.

The encoder consults no clock, locale, timezone database, environment variable,
filesystem or network. ``astimezone`` is always called with an explicit
``timezone.utc`` target, never the zero-argument form that infers the local zone.

Why content is hashed separately
--------------------------------
The request digest covers a *content digest*, not the content itself. That is
what makes a purged row still verifiable: after the prompt and the response are
destroyed, the tombstone still carries both digests, and the request digest can
still be recomputed from the surviving fields and checked. A reader who holds a
candidate prompt can still prove whether it was the one — and a reader who does
not, learns nothing. Inlining the content would have made the request digest
unrecomputable the moment the content was purged, which would leave a tombstone
whose central claim could no longer be checked.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from typing import Any, Mapping

__all__ = [
    "MEU_CANONICALIZATION_VERSION",
    "EGRESS_REQUEST_DIGEST_DOMAIN",
    "EGRESS_RESULT_DIGEST_DOMAIN",
    "EXCHANGE_CONTENT_DIGEST_DOMAIN",
    "CanonicalizationError",
    "canonical_bytes",
    "canonical_digest",
    "content_digest",
]

#: The rule-set version bound into every digest. Changing any rule in this
#: module's docstring requires a new version string.
MEU_CANONICALIZATION_VERSION = "ugence.model-egress-unit/canonicalization/v1"

#: Domain-separation tags. Three domains, because three different artifact
#: classes are hashed and a digest from one must never validate as another.
EGRESS_REQUEST_DIGEST_DOMAIN = "ugence.model-egress-unit/egress-request/v1"
EGRESS_RESULT_DIGEST_DOMAIN = "ugence.model-egress-unit/egress-result/v1"
EXCHANGE_CONTENT_DIGEST_DOMAIN = "ugence.model-egress-unit/exchange-content/v1"

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class CanonicalizationError(TypeError):
    """A payload cannot be canonicalized, so no digest exists for it."""


def _require_nfc(value: str, path: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise CanonicalizationError(
            f"{path}: string is not Unicode NFC. It is rejected rather than "
            f"normalized, because normalizing here would give two structurally "
            f"different payloads one digest ({MEU_CANONICALIZATION_VERSION})"
        )
    return value


def _to_canonical_obj(value: Any, path: str) -> Any:
    # bool first: it subclasses int, and a JSON 0/1 is not a JSON false/true.
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return _require_nfc(value, path)
    if isinstance(value, float):
        raise CanonicalizationError(
            f"{path}: float is rejected. Non-finite values have no canonical JSON "
            f"form at all, and every exact quantity in this exchange is an integer"
        )
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise CanonicalizationError(
                f"{path}: naive datetime is rejected. A value with no offset does "
                f"not name an instant, and assuming UTC would invent one"
            )
        return value.astimezone(timezone.utc).strftime(_TIMESTAMP_FORMAT)
    if isinstance(value, Mapping):
        out = {}
        for key in value:
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"{path}: mapping key {key!r} is not a string; JSON object keys "
                    f"are strings and coercing one would not be reversible"
                )
            out[_require_nfc(key, f"{path}.{key}")] = _to_canonical_obj(
                value[key], f"{path}.{key}")
        return out
    if isinstance(value, (list, tuple)):
        return [_to_canonical_obj(item, f"{path}[{i}]") for i, item in enumerate(value)]
    raise CanonicalizationError(
        f"{path}: {type(value).__name__} has no canonical form. There is no "
        f"fallback encoder by design — one would make the digest a function of a "
        f"Python object's repr rather than of the payload"
    )


def canonical_bytes(domain: str, type_name: str, body: Mapping[str, Any]) -> bytes:
    """The exact UTF-8 bytes :func:`canonical_digest` is computed over.

    The framing binds the rule-set version, the domain and the record type into
    the digest input, so the same body under a different domain or a future
    rule-set never collides with this one.
    """

    framed = {
        "canonicalization": MEU_CANONICALIZATION_VERSION,
        "domain": _require_nfc(domain, "$.domain"),
        "type": _require_nfc(type_name, "$.type"),
        "body": _to_canonical_obj(dict(body), "$"),
    }
    return json.dumps(
        framed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_digest(domain: str, type_name: str, body: Mapping[str, Any]) -> str:
    """The bare lowercase 64-char SHA-256 hex digest of :func:`canonical_bytes`.

    An identity fingerprint and nothing else. It is not a signature, not an
    authorization and not evidence that the exchange was permitted: computing or
    matching it establishes only that two payloads are the same payload.
    """

    return hashlib.sha256(canonical_bytes(domain, type_name, body)).hexdigest()


def content_digest(content: str) -> str:
    """Digest of one exchange payload — a prompt or a response body.

    Domain-separated from the record digests so a content digest can never be
    presented as a request digest. The content is required to be NFC for the same
    reason every other string is: one payload, one spelling, one digest.

    This is the value that survives a purge. It is what lets a tombstone still
    answer "was it this?" without holding the content that would answer "what was
    it?".
    """

    if not isinstance(content, str):
        raise CanonicalizationError(
            f"content must be str, not {type(content).__name__}")
    framed = json.dumps(
        {
            "canonicalization": MEU_CANONICALIZATION_VERSION,
            "domain": EXCHANGE_CONTENT_DIGEST_DOMAIN,
            "content": _require_nfc(content, "$.content"),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(framed).hexdigest()
