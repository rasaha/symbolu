"""Canonical serialization + digest tests."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from ugence_cloud_scaling_controller.canonical import serialization as ser


def test_sorted_keys_and_stable_output():
    a = ser.canonical_json({"b": 1, "a": 2, "c": {"z": 1, "y": 2}})
    b = ser.canonical_json({"c": {"y": 2, "z": 1}, "a": 2, "b": 1})
    assert a == b
    assert a == '{"a":2,"b":1,"c":{"y":2,"z":1}}'


def test_none_preserved_not_dropped():
    assert ser.canonical_json({"x": None}) == '{"x":null}'


def test_bool_before_int():
    assert ser.canonical_json({"t": True, "f": False}) == '{"f":false,"t":true}'


def test_negative_zero_normalized():
    assert ser.canonical_json(-0.0) == ser.canonical_json(0.0)


def test_nan_and_inf_rejected():
    for bad in (float("nan"), math.inf, -math.inf):
        with pytest.raises(ser.CanonicalizationError):
            ser.canonical_json(bad)


def test_datetime_rfc3339_utc():
    naive = datetime(2026, 8, 11, 12, 0, 0)
    aware = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
    assert ser.canonical_json(naive) == ser.canonical_json(aware)
    assert ser.canonical_json(aware) == '"2026-08-11T12:00:00.000000Z"'


def test_unicode_nfc_normalized():
    # U+00E9 (é) vs U+0065 U+0301 (e + combining acute) normalize to the same NFC form.
    composed = "café"
    decomposed = "café"
    assert ser.canonical_json(composed) == ser.canonical_json(decomposed)


def test_set_sorted_and_tuple_order_preserved():
    assert ser.canonical_json({3, 1, 2}) == "[1,2,3]"
    assert ser.canonical_json((3, 1, 2)) == "[3,1,2]"


def test_digest_is_sha256_prefixed_hex():
    d = ser.content_digest("dom", "v1", {"a": 1})
    assert d.startswith("sha256:")
    assert len(d) == len("sha256:") + 64
    int(d.split(":", 1)[1], 16)  # hex-decodable


def test_digest_domain_separation():
    payload = {"a": 1}
    assert ser.content_digest("dom_a", "v1", payload) != ser.content_digest("dom_b", "v1", payload)
    assert ser.content_digest("dom", "v1", payload) != ser.content_digest("dom", "v2", payload)


def test_digest_stable_and_sensitive():
    assert ser.content_digest("d", "v1", {"a": 1}) == ser.content_digest("d", "v1", {"a": 1})
    assert ser.content_digest("d", "v1", {"a": 1}) != ser.content_digest("d", "v1", {"a": 2})


def test_non_string_map_key_rejected():
    with pytest.raises(ser.CanonicalizationError):
        ser.canonical_json({1: "x"})
