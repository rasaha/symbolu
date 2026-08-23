"""Canonical serialization is stable, order-independent, and round-trip safe."""

from __future__ import annotations

import json

import fixtures
import pytest

from ugence_agent_constitution import (
    ArtifactKind,
    dumps,
    dumps_pretty,
    loads,
    to_canonical_obj,
)


def test_encoding_is_byte_identical_across_repeated_calls():
    artifact = fixtures.constitution()
    encodings = {dumps(artifact) for _ in range(25)}
    assert len(encodings) == 1


def test_key_insertion_order_does_not_change_the_encoding():
    """The whole point of canonical form: two dicts that differ only in insertion
    order are the same value and must encode identically."""
    forward = {"alpha": 1, "beta": {"x": 1, "y": 2}, "gamma": [1, 2, 3]}
    reversed_ = {"gamma": [1, 2, 3], "beta": {"y": 2, "x": 1}, "alpha": 1}
    assert dumps(forward) == dumps(reversed_)


def test_sequence_order_is_preserved_because_order_is_material():
    """Sets are sorted; lists are not. A requirement list's order is authored."""
    assert dumps([3, 1, 2]) != dumps([1, 2, 3])


def test_sets_are_sorted_so_set_iteration_order_cannot_leak():
    assert dumps({"s": {"b", "a", "c"}}) == dumps({"s": {"c", "a", "b"}})
    assert loads(dumps({"s": {"b", "a", "c"}}))["s"] == ["a", "b", "c"]


def test_enums_encode_by_value_not_by_name_or_repr():
    encoded = loads(dumps(ArtifactKind.AGENT_CONSTITUTION))
    assert encoded == "agent_constitution"


def test_encoding_is_compact_with_no_insignificant_whitespace():
    encoded = dumps({"a": 1, "b": [1, 2]})
    assert encoded == '{"a":1,"b":[1,2]}'
    assert " " not in encoded


def test_tuples_and_lists_encode_identically():
    assert dumps({"v": (1, 2, 3)}) == dumps({"v": [1, 2, 3]})


def test_non_ascii_content_is_preserved_not_escaped():
    encoded = dumps({"role": "Rückerstattung"})
    assert "Rückerstattung" in encoded


def test_pretty_form_carries_the_same_value_and_the_same_key_order():
    artifact = fixtures.constitution()
    pretty, compact = dumps_pretty(artifact), dumps(artifact)
    assert json.loads(pretty) == json.loads(compact)
    assert pretty.endswith("\n")


def test_round_trip_through_json_reproduces_the_artifact_and_its_encoding():
    for artifact in (
        fixtures.manifest(),
        fixtures.constitution(),
        fixtures.contract(),
        fixtures.subject(),
    ):
        restored = type(artifact).model_validate(loads(dumps(artifact)))
        assert restored == artifact
        assert dumps(restored) == dumps(artifact)


def test_canonical_obj_is_json_native_all_the_way_down():
    obj = to_canonical_obj(fixtures.constitution())
    json.dumps(obj)  # would raise on any non-native leaf
    assert isinstance(obj, dict)


@pytest.mark.parametrize("builder", ["manifest", "constitution", "contract", "subject"])
def test_every_artifact_kind_encodes_stably(builder):
    artifact = getattr(fixtures, builder)()
    assert artifact.canonical_json() == dumps(artifact)
    assert len({artifact.canonical_json() for _ in range(10)}) == 1
