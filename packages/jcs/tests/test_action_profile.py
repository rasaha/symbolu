"""Action Profile behaviour: what the canonicalizer accepts and what it refuses.

The profile fails closed. Each rejection below is a canonicalization fault with a
stable ``category``; none of them is a policy, authorization or clearance outcome,
and this package emits no such vocabulary.
"""
from __future__ import annotations

import pytest

from ugence_jcs import canonical_bytes
from ugence_jcs.errors import (
    BareNumberError,
    DuplicateSetElementError,
    JcsError,
    NonFiniteNumberError,
    NonNFCError,
    UnsupportedTypeError,
)


def test_member_names_sort_by_utf16_code_unit_order():
    # U+FB00 (BMP) sorts BEFORE U+1F600 in code-POINT order but AFTER it in UTF-16
    # code-unit order, because the astral character encodes to a D800-range surrogate.
    produced = canonical_bytes({"ﬀ": "1", "\U0001F600": "2"}).decode("utf-8")
    assert produced.index("\U0001F600") < produced.index("ﬀ")


def test_c0_controls_escape_and_non_ascii_stays_literal():
    produced = canonical_bytes({"a": "\x00\x1fé"}).decode("utf-8")
    assert "\\u0000" in produced and "\\u001f" in produced
    assert "é" in produced and "\\u00e9" not in produced


def test_short_escapes_only_for_the_seven_specified():
    produced = canonical_bytes({"a": "\b\t\n\f\r\"\\"}).decode("utf-8")
    assert '"a":"\\b\\t\\n\\f\\r\\"\\\\"' in produced


def test_bare_integer_rejected():
    with pytest.raises(BareNumberError) as exc:
        canonical_bytes({"replicas": 12})
    assert exc.value.category == "E_BARE_NUMBER"
    assert exc.value.path == "replicas"


def test_bare_float_rejected():
    with pytest.raises(BareNumberError):
        canonical_bytes({"ratio": 0.5})


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_float_rejected_before_bare_number(bad):
    with pytest.raises(NonFiniteNumberError) as exc:
        canonical_bytes({"x": bad})
    assert exc.value.category == "E_NAN_INF"


def test_unsupported_type_rejected():
    with pytest.raises(UnsupportedTypeError):
        canonical_bytes({"x": {"y"}})


def test_non_string_key_rejected():
    with pytest.raises(UnsupportedTypeError):
        canonical_bytes({("a",): "1"})


def test_arrays_keep_declaration_order_by_default():
    assert canonical_bytes({"a": ["c", "b", "a"]}) == b'{"a":["c","b","a"]}'


def test_declared_set_paths_sort_and_reject_duplicates():
    assert canonical_bytes({"a": ["c", "b"]}, frozenset({"a"})) == b'{"a":["b","c"]}'
    with pytest.raises(DuplicateSetElementError) as exc:
        canonical_bytes({"a": ["b", "b"]}, frozenset({"a"}))
    assert exc.value.category == "E_DUPLICATE_SET_ELEMENT"


def test_duplicates_outside_declared_set_paths_are_kept():
    assert canonical_bytes({"a": ["b", "b"]}) == b'{"a":["b","b"]}'


def test_nfc_validated_never_rewritten_on_declared_paths():
    decomposed = "e\u0301"  # NOT NFC; the composed form is U+00E9
    with pytest.raises(NonNFCError) as exc:
        canonical_bytes({"a": decomposed}, frozenset(), frozenset({"a"}))
    assert exc.value.category == "E_NON_NFC" and exc.value.path == "a"
    # Undeclared paths are passed through unchanged — validated, never normalized.
    assert canonical_bytes({"a": decomposed}) == ('{"a":"%s"}' % decomposed).encode()


def test_tuples_canonicalize_as_arrays():
    assert canonical_bytes({"a": ("b", "c")}) == canonical_bytes({"a": ["b", "c"]})


def test_every_fault_is_a_jcs_error():
    for thunk in (lambda: canonical_bytes({"a": 1}),
                  lambda: canonical_bytes({"a": {"b"}}),
                  lambda: canonical_bytes({"a": ["b", "b"]}, frozenset({"a"}))):
        with pytest.raises(JcsError):
            thunk()
