"""``canonical_sha256_hex``: a bare SHA-256 over exactly ``canonical_bytes``.

No domain tag, no length prefix, no envelope framing, no ``sha256:`` prefix, and
no Unicode or refusal logic of its own — everything is inherited from
``canonical_bytes``, and these tests prove that inheritance rather than restating
the canonicalizer's rules.
"""
import hashlib
import re
import subprocess
import sys
import textwrap

import pytest
from ugence_jcs import canonical_bytes, canonical_sha256_hex
from ugence_jcs.errors import (
    BareNumberError,
    DuplicateSetElementError,
    NonFiniteNumberError,
    NonNFCError,
    UnsupportedTypeError,
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")

# (value, set_paths, nfc_paths) covering objects, arrays, nesting, non-ASCII and
# NFC-normalizable strings, typed-string numerics, booleans and null.
VALUES = [
    ({}, frozenset(), frozenset()),
    ([], frozenset(), frozenset()),
    ({"b": "1", "a": "2"}, frozenset(), frozenset()),
    ({"a": ["c", "b", "a"]}, frozenset(), frozenset()),
    ({"s": ["b", "a", "c"]}, frozenset({"s"}), frozenset()),
    ({"nested": {"arr": [{"q": "1"}, {"p": "2"}]}}, frozenset(), frozenset()),
    ({"flag": True, "off": False, "none": None}, frozenset(), frozenset()),
    ({"amount": "12.50", "count": "3"}, frozenset(), frozenset()),
    ({"u": "café 中文 \U0001F600"}, frozenset(), frozenset()),
    ({"a": "é"}, frozenset(), frozenset({"a"})),   # composed: NFC, accepted
    ({"a": "é"}, frozenset(), frozenset()),       # decomposed on an undeclared path
    ({"t": "a\tb\nc\"d\\e\x01f\x1f"}, frozenset(), frozenset()),
    ([{"k": "v"}, ["x", "y"], "z", True, None], frozenset(), frozenset()),
]

REFUSALS = [
    (({"a": 1}, frozenset(), frozenset()), BareNumberError),
    (({"a": 0.5}, frozenset(), frozenset()), BareNumberError),
    (({"a": float("inf")}, frozenset(), frozenset()), NonFiniteNumberError),
    (({"a": float("nan")}, frozenset(), frozenset()), NonFiniteNumberError),
    (({"a": "é"}, frozenset(), frozenset({"a"})), NonNFCError),
    (({"a": {"b"}}, frozenset(), frozenset()), UnsupportedTypeError),
    (({("a",): "1"}, frozenset(), frozenset()), UnsupportedTypeError),
    (({"a": ["b", "b"]}, frozenset({"a"}), frozenset()), DuplicateSetElementError),
]


@pytest.mark.parametrize("value,set_paths,nfc_paths", VALUES)
def test_is_sha256_of_canonical_bytes(value, set_paths, nfc_paths):
    expected = hashlib.sha256(canonical_bytes(value, set_paths, nfc_paths)).hexdigest()
    assert canonical_sha256_hex(value, set_paths, nfc_paths) == expected


@pytest.mark.parametrize("value,set_paths,nfc_paths", VALUES)
def test_output_is_64_lowercase_hex_with_no_prefix(value, set_paths, nfc_paths):
    produced = canonical_sha256_hex(value, set_paths, nfc_paths)
    assert HEX64.match(produced), produced
    assert not produced.startswith("sha256:")


@pytest.mark.parametrize("value,set_paths,nfc_paths", VALUES)
def test_keyword_arguments_are_forwarded_unchanged(value, set_paths, nfc_paths):
    assert canonical_sha256_hex(value, set_paths=set_paths, nfc_paths=nfc_paths) == \
        canonical_sha256_hex(value, set_paths, nfc_paths)


def test_key_insertion_order_does_not_change_the_digest():
    a = {"b": "1", "a": "2", "\U0001F600": "3", "é": "4"}
    b = {"é": "4", "a": "2", "\U0001F600": "3", "b": "1"}
    assert list(a) != list(b)
    assert canonical_sha256_hex(a) == canonical_sha256_hex(b)

    nested_a = {"outer": {"y": "1", "x": "2"}, "arr": [{"q": "1", "p": "2"}]}
    nested_b = {"arr": [{"p": "2", "q": "1"}], "outer": {"x": "2", "y": "1"}}
    assert canonical_sha256_hex(nested_a) == canonical_sha256_hex(nested_b)


def test_unicode_behaviour_is_inherited_from_canonical_bytes():
    # The fixtures of test_action_profile.py's NFC test, run through the new function.
    decomposed = "é"
    with pytest.raises(NonNFCError) as exc:
        canonical_sha256_hex({"a": decomposed}, frozenset(), frozenset({"a"}))
    assert exc.value.category == "E_NON_NFC" and exc.value.path == "a"
    # Undeclared paths pass through unchanged — never normalized by either function.
    assert canonical_sha256_hex({"a": decomposed}) == \
        hashlib.sha256(('{"a":"%s"}' % decomposed).encode()).hexdigest()
    assert canonical_sha256_hex({"a": decomposed}) != canonical_sha256_hex({"a": "é"})
    # Member ordering stays UTF-16 code-unit ordering, not code-point ordering.
    mixed = {"a": "1", "A": "2", "é": "3", "\U0001F600": "4", "b": "5", "ﬀ": "6"}
    assert canonical_sha256_hex(mixed) == \
        hashlib.sha256(canonical_bytes(mixed)).hexdigest()


@pytest.mark.parametrize("value,set_paths,nfc_paths", VALUES)
def test_deterministic_within_a_process(value, set_paths, nfc_paths):
    results = {canonical_sha256_hex(value, set_paths, nfc_paths) for _ in range(10)}
    assert len(results) == 1


def test_deterministic_across_fresh_interpreters():
    script = textwrap.dedent(
        """
        import sys
        sys.path.insert(0, sys.argv[1])
        from ugence_jcs import canonical_sha256_hex
        values = [
            ({"b": "1", "a": "2"}, frozenset()),
            ({"s": ["b", "a", "c"]}, frozenset({"s"})),
            ({"u": "caf\\u00e9 \\u4e2d\\u6587 \\U0001F600"}, frozenset()),
            ({"nested": {"arr": [{"q": "1"}, {"p": "2"}]}}, frozenset()),
        ]
        print(",".join(canonical_sha256_hex(v, s) for v, s in values))
        """
    )
    src = str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src")
    runs = []
    for seed in ("0", "1", "random"):
        out = subprocess.run(
            [sys.executable, "-c", script, src],
            capture_output=True, text=True, check=True,
            env={**__import__("os").environ, "PYTHONHASHSEED": seed},
        )
        runs.append(out.stdout.strip())
    expected = ",".join(
        canonical_sha256_hex(v, s) for v, s in (
            ({"b": "1", "a": "2"}, frozenset()),
            ({"s": ["b", "a", "c"]}, frozenset({"s"})),
            ({"u": "café 中文 \U0001F600"}, frozenset()),
            ({"nested": {"arr": [{"q": "1"}, {"p": "2"}]}}, frozenset()),
        )
    )
    assert runs == [expected, expected, expected]


@pytest.mark.parametrize("args,exc", REFUSALS)
def test_refusal_parity_with_canonical_bytes(args, exc):
    value, set_paths, nfc_paths = args
    with pytest.raises(exc) as from_bytes:
        canonical_bytes(value, set_paths, nfc_paths)
    with pytest.raises(exc) as from_hex:
        canonical_sha256_hex(value, set_paths, nfc_paths)
    assert type(from_hex.value) is type(from_bytes.value)
    assert from_hex.value.category == from_bytes.value.category
    assert from_hex.value.path == from_bytes.value.path
