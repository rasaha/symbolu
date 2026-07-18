"""Domain-separated, length-prefixed hashing (spec §9, §14, §17)."""

from __future__ import annotations

import hashlib
import struct

import pytest

from action_gate_ref import canon_profile as cp
from action_gate_ref import hashing, jcs


def test_domain_separation_same_bytes_differ():
    b = jcs.canonicalize({"x": "1"})
    seen = {hashing.domain_digest(d, b) for d in cp.DOMAINS}
    assert len(seen) == len(cp.DOMAINS)  # every domain yields a distinct digest


def test_length_prefix_framing_matches_spec():
    # Independently recompute digest = H(LP(tag)||LP(canon)||LP(schema)||LP(bytes))
    b = jcs.canonicalize({"a": "2", "b": "1"})
    tag = cp.domain_tag("ACTION").encode("ascii")

    def lp(x):
        return struct.pack(">Q", len(x)) + x

    framed = (lp(tag) + lp(cp.CANONICALIZATION_VERSION.encode("ascii"))
              + lp(cp.ENVELOPE_SCHEMA_VERSION.encode("ascii")) + lp(b))
    assert hashing.domain_digest("ACTION", b) == hashlib.sha256(framed).hexdigest()


def test_length_prefix_prevents_concatenation_ambiguity():
    # Moving the boundary between canon_version and canonical_bytes over the same
    # concatenation must change the digest — length prefixes make ("a","bc") and
    # ("ab","c") distinct even though "a"+"bc" == "ab"+"c".
    a = hashing.domain_digest("ACTION", b"bc", canonicalization_version="a", schema_version="")
    b = hashing.domain_digest("ACTION", b"c", canonicalization_version="ab", schema_version="")
    assert a != b


def test_default_is_sha256():
    assert cp.DEFAULT_HASH_ALGORITHM_ID == "sha-256"
    digest = hashing.domain_digest("ACTION", b"x")
    assert len(digest) == 64  # sha-256 hex


def test_sha512_256_alternative_supported_and_distinct():
    assert hashing.algorithm_supported("sha-512-256")
    b = jcs.canonicalize({"x": "1"})
    d256 = hashing.domain_digest("ACTION", b, algorithm_id="sha-256")
    d512 = hashing.domain_digest("ACTION", b, algorithm_id="sha-512-256")
    assert d256 != d512
    assert len(d512) == 64  # sha-512/256 also 32 bytes


def test_md5_sha1_not_exposed():
    assert "md5" not in cp.HASH_ALGORITHMS.values()
    assert "sha1" not in cp.HASH_ALGORITHMS.values()
    assert not hashing.algorithm_supported("md5")
    assert not hashing.algorithm_supported("sha-1")


def test_unsupported_algorithm_rejected():
    with pytest.raises(ValueError):
        hashing.domain_digest("ACTION", b"x", algorithm_id="crc32")


def test_chain_hash_order_sensitive():
    a = hashing.raw_chain_hash("00", "aa")
    b = hashing.raw_chain_hash("aa", "00")
    assert a != b


def test_chain_hash_domain_tagged():
    # AUDIT_CHAIN framing differs from a plain ACTION digest of the same inputs.
    assert hashing.raw_chain_hash("p", "r") != hashing.domain_digest("ACTION", b"pr")


def test_reproducible_across_calls():
    b = jcs.canonicalize({"z": "1", "a": "2"})
    assert hashing.domain_digest("APPROVAL", b) == hashing.domain_digest("APPROVAL", b)
