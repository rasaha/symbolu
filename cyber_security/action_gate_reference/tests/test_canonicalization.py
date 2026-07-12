"""Canonicalization + Action Profile (spec §2-§7)."""

from __future__ import annotations

import pytest

from action_gate_ref import jcs
from action_gate_ref.errors import (
    BareNumberError, DuplicateKeyError, NanInfError, NonNFCError,
)


def test_key_order_independent():
    assert jcs.canonicalize({"b": "1", "a": "2"}) == jcs.canonicalize({"a": "2", "b": "1"})


def test_whitespace_independent():
    a = jcs.canonicalize(jcs.load_strict(b'{"a":"1",  "b":\n "2"}'))
    b = jcs.canonicalize(jcs.load_strict(b'{"a":"1","b":"2"}'))
    assert a == b


def test_omit_vs_null_differ():
    assert jcs.canonicalize({"x": "1"}) != jcs.canonicalize({"x": "1", "y": None})


def test_bare_number_rejected():
    with pytest.raises(BareNumberError) as ei:
        jcs.canonicalize({"n": 5})
    assert ei.value.code == "E_BARE_NUMBER"
    with pytest.raises(BareNumberError):
        jcs.canonicalize({"n": 1.5})


def test_bool_null_allowed():
    assert jcs.canonicalize({"a": True, "b": False, "c": None}) == b'{"a":true,"b":false,"c":null}'


def test_duplicate_key_rejected():
    with pytest.raises(DuplicateKeyError) as ei:
        jcs.load_strict(b'{"a":"1","a":"2"}')
    assert ei.value.code == "E_DUP_KEY"


def test_nan_inf_rejected():
    for tok in (b'{"x": NaN}', b'{"x": Infinity}', b'{"x": -Infinity}'):
        with pytest.raises(NanInfError):
            jcs.load_strict(tok)


def test_set_reorder_same_ordered_reorder_diff():
    sp = frozenset({"perms"})
    assert jcs.canonicalize({"perms": ["x", "y"]}, sp) == jcs.canonicalize({"perms": ["y", "x"]}, sp)
    assert jcs.canonicalize({"list": ["x", "y"]}) != jcs.canonicalize({"list": ["y", "x"]})


def test_set_duplicate_rejected():
    with pytest.raises(DuplicateKeyError):
        jcs.canonicalize({"perms": ["x", "x"]}, frozenset({"perms"}))


def test_nfc_required_rejects_nfd():
    nfd = "é"  # e + combining acute
    with pytest.raises(NonNFCError):
        jcs.canonicalize({"name": nfd}, nfc_paths=frozenset({"name"}))
    # not rewritten elsewhere: NFC and NFD are distinct raw strings
    assert jcs.canonicalize({"name": "é"}) != jcs.canonicalize({"name": nfd})


def test_string_escaping():
    assert jcs.canonicalize({"s": 'a"\\\n\t'}) == b'{"s":"a\\"\\\\\\n\\t"}'


def test_reproducible_across_runs():
    v = {"z": "1", "a": ["b", "c"], "m": {"k": None}}
    assert jcs.canonicalize(v) == jcs.canonicalize(v)
