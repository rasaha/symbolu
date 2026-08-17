"""Versioned, domain-separated canonicalization for trusted-evidence contracts.

**One** encoder produces the bytes behind **one** digest path. There is no
second serializer, no legacy digest, no dual-acceptance fallback, and no
alternate encoding a caller can select — ADR §22.2 requires canonical bytes to
be "a pure function of the payload", and two functions of the payload are not
one function.

Exact encoding rules (canonicalization ``v1``)
----------------------------------------------
* **Serialization**: UTF-8 JSON via ``json.dumps`` with ``sort_keys=True``,
  ``separators=(",", ":")`` (no insignificant whitespace) and
  ``ensure_ascii=False``. The digest input is exactly those UTF-8 bytes.
* **Key ordering**: object keys sorted lexicographically by code point.
* **Field inclusion is total and deterministic**: every dataclass field is
  included, always, by declared name. Nothing is dropped when empty, and no
  field is conditionally omitted — a conditional omission would let two
  different payloads share one byte sequence.
* **``None`` is represented explicitly** as JSON ``null``. ``None`` and ``""``
  are therefore distinct byte sequences and distinct digests.
* **Datetimes** must be timezone-aware; they are normalized to UTC with
  ``astimezone(timezone.utc)`` — pure arithmetic against the value's own
  offset — and rendered ``%Y-%m-%dT%H:%M:%S.%fZ``, which **preserves
  microseconds**. Two spellings of one instant therefore render identically.
  **A naive datetime is rejected**, here and at every construction boundary
  (ADR §22.4): a value with no offset does not name an instant, and guessing UTC
  would silently invent one.
* **Strings** must already be Unicode **NFC**; non-canonical input is rejected,
  never silently normalized (see the posture note below).
* **``bool`` before ``int``** — ``bool`` subclasses ``int`` in Python, so it is
  dispatched first and serialized as a JSON boolean, never as ``0``/``1``.
* **``float`` is rejected outright.** This subsumes the rejection of non-finite
  values (``nan``, ``inf``, ``-inf``), which have no canonical JSON form at all;
  exact values in these contracts are integers or strings. It matches the merged
  ``ugence_policy_authority`` canonicalization ``v1`` posture.
* **Ordered collections** (``list``/``tuple``) preserve order — order is
  semantic wherever these contracts carry a sequence (a chain of custody is
  ordered), and a caller-supplied set-like sequence is normalized into its
  ratified order *before* it reaches the encoder, not by the encoder.
* **Mappings and ``bytes`` are rejected.** No TEV-1 contract carries either.
  Rejecting mappings structurally enforces the ADR's rule that evidence
  coordinates are never collapsed into a free-form metadata dictionary.
* **Unknown types fail closed** (ADR §22.8). There is **no** ``default=`` hook,
  no ``str()`` fallback, and no ``repr()`` anywhere in this module: an
  unrecognized type raises. A permissive fallback would make the digest a
  function of a Python object's textual rendering — including its ``id()`` for
  any default ``__repr__`` — which is neither deterministic across processes nor
  a function of the payload.

Determinism inputs
------------------
The encoder consults **no** wall clock, locale, timezone database, environment
variable, filesystem or network. ``astimezone`` is always called with an
explicit ``timezone.utc`` target, never the zero-argument form that would infer
the local zone. Package tests assert this structurally over the whole source
tree, not merely for one code path.

Unicode posture — reject, do not normalize
------------------------------------------
Silent NFC normalization would map two *structurally different* artifacts onto
one digest: an NFD-spelled and an NFC-spelled coordinate would become
indistinguishable, so a digest over one would attest a value nobody wrote.
Rejecting keeps the digest a faithful function of the exact bytes the author
committed to. The posture is bound to the canonicalization version, so changing
it requires a new version. This is the merged ``ugence_policy_authority`` §12
posture (a), adopted rather than re-litigated.

Domain separation and versioning
--------------------------------
ADR §22.1 requires every digest to bind a canonicalization version and a
domain-separation tag, and **DD-9 explicitly leaves the exact byte constants to
TEV-1/TEV-2**. This module resolves them for the *evidence-identity* domain
only. The receipt domain and the benchmark domain are deliberately **not**
minted here: their artifacts do not exist yet (TEV-2, BR-1), and a tag without
an artifact is an unused constant that a later milestone would have to either
honour or break.

Every canonical byte sequence is framed as::

    {"body": {...}, "canonicalization": <version>, "domain": <tag>, "type": <name>}

so the same body under two contract types can never produce the same bytes.

Independent verification
------------------------
:func:`canonical_bytes` and :func:`canonical_digest` are public and pure. A
third party holding a contract and this module can recompute any digest without
package internals; the package tests pin representative byte strings and
reconstruct one digest from hand-written literal bytes and ``hashlib`` alone.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .errors import TrustedEvidenceCanonicalizationError

__all__ = [
    "TRUSTED_EVIDENCE_CANONICALIZATION_VERSION",
    "EVIDENCE_IDENTITY_DIGEST_DOMAIN",
    "canonical_bytes",
    "canonical_digest",
]

#: The canonicalization rule-set version bound into every digest (ADR §22.1).
#: Changing any rule in this module's docstring requires a new version string.
TRUSTED_EVIDENCE_CANONICALIZATION_VERSION = (
    "ugence.trusted-evidence-authority/canonicalization/v1"
)

#: The domain-separation tag bound into every evidence-identity digest.
#:
#: Distinct from any receipt or benchmark domain, neither of which exists yet
#: (TEV-2 / BR-1). ADR §26.6: a signature or digest valid in one domain must not
#: be reusable in another.
EVIDENCE_IDENTITY_DIGEST_DOMAIN = (
    "ugence.trusted-evidence-authority/evidence-identity/v1"
)

_TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _require_nfc(value: str, path: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise TrustedEvidenceCanonicalizationError(
            f"{path}: string is not Unicode NFC-normalized; trusted-evidence "
            "contracts reject non-canonical input rather than silently "
            f"normalizing it ({TRUSTED_EVIDENCE_CANONICALIZATION_VERSION})"
        )
    return value


def _format_datetime(value: datetime, path: str) -> str:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise TrustedEvidenceCanonicalizationError(
            f"{path}: a naive datetime is not a well-defined instant and must "
            "not enter a canonical byte sequence, a validity interval, or a digest"
        )
    return value.astimezone(timezone.utc).strftime(_TIMESTAMP_FMT)


def _to_canonical_obj(value: Any, path: str) -> Any:
    """Recursively convert ``value`` into a JSON-canonical structure.

    The result contains only ``dict`` (string keys), ``list``, ``str``, ``int``,
    ``bool`` and ``None``. Every rejection carries the offending path.
    """

    if value is None:
        return None
    # ``bool`` before ``int`` — ``bool`` subclasses ``int``.
    if isinstance(value, bool):
        return value
    # ``float`` before any numeric handling: rejected outright, which covers
    # nan/inf/-inf as well as every finite float.
    if isinstance(value, float):
        raise TrustedEvidenceCanonicalizationError(
            f"{path}: float is not canonicalizable — a governed coordinate must "
            "be an exact integer or a string (this also rejects nan/inf/-inf, "
            "which have no canonical JSON form)"
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return _require_nfc(value, path)
    if isinstance(value, Enum):
        return _to_canonical_obj(value.value, path)
    if isinstance(value, datetime):
        return _format_datetime(value, path)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            _require_nfc(f.name, f"{path}.{f.name}"): _to_canonical_obj(
                getattr(value, f.name), f"{path}.{f.name}"
            )
            for f in fields(value)
        }
    if isinstance(value, (list, tuple)):
        return [_to_canonical_obj(v, f"{path}[{i}]") for i, v in enumerate(value)]
    raise TrustedEvidenceCanonicalizationError(
        f"{path}: type {type(value).__name__!r} is not canonicalizable; the "
        "encoder has no permissive fallback and never renders an unknown object"
    )


def canonical_bytes(contract: Any) -> bytes:
    """Return the exact UTF-8 bytes :func:`canonical_digest` is computed over.

    ``contract`` must be a frozen dataclass instance from this package. The
    returned bytes are the framed, domain-separated, version-labelled encoding
    described in the module docstring.

    Two contracts that compare equal always produce byte-identical output,
    including when their instants were written with different UTC offsets::

        if a == b:
            assert canonical_bytes(a) == canonical_bytes(b)

    Two contracts differing in **any** load-bearing coordinate always produce
    different output.
    """

    if not is_dataclass(contract) or isinstance(contract, type):
        raise TrustedEvidenceCanonicalizationError(
            "canonical_bytes expects a trusted-evidence contract instance "
            f"(got {type(contract).__name__})"
        )
    framed = {
        "canonicalization": TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
        "domain": EVIDENCE_IDENTITY_DIGEST_DOMAIN,
        "type": type(contract).__name__,
        "body": _to_canonical_obj(contract, "$"),
    }
    return json.dumps(
        framed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_digest(contract: Any) -> str:
    """Return the bare lowercase 64-char sha-256 hex digest of the canonical bytes.

    The digest is computed **solely** from :func:`canonical_bytes` — no other
    input, no salt, no clock, no side channel. It is an identity fingerprint. It
    is **not** evidence, not a signature, not an authenticity proof, and not an
    admission decision: ADR §8.1.3 — "possession is not validity" — and §10.5
    together mean that computing or matching a digest establishes nothing about
    where the content came from.
    """

    return hashlib.sha256(canonical_bytes(contract)).hexdigest()
