"""Determinism + canonical serialization tests (§19, §28)."""
from __future__ import annotations

from _support import SCENARIOS, result_of
from ugence_governance_studio_api.serialization.canonical import canonical_bytes, canonical_digest


def test_canonical_json_is_byte_stable():
    obj = {"b": 2, "a": [3, 1, 2], "c": {"y": 1, "x": 2}}
    assert canonical_bytes(obj) == canonical_bytes(dict(reversed(list(obj.items()))))


def test_canonical_digest_stable():
    obj = {"k": [1, 2, 3]}
    assert canonical_digest(obj) == canonical_digest(dict(obj))


def test_scenario_fingerprints_match_frozen(client):
    for sid in SCENARIOS:
        result = result_of(client.get(f"/api/v1/scenarios/{sid}/plan"))
        assert result["verification"]["match"] is True


def test_export_bundle_deterministic(client):
    a = result_of(client.get("/api/v1/scenarios/procurement/export"))
    b = result_of(client.get("/api/v1/scenarios/procurement/export"))
    assert canonical_digest(a) == canonical_digest(b)
