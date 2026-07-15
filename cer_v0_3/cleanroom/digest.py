"""Clean-room domain-separated, length-prefixed action identity.

Independent reimplementation from the published specification
(ACTION_CANONICALIZATION_AND_HASHING_SPEC.md §9, §17):

    digest = SHA-256( LP(domain_tag) || LP(canon_version) || LP(schema_version) || LP(canon) )
    LP(x)  = uint64_be(len(x)) || x
    domain_tag(ACTION) = "SYMBOLU/ACTIONGATE/ACTION/v1"

For the CER V0.2 identity profile (v2, provenance-excluded) the envelope schema
version in the frame is "2.0.0"; canonicalization version is "1". SHA-256 comes
from hashlib (never hand-rolled). Standard library only.
"""
from __future__ import annotations

import hashlib
import struct

_DOMAIN_PREFIX = "SYMBOLU/ACTIONGATE"
_DOMAIN_VERSION = "v1"
CANONICALIZATION_VERSION = "1"
# CER V0.2 identity profile v2 (provenance excluded) domain-separates via this tag.
ENVELOPE_SCHEMA_VERSION_V2 = "2.0.0"
ENVELOPE_SCHEMA_VERSION_V1 = "1.0.0"


def _domain_tag(domain: str) -> bytes:
    return f"{_DOMAIN_PREFIX}/{domain}/{_DOMAIN_VERSION}".encode("ascii")


def _lp(b: bytes) -> bytes:
    return struct.pack(">Q", len(b)) + b


def action_digest(canonical: bytes, *, schema_version: str = ENVELOPE_SCHEMA_VERSION_V2,
                  canonicalization_version: str = CANONICALIZATION_VERSION) -> str:
    """Hex action identity for ``canonical`` bytes under the ACTION domain."""
    framed = (
        _lp(_domain_tag("ACTION"))
        + _lp(canonicalization_version.encode("ascii"))
        + _lp(schema_version.encode("ascii"))
        + _lp(canonical)
    )
    return hashlib.sha256(framed).hexdigest()
