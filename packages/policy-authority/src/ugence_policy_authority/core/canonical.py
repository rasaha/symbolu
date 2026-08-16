"""Versioned, domain-separated canonicalization for the Ugence Policy Authority.

One encoder produces the bytes behind every digest and every signed payload, so
a digest depends only on canonical meaning, never on transport encoding.

Exact encoding rules (canonicalization ``v1``)
----------------------------------------------
* **Serialization**: UTF-8 JSON via ``json.dumps`` with ``sort_keys=True``,
  ``separators=(",", ":")`` (no insignificant whitespace) and
  ``ensure_ascii=False``. The hash input is exactly those UTF-8 bytes.
* **Key ordering**: object keys sorted lexicographically by code point.
* **Hash**: ``sha-256``, rendered as bare lowercase 64-char hex (no
  ``sha256:`` prefix) so it is directly comparable with the digest shape the
  policy contracts validate.
* **Enums** serialize by ``.value``.
* **Datetimes** must be timezone-aware; they are normalized to UTC and rendered
  ``%Y-%m-%dT%H:%M:%S.%fZ``. Two representations of the same instant therefore
  render byte-identically. **A naive datetime is rejected**, here and at every
  boundary — a datetime without an offset is not a well-defined instant and
  must never enter a signed payload, an effective period, or a digest.
* **Strings** must already be Unicode **NFC**. See the posture note below.
* **``float`` is rejected outright**; exact values are integers or strings.
* **``bytes``** are base64url-encoded without padding.
* **Ordered collections** (``list``/``tuple``) preserve order — order is
  semantic in every governed policy collection.

Unicode posture — ADR §12.1 option (a), versioned with ``v1``
--------------------------------------------------------------
This implementation **requires canonical NFC strings and rejects non-canonical
input at the authority boundary**, recursively, including nested fields and
mapping keys. It deliberately does **not** silently normalize.

Silent normalization would map two *structurally different* artifacts onto one
digest: an NFD-spelled and an NFC-spelled policy would become
indistinguishable, so a signature over one would verify a body nobody signed.
Rejecting keeps the digest a faithful function of the exact bytes an author
committed to. The posture is bound to the canonicalization version, so changing
it requires a new version.

Independent verification
------------------------
:func:`canonical_bytes`, :func:`sha256_hex` and the adapter-facing
:func:`framed_body_digest` are public. A third party holding the artifact and
the public adapter projection can recompute and check any digest without
authority internals.
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

from .errors import PolicyCanonicalizationError
from .statuses import CANONICALIZATION_VERSION

__all__ = [
    "CANONICALIZATION_VERSION",
    "POLICY_BODY_DIGEST_DOMAIN",
    "to_canonical_obj",
    "canonical_dumps",
    "canonical_bytes",
    "sha256_hex",
    "framed_body_bytes",
    "framed_body_digest",
    "require_nfc",
    "require_tzaware",
]

#: Domain tag bound into every policy-body digest.
POLICY_BODY_DIGEST_DOMAIN = "ugence.policy-authority/policy-body/v1"

_TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def require_nfc(value: str, *, path: str = "<string>") -> str:
    """Return ``value`` if it is already NFC; otherwise reject it.

    Posture (a): the authority never silently normalizes. See the module
    docstring for why folding NFD onto NFC would be unsafe.
    """

    if unicodedata.normalize("NFC", value) != value:
        raise PolicyCanonicalizationError(
            f"{path}: string is not Unicode NFC-normalized; the authority rejects "
            "non-canonical input rather than silently normalizing it "
            f"(canonicalization {CANONICALIZATION_VERSION})"
        )
    return value


def require_tzaware(value: datetime, *, path: str = "<datetime>") -> datetime:
    """Return ``value`` if it carries a UTC offset; otherwise reject it."""

    if not isinstance(value, datetime):
        raise PolicyCanonicalizationError(f"{path}: expected a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise PolicyCanonicalizationError(
            f"{path}: naive datetime is not a well-defined instant and must not "
            "enter a digest, an effective period, or a signed payload"
        )
    return value


def _format_datetime(value: datetime, path: str) -> str:
    return require_tzaware(value, path=path).astimezone(timezone.utc).strftime(_TIMESTAMP_FMT)


def to_canonical_obj(value: Any, *, path: str = "$") -> Any:
    """Recursively convert ``value`` into a JSON-canonical structure.

    The result contains only ``dict`` (string keys), ``list``, ``str``, ``int``,
    ``bool`` and ``None``. Every rejection carries the offending path.
    """

    # ``bool`` before ``int`` (bool subclasses int); ``float`` rejected before
    # any numeric handling.
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise PolicyCanonicalizationError(
            f"{path}: float is not canonicalizable — a governed value must be an "
            "exact integer or a string"
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return require_nfc(value, path=path)
    if isinstance(value, bytes):
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    if isinstance(value, Enum):
        return to_canonical_obj(value.value, path=path)
    if isinstance(value, datetime):
        return _format_datetime(value, path)
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        # Field order is irrelevant — keys are sorted at encode time.
        return {
            require_nfc(f.name, path=f"{path}.{f.name}"): to_canonical_obj(
                getattr(value, f.name), path=f"{path}.{f.name}"
            )
            for f in fields(value)
        }
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise PolicyCanonicalizationError(
                    f"{path}: mapping keys must be strings (got {type(key).__name__})"
                )
            canonical_key = require_nfc(key, path=f"{path}.{key}")
            out[canonical_key] = to_canonical_obj(item, path=f"{path}.{canonical_key}")
        return out
    if isinstance(value, (list, tuple)):
        return [to_canonical_obj(v, path=f"{path}[{i}]") for i, v in enumerate(value)]
    raise PolicyCanonicalizationError(
        f"{path}: type {type(value).__name__!r} is not canonicalizable"
    )


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
    """Return the bare lowercase 64-char sha-256 hex digest of ``data``."""

    return hashlib.sha256(data).hexdigest()


def framed_body_bytes(
    *, adapter_id: str, policy_type: str, projection: Mapping[str, Any]
) -> bytes:
    """Frame an adapter's canonical projection and return its canonical bytes.

    The **adapter** supplies the family-specific ``projection`` — the core never
    interprets a family artifact. The **core** owns the frame, so every family
    is bound to the same canonicalization version, domain tag, adapter identity
    and policy type, and two families can never collide on identical bytes.
    """

    return canonical_bytes(
        {
            "canonicalization": CANONICALIZATION_VERSION,
            "domain": POLICY_BODY_DIGEST_DOMAIN,
            "adapter": adapter_id,
            "policy_type": policy_type,
            "body": projection,
        }
    )


def framed_body_digest(
    *, adapter_id: str, policy_type: str, projection: Mapping[str, Any]
) -> str:
    """Return the 64-hex digest of a framed adapter projection."""

    return sha256_hex(
        framed_body_bytes(adapter_id=adapter_id, policy_type=policy_type, projection=projection)
    )
