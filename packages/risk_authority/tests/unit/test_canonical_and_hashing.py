"""Canonical serialization + digest determinism (spec §8, §27; CI gate)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from risk_authority.crypto.canonical import canonical_bytes, canonical_dumps
from risk_authority.crypto.hashing import digest
from risk_authority.domain import Scope


def test_key_ordering_is_deterministic():
    a = {"b": 1, "a": 2, "c": 3}
    b = {"c": 3, "a": 2, "b": 1}
    assert canonical_bytes(a) == canonical_bytes(b)


def test_set_ordering_is_normalized():
    assert canonical_bytes({"x": {3, 1, 2}}) == canonical_bytes({"x": [1, 2, 3]})


def test_list_ordering_is_preserved():
    assert canonical_bytes([1, 2, 3]) != canonical_bytes([3, 2, 1])


def test_none_is_explicit_not_dropped():
    assert canonical_dumps({"a": None}) == '{"a":null}'


def test_float_is_rejected():
    with pytest.raises(TypeError):
        canonical_bytes({"amount": 1.5})


def test_datetime_normalized_to_utc():
    naive = datetime(2026, 8, 10, 12, 0, 0)
    aware = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
    assert canonical_bytes(naive) == canonical_bytes(aware)


def test_unicode_is_nfc_normalized():
    # U+00E9  vs  e + U+0301 combining acute — same NFC form.
    composed = "café"
    decomposed = "café"
    assert canonical_bytes(composed) == canonical_bytes(decomposed)


def test_scope_digest_is_order_independent_after_normalization():
    a = Scope(tools_allow=("b", "a"), data_allow=("z", "y")).normalized()
    b = Scope(tools_allow=("a", "b"), data_allow=("y", "z")).normalized()
    assert digest(a) == digest(b)


def test_digest_has_sha256_prefix():
    assert digest({"a": 1}).startswith("sha256:")
