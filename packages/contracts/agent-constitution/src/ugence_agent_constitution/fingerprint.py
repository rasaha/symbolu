"""SHA-256 content fingerprinting over canonical JSON.

A fingerprint is a *logical* digest: it commits to the canonical JSON encoding of
an artifact's material content, not to the bytes of any particular file, so
re-serializing, re-ordering keys, or round-tripping through JSON never perturbs
it. A material edit — any change to a value that is inside the digest scope —
always does.

Two scoping rules make that property hold:

* :data:`DIGEST_ALGORITHM` is pinned. The prefix is carried in the fingerprint
  string itself (``sha256:<hex>``) so a future algorithm change is visible in
  every stored value rather than silently changing what a bare hex string means.
* A digest-bearing artifact excludes its own digest field (and any field it
  declares in ``DIGEST_EXCLUDED_FIELDS``) from its own digest scope. Without that
  the digest would have to commit to itself, which has no fixed point.

This module reads no clock, no environment, no filesystem and no randomness.
Fingerprinting is a pure function of the value passed in. It is *not* a
signature: AC-0 ships no signing, and a fingerprint attests to content identity
only, never to who produced it or whether they were entitled to.
"""

from __future__ import annotations

import hashlib
from typing import Any, ClassVar, Mapping, Protocol, Sequence, runtime_checkable

from .serialization.canonical_json import dumps, to_canonical_obj

#: The one hash this build computes. Carried as a prefix on every fingerprint.
DIGEST_ALGORITHM = "sha256"
#: ``sha256:`` — the prefix every fingerprint string produced here starts with.
DIGEST_PREFIX = DIGEST_ALGORITHM + ":"
#: Length of the hex body of a ``sha256`` digest.
DIGEST_HEX_LENGTH = 64


@runtime_checkable
class DigestScoped(Protocol):
    """An artifact that knows which of its own fields are outside its digest."""

    DIGEST_EXCLUDED_FIELDS: ClassVar[frozenset]

    def model_dump(self, *args: Any, **kwargs: Any) -> dict: ...


def fingerprint(value: Any) -> str:
    """Return ``sha256:<hex>`` over the canonical JSON encoding of ``value``.

    ``value`` may be any structure :mod:`.serialization.canonical_json` accepts:
    pydantic models, enums, mappings, sequences, sets, and JSON scalars.
    """
    encoded = dumps(value).encode("utf-8")
    return DIGEST_PREFIX + hashlib.sha256(encoded).hexdigest()


def fingerprint_text(text: str) -> str:
    """Return ``sha256:<hex>`` over the UTF-8 bytes of an already-serialized string.

    Use this only when the caller holds canonical JSON it produced itself. For a
    live object, prefer :func:`fingerprint`, which canonicalizes first.
    """
    return DIGEST_PREFIX + hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_scope(artifact: Any) -> dict:
    """Return the canonical, JSON-native content an artifact's digest commits to.

    Fields named in the artifact's ``DIGEST_EXCLUDED_FIELDS`` are removed at the
    top level only. Nested content is always in scope: a change anywhere inside a
    capability requirement, an issuer identity or a predecessor reference is a
    material change.
    """
    excluded = frozenset(getattr(artifact, "DIGEST_EXCLUDED_FIELDS", frozenset()))
    if isinstance(artifact, Mapping):
        payload = dict(artifact)
    else:
        payload = artifact.model_dump(mode="python")
    scoped = {k: v for k, v in payload.items() if k not in excluded}
    return to_canonical_obj(scoped)


def compute_content_digest(artifact: Any) -> str:
    """Return the fingerprint of an artifact's digest scope.

    This is what a digest-bearing artifact's declared ``content_digest`` must
    equal. Semantic validation recomputes it and refuses any artifact whose
    declared digest disagrees — a declared digest is a claim, never a warrant.
    """
    return fingerprint(digest_scope(artifact))


def is_well_formed_digest(value: Any) -> bool:
    """True when ``value`` is syntactically a ``sha256:<64 hex>`` fingerprint.

    Syntax only. A well-formed digest may still be the wrong digest; that is
    decided by recomputation, not by shape.
    """
    if not isinstance(value, str) or not value.startswith(DIGEST_PREFIX):
        return False
    body = value[len(DIGEST_PREFIX):]
    if len(body) != DIGEST_HEX_LENGTH:
        return False
    return all(c in "0123456789abcdef" for c in body)


def digests_agree(declared: str, artifact: Any) -> bool:
    """True when ``declared`` is exactly the recomputed digest of ``artifact``."""
    return is_well_formed_digest(declared) and declared == compute_content_digest(artifact)


def fingerprint_sequence(values: Sequence[Any]) -> str:
    """Fingerprint an ordered sequence. Order is material and is preserved."""
    return fingerprint(list(values))


__all__ = [
    "DIGEST_ALGORITHM",
    "DIGEST_PREFIX",
    "DIGEST_HEX_LENGTH",
    "DigestScoped",
    "fingerprint",
    "fingerprint_text",
    "fingerprint_sequence",
    "digest_scope",
    "compute_content_digest",
    "is_well_formed_digest",
    "digests_agree",
]
