"""Domain-separated, length-prefixed hashing (spec §9, §17).

    digest = H( LP(domain_tag) || LP(canon_version) || LP(schema_version) || LP(canonical_bytes) )
    LP(x)  = uint64_be(len(x)) || x

Cryptographic primitives come from hashlib (OpenSSL) — never hand-rolled.
SHA-256 default; SHA-512/256 where the library supports it. MD5/SHA-1 and
non-cryptographic hashes are not exposed.
"""

from __future__ import annotations

import hashlib
import struct

from . import canon_profile as cp
from .canon_profile import HASH_ALGORITHMS, domain_tag


def _new(algorithm_id: str):
    if algorithm_id not in HASH_ALGORITHMS:
        raise ValueError(f"unsupported hash_algorithm_id {algorithm_id!r}")
    name = HASH_ALGORITHMS[algorithm_id]
    if name not in hashlib.algorithms_available:
        raise ValueError(f"hash {name!r} unavailable in this runtime")
    return hashlib.new(name)


def algorithm_supported(algorithm_id: str) -> bool:
    return (
        algorithm_id in HASH_ALGORITHMS
        and HASH_ALGORITHMS[algorithm_id] in hashlib.algorithms_available
    )


def _lp(b: bytes) -> bytes:
    return struct.pack(">Q", len(b)) + b


def domain_digest(
    domain: str,
    canonical_bytes: bytes,
    *,
    algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
    schema_version: str = cp.ENVELOPE_SCHEMA_VERSION,
    canonicalization_version: str = cp.CANONICALIZATION_VERSION,
) -> str:
    """Return the hex digest for ``canonical_bytes`` under ``domain``."""
    tag = domain_tag(domain).encode("ascii")
    framed = (
        _lp(tag)
        + _lp(canonicalization_version.encode("ascii"))
        + _lp(schema_version.encode("ascii"))
        + _lp(canonical_bytes)
    )
    h = _new(algorithm_id)
    h.update(framed)
    return h.hexdigest()


def raw_chain_hash(
    prev_chain_hex: str,
    record_hash_hex: str,
    *,
    algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
) -> str:
    """chain_hash_n = H( LP(AUDIT_CHAIN_tag) || LP(prev) || LP(record_hash) )  (spec §14)."""
    tag = domain_tag("AUDIT_CHAIN").encode("ascii")
    framed = _lp(tag) + _lp(prev_chain_hex.encode("ascii")) + _lp(record_hash_hex.encode("ascii"))
    h = _new(algorithm_id)
    h.update(framed)
    return h.hexdigest()
