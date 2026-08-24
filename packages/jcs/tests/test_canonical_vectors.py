"""Byte-for-byte canonicalization vectors.

These literals were captured from ``cer_v0_3/cleanroom/canon.py`` BEFORE the
extraction and are asserted against ``ugence_jcs`` AFTER it. Any divergence in the
emitted byte stream — key ordering, escaping, set-path handling, container framing
— fails here, which is what makes the extraction a preservation rather than a
rewrite.
"""
from __future__ import annotations

import hashlib

import pytest

from ugence_jcs import canonical_bytes, canonical_string

#: (value, set_paths, canonical text, sha256 of the canonical bytes)
VECTORS = [
    ({"b": "1", "a": "2"}, frozenset(),
     '{"a":"2","b":"1"}',
     "f7a837dc9b605d08d450f14bb4927ae8ab268b757d17b579b4e8e61500d87c4a"),
    ({"z": {"y": "x"}, "a": ["3", "1", "2"]}, frozenset(),
     '{"a":["3","1","2"],"z":{"y":"x"}}',
     "ea966f31969a0adf4ae262a864c88b21d4a495c0ed3cceca2c1990b75d88f5ee"),
    ({"s": ["b", "a", "c"]}, frozenset({"s"}),
     '{"s":["a","b","c"]}',
     "0ddc22f3560af6a4745e12d3f5d4494ab6bc254204fbbf9db57d0d6b2e80d442"),
    ({"t": "a\tb\nc\"d\\e\x01f\x1f"}, frozenset(),
     '{"t":"a\\tb\\nc\\"d\\\\e\\u0001f\\u001f"}',
     "b5c62320cba9d0188d729b636d87d4e253e68c6d99f093ab77c18a3cd49009ea"),
    ({"u": "café 中文 \U0001F600"}, frozenset(),
     '{"u":"café 中文 \U0001F600"}',
     "74914e10ec99775cea06641ae1bff2fd3b7682fbe27466f3c75b739c689de235"),
    ({"k": True, "l": False, "m": None}, frozenset(),
     '{"k":true,"l":false,"m":null}',
     "bd423b8ce88e350245a32ba4d95da88f7b991b8100b345baaa66cd6a9c7a4f44"),
    ({"a": "1", "A": "2", "é": "3", "\U0001F600": "4", "b": "5", "ﬀ": "6"},
     frozenset(),
     '{"A":"2","a":"1","b":"5","é":"3","\U0001F600":"4","ﬀ":"6"}',
     "1dde3b94ff5ec761182b96f039c7ce017cd6f34896ca7797842fa5fe60b32676"),
    ({"nested": {"arr": [{"q": "1"}, {"p": "2"}]}}, frozenset(),
     '{"nested":{"arr":[{"q":"1"},{"p":"2"}]}}',
     "f5c96be1edb62795e9fb2426435cb9b0e92c5d6f9846fd21c84f1ef39435d85d"),
    ({"deep": {"set": ["b", "a"]}}, frozenset({"deep.set"}),
     '{"deep":{"set":["a","b"]}}',
     "2d7b227e225e0d434c8c4fb70c967fd4911c9a3d21799452ca5814f903aa95cf"),
    ([], frozenset(), "[]",
     "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"),
    ({}, frozenset(), "{}",
     "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"),
]


@pytest.mark.parametrize("value,set_paths,expected,digest", VECTORS)
def test_canonical_bytes_are_byte_for_byte_preserved(value, set_paths, expected, digest):
    produced = canonical_bytes(value, set_paths)
    assert produced == expected.encode("utf-8")
    assert hashlib.sha256(produced).hexdigest() == digest


@pytest.mark.parametrize("value,set_paths,expected,digest", VECTORS)
def test_canonical_string_matches_bytes(value, set_paths, expected, digest):
    assert canonical_string(value, set_paths).encode("utf-8") == canonical_bytes(
        value, set_paths)


def test_output_is_utf8_without_bom_or_whitespace():
    produced = canonical_bytes({"a": "1", "b": {"c": "2"}})
    assert not produced.startswith(b"\xef\xbb\xbf")
    assert b" " not in produced and b"\n" not in produced


def test_repeated_calls_are_stable():
    value = {"b": ["2", "1"], "a": {"z": "9", "y": "8"}}
    assert canonical_bytes(value) == canonical_bytes(value)
