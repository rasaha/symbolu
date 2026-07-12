"""All conformance vectors + pinned-digest reproducibility (spec §19)."""

from __future__ import annotations

import json

import pytest

from action_gate_ref import conformance

RESULT = conformance.run_conformance()


def test_all_vectors_pass():
    failed = [r["vector"] for r in RESULT["results"] if not r["passed"]]
    assert not failed, failed


def test_at_least_24_vectors():
    assert RESULT["count"] >= 24


@pytest.mark.parametrize("vec", [r["vector"] for r in RESULT["results"]])
def test_vector(vec):
    r = next(r for r in RESULT["results"] if r["vector"] == vec)
    assert r["passed"], r["detail"]


def test_pinned_digests_reproducible():
    a = conformance.pinned_digests()
    b = conformance.pinned_digests()
    assert a == b
    assert len(a["action_hash_sha256"]) == 64
    assert a["reference_action_byte_len"] == len(
        a["reference_action_canonical_bytes"].encode("utf-8"))


def test_generated_fixture_matches_current_impl():
    # The committed fixture must equal what the current implementation produces
    # (regression pinning: a canonical-bytes or digest drift fails here).
    path = conformance.FIXTURES / "conformance_vectors.json"
    if not path.exists():
        pytest.skip("fixture not generated yet")
    committed = json.loads(path.read_text())
    assert committed["pinned"] == conformance.pinned_digests()
    live = {r["vector"]: r["passed"] for r in conformance.run_conformance()["results"]}
    assert all(live.values())
